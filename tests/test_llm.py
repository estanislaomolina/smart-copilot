"""Frontera real del SDK con transporte HTTP controlado; no mide precisión del modelo."""
import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import anthropic
import httpx
from fastapi.testclient import TestClient

from backend.domain.models import AnalysisRequest, IncidentData, FieldValue, ProtocolQuestion
from backend.main import create_app
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.protocols.models import ProtocolRequest
from backend.protocols.evaluation import ChecklistEvaluationRequest
from backend.providers.base import ProviderError
from backend.providers.config import ProviderSettings, GROQ_MODEL
from backend.providers.groq import GroqGateway, strict_schema
from backend.providers.llm_models import ExtractedIncident
from backend.providers.haiku import HaikuGateway
from backend.providers.llm import LLMExtractionProvider, LLMChecklistEvaluator
from backend.providers.llm_models import Quote

TEXT = "Llamante: Hay fuego 🏠. Hay tres personas heridas."


def unknown():
    return {"value": None, "origin": "unknown", "quotes": [], "rationale": None}


def field(value, quote, origin="transcript"):
    return {"value": value, "origin": origin, "quotes": [{"text": quote}],
            "rationale": "Interpretación a revisar." if origin == "inference" else None}


def incident():
    return {"location": {key: unknown() for key in ("street", "number", "intersection", "reference", "district")},
            "category": field("INCENDIO_RESCATE", "Hay fuego", "inference"),
            "subcategory": unknown(), "risks": [field("tres personas heridas", "Hay tres personas heridas.")],
            "summary": field("Se reporta fuego y tres personas heridas.", TEXT, "inference")}


def response(output, stop="end_turn"):
    return httpx.Response(200, json={
        "id": "msg_local_test", "type": "message", "role": "assistant",
        "model": "claude-haiku-4-5-20251001", "stop_reason": stop, "stop_sequence": None,
        "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
        "usage": {"input_tokens": 10, "output_tokens": 10},
    })


class HaikuTests(unittest.TestCase):
    def gateway(self, handler, retries=0):
        client = anthropic.Anthropic(api_key="local-test-key", max_retries=0,
                                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        return HaikuGateway(ProviderSettings(provider="haiku", api_key="local-test-key", retries=retries), client)

    def test_sdk_structured_output_evidence_and_unassigned_priority(self):
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return response(incident())
        provider = LLMExtractionProvider(self.gateway(handler))
        result = asyncio.run(provider.analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(result.provider, "real")
        self.assertEqual(result.data.category.value, "INCENDIO_RESCATE")
        self.assertIsNone(result.data.priority.value)
        for value in result.data.fields():
            for span in value.evidence:
                self.assertEqual(TEXT[span.start:span.end], span.text)
        self.assertEqual(json.loads(requests[0]["messages"][0]["content"]), {"transcript": TEXT})
        self.assertEqual(requests[0]["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("priority", requests[0]["output_config"]["format"]["schema"]["properties"])
        self.assertNotIn("instructions", requests[0]["output_config"]["format"]["schema"]["properties"])
        repeated = Quote(text="🏠 sí").resolve("sí 🏠 sí")
        self.assertEqual(repeated.start, 3)
        with self.assertRaises(ValueError):
            Quote(text="sí").resolve("sí 🏠 sí")
        with self.assertRaises(ValueError):
            Quote(text="ausente").resolve(TEXT)

    def test_invented_evidence_category_and_claimed_operator_are_rejected(self):
        bad_quote = incident(); bad_quote["category"]["quotes"][0]["text"] = "Texto inexistente"
        bad_category = incident(); bad_category["category"]["value"] = "CATEGORIA_INVENTADA"
        bad_origin = incident(); bad_origin["category"]["origin"] = "operator"
        bad_unknown = incident(); bad_unknown["location"]["street"]["value"] = "Calle supuesta"
        for output in (bad_quote, bad_category, bad_origin, bad_unknown):
            with self.subTest(output=output):
                provider = LLMExtractionProvider(self.gateway(lambda request: response(output)))
                with self.assertRaises(ProviderError) as raised:
                    asyncio.run(provider.analyze(AnalysisRequest(transcript=TEXT)))
                self.assertEqual(raised.exception.code, "invalid_provider_output")

    def test_truncated_and_refused_outputs_never_become_results(self):
        for stop in ("max_tokens", "refusal"):
            gateway = self.gateway(lambda request: response(incident(), stop))
            with self.assertRaises(ProviderError) as raised:
                asyncio.run(LLMExtractionProvider(gateway).analyze(AnalysisRequest(transcript=TEXT)))
            self.assertEqual(raised.exception.code, "invalid_provider_output")

    def test_bounded_retry_and_safe_error_mapping(self):
        calls = []
        def flaky(request):
            calls.append(request)
            return httpx.Response(429, json={"error": {"type": "rate_limit_error", "message": "private-marker"}}) if len(calls) == 1 else response(incident())
        with patch("backend.providers.haiku.time.sleep"):
            asyncio.run(LLMExtractionProvider(self.gateway(flaky, 1)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(len(calls), 2)
        for status, expected_code, count in ((401, "provider_unavailable", 1), (503, "provider_unavailable", 2),
                                              (0, "provider_timeout", 2)):
            calls = []
            def failing(request):
                calls.append(request)
                if status == 0:
                    raise httpx.ReadTimeout("private-marker", request=request)
                return httpx.Response(status, json={"error": {"type": "api_error", "message": "private-marker"}})
            with patch("backend.providers.haiku.time.sleep"):
                with self.assertRaises(ProviderError) as raised:
                    asyncio.run(LLMExtractionProvider(self.gateway(failing, 1)).analyze(AnalysisRequest(transcript=TEXT)))
            self.assertEqual(raised.exception.code, expected_code)
            self.assertNotIn("private-marker", str(raised.exception))
            self.assertEqual(len(calls), count)

    def test_checklist_uses_only_received_questions_and_preserves_manual_review(self):
        catalog = ProtocolCatalog()
        definition = catalog.general_for("INCENDIO_RESCATE")
        questions = definition.questions
        payloads = []
        def handler(request):
            payload = json.loads(json.loads(request.content)["messages"][0]["content"])
            payloads.append(payload)
            return response({"questions": [
                {"id": q.id, "status": "answered" if index == 1 else "pending",
                 "answer": "Tres personas heridas." if index == 1 else None,
                 "quotes": [{"text": "Hay tres personas heridas."}] if index == 1 else [],
                 "rationale": None} for index, q in enumerate(questions)]})
        evaluator = LLMChecklistEvaluator(self.gateway(handler))
        evaluated = evaluator.evaluate(ChecklistEvaluationRequest(transcript=TEXT, questions=questions))
        self.assertEqual(evaluated.questions[1].status, "answered")
        manual = ProtocolQuestion(id=questions[1].id, text=questions[1].text, status="answered",
                                  answer="Respuesta confirmada distinta", origin="operator")
        data = IncidentData(category=FieldValue(value="INCENDIO_RESCATE", origin="operator"), questions=[manual])
        result = ProtocolEngine(catalog, evaluator).apply(ProtocolRequest(request=AnalysisRequest(transcript=TEXT), data=data))
        self.assertEqual(result.questions[1].answer, manual.answer)
        self.assertEqual(result.questions[1].origin, "operator")
        self.assertTrue(result.review_notices)
        self.assertEqual(set(payloads[0]), {"transcript", "questions"})
        self.assertTrue(all(set(q) == {"id", "text", "answer_type", "follow_up"} for q in payloads[0]["questions"]))
        invalid = LLMChecklistEvaluator(self.gateway(lambda request: response({"questions": [{
            "id": "invented", "status": "pending", "answer": None, "quotes": [], "rationale": None}]})))
        with self.assertRaises(ProviderError):
            invalid.evaluate(ChecklistEvaluationRequest(transcript=TEXT, questions=questions))

    def test_http_configuration_and_explicit_manual_continuation_without_remote_calls(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(401, json={"error": {"type": "authentication_error", "message": "private-marker"}})
        gateway = self.gateway(handler)
        with TemporaryDirectory() as folder, patch.dict(os.environ, {
            "LLM_PROVIDER": "haiku", "ANTHROPIC_API_KEY": "local-test-key",
        }), patch("backend.main.HaikuGateway", return_value=gateway):
            with TestClient(create_app(db_path=Path(folder) / "calls.sqlite3")) as client:
                self.assertEqual(client.get("/api/config").json()["configured_provider"], "haiku")
                failed = client.post("/api/analyze", json={"transcript": TEXT})
                self.assertEqual(failed.status_code, 503)
                self.assertNotIn("private-marker", failed.text)
                self.assertNotIn("local-test-key", failed.text)
                count = len(calls)
                manual = client.post("/api/protocols/apply", json={
                    "request": {"transcript": TEXT},
                    "data": {"category": {"value": "INCENDIO_RESCATE", "origin": "operator"}},
                    "manual_only": True,
                })
                self.assertEqual(manual.status_code, 200, manual.text)
                self.assertTrue(all(q["status"] == "pending" for q in manual.json()["questions"]))
                self.assertEqual(len(calls), count)
                self.assertTrue(any("Carga manual" in warning for warning in manual.json()["warnings"]))

    def test_missing_key_and_invalid_provider_configuration_fail_explicitly(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "haiku", "ANTHROPIC_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "ANTHROPIC_API_KEY"):
                ProviderSettings.from_env()
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock", "ANTHROPIC_API_KEY": "", "LLM_TIMEOUT_SECONDS": "invalid"}):
            self.assertEqual(ProviderSettings.from_env().provider, "mock")



def groq_response(output, finish="stop", **message_fields):
    return httpx.Response(200, json={
        "choices": [{"finish_reason": finish, "message": {
            "role": "assistant", "content": json.dumps(output, ensure_ascii=False), **message_fields}}],
    })


class GroqTests(unittest.TestCase):
    def gateway(self, handler, retries=0, on_attempt=None):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return GroqGateway(ProviderSettings(provider="groq", model=GROQ_MODEL,
                                            api_key="local-groq-test-key", retries=retries), client, on_attempt)

    def test_strict_request_and_shared_conversion_keep_evidence_checks(self):
        requests = []
        def handler(request):
            requests.append(request)
            return groq_response(incident())
        result = asyncio.run(LLMExtractionProvider(self.gateway(handler)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(result.model, GROQ_MODEL)
        self.assertEqual(result.provider, "real")
        self.assertEqual(result.data.category.value, "INCENDIO_RESCATE")
        self.assertIsNone(result.data.priority.value)
        self.assertTrue(any("Groq" in warning for warning in result.warnings))
        request = requests[0]
        self.assertEqual(str(request.url), "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer local-groq-test-key")
        body = json.loads(request.content)
        self.assertEqual(json.loads(body["messages"][1]["content"]), {"transcript": TEXT})
        self.assertEqual(body["reasoning_effort"], "medium")
        self.assertEqual(body["max_completion_tokens"], 3000)
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        def check(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    self.assertEqual(set(node["required"]), set(node["properties"]))
                    self.assertFalse(node["additionalProperties"])
                self.assertNotIn("default", node)
                self.assertNotIn("const", node)
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)
        check(strict_schema(ExtractedIncident))
        bad = incident(); bad["category"]["quotes"][0]["text"] = "Texto ausente"
        with self.assertRaises(ProviderError) as raised:
            asyncio.run(LLMExtractionProvider(self.gateway(lambda request: groq_response(bad))).analyze(
                AnalysisRequest(transcript=TEXT)))
        self.assertEqual(raised.exception.code, "invalid_provider_output")

    def test_known_fields_require_quotes_in_remote_schema_and_local_validation(self):
        schema = strict_schema(ExtractedIncident)
        for name in ("ReportedField", "InferredField"):
            self.assertEqual(schema["$defs"][name]["properties"]["quotes"]["minItems"], 1)
        self.assertEqual(schema["$defs"]["UnknownField"]["properties"]["quotes"]["maxItems"], 0)
        for key in ("category", "subcategory", "summary"):
            malformed = incident()
            if malformed[key]["value"] is None:
                malformed[key] = field("Subtipo informado", "Hay fuego", "inference")
            malformed[key]["quotes"] = []
            with self.subTest(field=key), self.assertRaises(ProviderError):
                asyncio.run(LLMExtractionProvider(self.gateway(
                    lambda request: groq_response(malformed))).analyze(AnalysisRequest(transcript=TEXT)))

    def test_malformed_truncated_refused_and_tool_outputs_are_rejected(self):
        cases = [
            groq_response(incident(), "length"),
            groq_response(incident(), refusal="Rechazado"),
            groq_response(incident(), tool_calls=[{"function": {"name": "inventado"}}]),
            httpx.Response(200, json={"choices": []}),
            httpx.Response(200, json={"choices": ["malformed"]}),
            httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{bad"}}]}),
        ]
        for response in cases:
            with self.subTest(response=response.text):
                gateway = self.gateway(lambda request: response)
                with self.assertRaises(ProviderError) as raised:
                    asyncio.run(LLMExtractionProvider(gateway).analyze(AnalysisRequest(transcript=TEXT)))
                self.assertEqual(raised.exception.code, "invalid_provider_output")

    def test_free_quota_is_not_retried_and_transport_retry_is_bounded(self):
        for status, expected, count in ((429, "provider_rate_limited", 1),
                                        (401, "provider_unavailable", 1),
                                        (503, "provider_unavailable", 2),
                                        (0, "provider_timeout", 2)):
            calls = []
            def handler(request):
                calls.append(request)
                if status == 0:
                    raise httpx.ReadTimeout("private-marker", request=request)
                return httpx.Response(status, json={"error": {"message": "private-marker"}})
            with patch("backend.providers.groq.time.sleep"):
                with self.assertRaises(ProviderError) as raised:
                    asyncio.run(LLMExtractionProvider(self.gateway(handler, 1)).analyze(AnalysisRequest(transcript=TEXT)))
            self.assertEqual(raised.exception.code, expected)
            self.assertEqual(len(calls), count)
            self.assertNotIn("private-marker", str(raised.exception))
        calls = []
        def flaky(request):
            calls.append(request)
            return httpx.Response(503) if len(calls) == 1 else groq_response(incident())
        with patch("backend.providers.groq.time.sleep"):
            result = asyncio.run(LLMExtractionProvider(self.gateway(flaky, 1)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(result.provider, "real")
        self.assertEqual(len(calls), 2)

    def test_checklist_states_require_consistent_answers_and_evidence(self):
        from backend.providers.llm_models import EvaluatedChecklist
        from pydantic import ValidationError
        entries = [
            {"id": "q", "status": "ambiguous", "answer": None, "quotes": [], "rationale": "Falta confirmar."},
            {"id": "q", "status": "answered", "answer": "Sí.", "quotes": [], "rationale": None},
            {"id": "q", "status": "pending", "answer": "No sé", "quotes": [], "rationale": None},
        ]
        for entry in entries:
            with self.subTest(status=entry["status"]), self.assertRaises(ValidationError):
                EvaluatedChecklist.model_validate({"questions": [entry]})

    def test_remote_schema_rejection_has_one_bounded_correction(self):
        calls, trace = [], []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(400, json={"error": {"code": "json_validate_failed",
                                                          "failed_generation": "private-marker"}})
            return groq_response(incident())
        with patch("backend.providers.groq.time.sleep"):
            result = asyncio.run(LLMExtractionProvider(self.gateway(handler, 1, trace.append)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(result.provider, "real")
        self.assertEqual(len(calls), 2)
        self.assertNotIn("private-marker", calls[1].content.decode())
        self.assertEqual([e["outcome"] for e in trace], ["remote_schema", "valid"])
        self.assertEqual(trace[0]["issues"], [{"type": "json_invalid", "field": "response"}])
        self.assertNotIn("private-marker", json.dumps(trace))
        calls = []
        def invalid(request):
            calls.append(request)
            return httpx.Response(400, json={"error": {"code": "json_validate_failed"}})
        with patch("backend.providers.groq.time.sleep"), self.assertRaises(ProviderError) as raised:
            asyncio.run(LLMExtractionProvider(self.gateway(invalid, 1)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(raised.exception.code, "invalid_provider_output")
        self.assertEqual(len(calls), 2)

    def test_literal_quote_validation_can_request_one_correction_without_fuzzy_matching(self):
        calls, trace = [], []
        def handler(request):
            calls.append(request)
            output = incident()
            if len(calls) == 1:
                output["category"]["quotes"][0]["text"] = "Cita no literal"
            return groq_response(output)
        with patch("backend.providers.groq.time.sleep"):
            result = asyncio.run(LLMExtractionProvider(self.gateway(handler, 1, trace.append)).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(len(calls), 2)
        self.assertEqual(result.data.category.evidence[0].text, "Hay fuego")
        self.assertEqual([e["outcome"] for e in trace], ["local_validation", "valid"])
        self.assertTrue(any(i["type"] == "evidence_not_found" for i in trace[0]["issues"]))
        self.assertNotIn("Cita no literal", json.dumps(trace))
        self.assertNotIn(TEXT, json.dumps(trace))
        repaired_request = json.loads(calls[1].content)
        self.assertNotIn("Cita no literal", repaired_request["messages"][0]["content"])
        feedback = json.loads(repaired_request["messages"][2]["content"])
        self.assertIn("Cita no literal", feedback["previous_output"])
        self.assertTrue(feedback["validation_errors"])
        self.assertNotIn("input", feedback["validation_errors"][0])

    def test_reported_risk_cannot_promote_an_interpretation_to_caller_fact(self):
        output = incident()
        output["risks"][0]["value"] = "Persona inconsciente"
        with self.assertRaises(ProviderError):
            asyncio.run(LLMExtractionProvider(self.gateway(
                lambda request: groq_response(output))).analyze(AnalysisRequest(transcript=TEXT)))
        output["risks"][0] = field("Posible afectación grave", "Hay tres personas heridas.", "inference")
        result = asyncio.run(LLMExtractionProvider(self.gateway(
            lambda request: groq_response(output))).analyze(AnalysisRequest(transcript=TEXT)))
        self.assertEqual(result.data.risks[0].origin, "inference")

    def test_groq_selected_without_anthropic_and_http_quota_allows_manual_flow(self):
        calls = []
        limited = False
        def handler(request):
            nonlocal limited
            calls.append(request)
            if limited:
                return httpx.Response(429, json={"error": {"message": "private-marker"}})
            payload = json.loads(json.loads(request.content)["messages"][1]["content"])
            if "questions" not in payload:
                return groq_response(incident())
            return groq_response({"questions": [
                {"id": q["id"], "status": "answered" if index == 1 else "pending",
                 "answer": "Tres personas heridas." if index == 1 else None,
                 "quotes": [{"text": "Hay tres personas heridas."}] if index == 1 else [],
                 "rationale": None} for index, q in enumerate(payload["questions"])]})
        gateway = self.gateway(handler)
        with TemporaryDirectory() as folder, patch.dict(os.environ, {
            "LLM_PROVIDER": "groq", "GROQ_API_KEY": "local-groq-test-key",
            "ANTHROPIC_API_KEY": "unused-anthropic-test-key",
        }), patch("backend.main.GroqGateway", return_value=gateway), patch(
            "backend.main.HaikuGateway", side_effect=AssertionError("Anthropic no seleccionado")):
            with TestClient(create_app(db_path=Path(folder) / "groq.sqlite3")) as client:
                config = client.get("/api/config").json()
                self.assertEqual(config["configured_provider"], "groq")
                self.assertEqual(config["configured_model"], GROQ_MODEL)
                self.assertEqual(config["stage"], "llm_analysis")
                analyzed = client.post("/api/analyze", json={"transcript": TEXT})
                self.assertEqual(analyzed.status_code, 200, analyzed.text)
                data = analyzed.json()["data"]
                guide = client.post("/api/protocols/apply", json={"request": {"transcript": TEXT}, "data": data})
                self.assertEqual(guide.status_code, 200, guide.text)
                self.assertEqual(guide.json()["questions"][1]["status"], "answered")
                self.assertEqual(len(calls), 2)
                limited = True
                failed = client.post("/api/analyze", json={"transcript": TEXT})
                self.assertEqual(failed.status_code, 429)
                self.assertEqual(failed.json()["code"], "provider_rate_limited")
                self.assertNotIn("private-marker", failed.text)
                self.assertNotIn("local-groq-test-key", failed.text)
                count = len(calls)
                manual = client.post("/api/protocols/apply", json={
                    "request": {"transcript": TEXT}, "data": data, "manual_only": True})
                self.assertEqual(manual.status_code, 200, manual.text)
                self.assertEqual(len(calls), count)
                self.assertTrue(all(q["status"] == "pending" for q in manual.json()["questions"]))

    def test_configuration_requires_only_selected_provider_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "",
                                     "ANTHROPIC_API_KEY": "not-a-groq-key"}):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                ProviderSettings.from_env()
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "local-groq-test-key"}):
            settings = ProviderSettings.from_env()
            self.assertEqual(settings.model, GROQ_MODEL)
            self.assertNotIn("local-groq-test-key", repr(settings))
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock", "GROQ_API_KEY": "unused"}):
            self.assertEqual(ProviderSettings.from_env().provider, "mock")


    def test_failed_correction_stays_rejected_and_truncation_is_not_retried(self):
        bad = incident()
        bad["category"]["quotes"][0]["text"] = "missing-private-text"
        trace, calls = [], []
        def invalid(request):
            calls.append(request)
            return groq_response(bad)
        with patch("backend.providers.groq.time.sleep"), self.assertRaises(ProviderError):
            asyncio.run(LLMExtractionProvider(self.gateway(invalid, 1, trace.append)).analyze(
                AnalysisRequest(transcript=TEXT)))
        self.assertEqual(len(calls), 2)
        self.assertEqual([e["outcome"] for e in trace], ["local_validation", "local_validation"])
        self.assertNotIn("missing-private-text", json.dumps(trace))
        trace, calls = [], []
        def truncated(request):
            calls.append(request)
            return groq_response(incident(), "length")
        with self.assertRaises(ProviderError):
            asyncio.run(LLMExtractionProvider(self.gateway(truncated, 1, trace.append)).analyze(
                AnalysisRequest(transcript=TEXT)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(trace[0]["outcome"], "truncated")

    def test_unknown_location_type_keeps_raw_name_as_reference(self):
        text = TEXT + " Estoy en La Ribera, pero no sé si es calle o barrio."
        output = incident()
        output["location"]["reference"] = field("La Ribera", "La Ribera")
        output["location"]["reference"]["rationale"] = "El tipo de ubicación sigue desconocido."
        for key in ("street", "district"):
            output["location"][key]["rationale"] = "No se determina el tipo de ubicación."
        result = asyncio.run(LLMExtractionProvider(self.gateway(lambda request: groq_response(output))).analyze(
            AnalysisRequest(transcript=text)))
        self.assertIsNone(result.data.location.street.value)
        self.assertIsNone(result.data.location.district.value)
        self.assertEqual(result.data.location.reference.value, "La Ribera")
        self.assertEqual(result.data.location.reference.evidence[0].text, "La Ribera")


if __name__ == "__main__":
    unittest.main()
