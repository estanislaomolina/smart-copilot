"""Integridad del evaluador, sin red ni juicios de precisión del modelo."""
import asyncio
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import httpx
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from backend.domain.models import AnalysisResult, IncidentData
from backend.protocols.models import ProtocolResult
from backend.providers.base import ProviderError
from scripts.evaluate import Case, Suite, compare, evaluate, summarize, summarize_review, main, merge_reports


class EvaluationTests(unittest.TestCase):
    def test_unknown_is_not_a_missing_question_or_a_correct_known_value(self):
        case = Case(id="dev", transcript="Llamante: No sé la dirección.",
                    fields={"location.number": None, "location.street": "Horizonte"},
                    questions=[{"text": "¿Hay heridos?", "status": "pending"}])
        checks = compare(case, IncidentData(), ProtocolResult(selection="pending"))
        self.assertEqual([item["passed"] for item in checks], [True, False, False])

    def test_only_transcript_reaches_provider_and_expectations_are_compared_locally(self):
        received = []
        class Provider:
            async def analyze(self, request):
                received.append(request.model_dump())
                return AnalysisResult(request=request, data=IncidentData(), provider="mock")
        class Engine:
            def apply(self, request):
                self.request = request
                return ProtocolResult(selection="pending")
        suite = Suite(split="development", description="Prueba local.", cases=[
            Case(id="not-for-provider", transcript="Llamante: No sé.", fields={"priority": None},
                 focus="metadata-local", review_notes=["No enviar al modelo."])])
        results = asyncio.run(evaluate(suite, Provider(), Engine()))
        self.assertEqual(received, [{"transcript": "Llamante: No sé."}])
        self.assertEqual(results[0]["status"], "passed")

    def test_quota_stops_remaining_cases_and_does_not_copy_remote_errors(self):
        class Provider:
            calls = 0
            async def analyze(self, request):
                self.calls += 1
                raise ProviderError("provider_rate_limited", "Texto externo que no se debe guardar.")
        provider = Provider()
        suite = Suite(split="development", description="Prueba local.", cases=[
            Case(id=str(i), transcript="Llamante: No sé.", fields={"priority": None}) for i in range(2)])
        results = asyncio.run(evaluate(suite, provider, SimpleNamespace()))
        self.assertEqual(provider.calls, 1)
        self.assertEqual([r["status"] for r in results], ["error", "skipped"])
        self.assertNotIn("Texto externo", str(results))


    def test_stage_timings_and_attempts_distinguish_retries_without_sleeping(self):
        attempts = [0]
        class Provider:
            async def analyze(self, request):
                attempts[0] += 2  # Dos intentos de transporte simulados.
                return AnalysisResult(request=request, data=IncidentData(), provider="real", model="test")
        class Engine:
            def apply(self, request):
                attempts[0] += 1
                return ProtocolResult(selection="pending")
        suite = Suite(split="development", description="Prueba local.", cases=[
            Case(id="timing", transcript="Llamante: No sé.", fields={"priority": None})])
        with patch("scripts.evaluate.time", SimpleNamespace(monotonic=iter([0, 0, 2, 2, 5, 5]).__next__)):
            results = asyncio.run(evaluate(suite, Provider(), Engine(), lambda: attempts[0]))
        result = results[0]
        self.assertEqual(result["timings_seconds"], {"extraction": 2, "checklist": 3, "total": 5})
        self.assertEqual(result["request_attempts"], {"extraction": 2, "checklist": 1})
        self.assertEqual(result["retries"], {"extraction": 1, "checklist": 0})
        self.assertEqual(summarize(results)["latency_seconds"]["checklist"]["median"], 3)

    def test_checklist_error_preserves_extraction_and_never_certifies_semantic_support(self):
        class Provider:
            async def analyze(self, request):
                data = IncidentData.model_validate({
                    "summary": {"value": "Se desconoce el incidente.", "origin": "transcript",
                                "evidence": [{"text": "No sé.", "start": 10, "end": 16}]}})
                return AnalysisResult(request=request, data=data, provider="mock")
        class Engine:
            def apply(self, request):
                raise ProviderError("invalid_provider_output", "Cuerpo remoto privado")
        suite = Suite(split="development", description="Prueba local.", cases=[
            Case(id="partial", transcript="Llamante: No sé.", fields={"location.number": None},
                 questions=[{"text": "Pregunta no evaluada", "status": "pending"}])])
        # La cita es exacta, pero la interpretación del resumen no se certifica automáticamente.
        results = asyncio.run(evaluate(suite, Provider(), Engine()))
        result = results[0]
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["stage"], "checklist")
        self.assertEqual(len(result["checks"]), 1)
        self.assertTrue(result["checks"][0]["passed"])
        self.assertIsNotNone(result["timings_seconds"]["checklist"])
        self.assertEqual(result["human_review"]["entries"][0]["verdict"], "pending")
        self.assertEqual(summarize(results)["terminal_invalid_outputs"], 1)
        self.assertEqual(summarize_review(results)["pending"], 1)
        self.assertEqual(summarize_review(results)["supported"], 0)
        result["human_review"]["entries"][0]["verdict"] = "unsupported"
        self.assertEqual(summarize_review(results)["unsupported"], 1)


    def test_groq_cli_observes_transport_without_retries_or_live_network(self):
        client_type = httpx.Client
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            unknown = {"value": None, "origin": "unknown", "quotes": [], "rationale": None}
            output = {"location": {key: unknown for key in
                                  ("street", "number", "intersection", "reference", "district")},
                      "category": unknown, "subcategory": unknown, "risks": [], "summary": unknown}
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop",
                "message": {"content": json.dumps(output)}}]})
        def client(**kwargs):
            return client_type(transport=httpx.MockTransport(handler), **kwargs)
        with TemporaryDirectory() as folder:
            cases, report = Path(folder) / "cases.json", Path(folder) / "report.json"
            cases.write_text(json.dumps({"split": "development", "description": "Prueba local.",
                "cases": [{"id": "local-only", "transcript": "Llamante: No sé.",
                           "fields": {"priority": None}, "review_notes": ["No enviar."]}]}))
            argv = ["evaluate.py", "--provider", "groq", "--cases", str(cases), "--output", str(report)]
            with patch.dict(os.environ, {"GROQ_API_KEY": "local-test-key", "LLM_MAX_RETRIES": "1"}), \
                 patch("sys.argv", argv), patch("httpx.Client", side_effect=client), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            result = json.loads(report.read_text())
            with patch("sys.argv", argv), patch("httpx.Client", side_effect=AssertionError("No consultar")), \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                main()
            self.assertEqual(stopped.exception.code, 2)
        self.assertEqual(len(sent), 1)
        self.assertEqual(json.loads(sent[0]["messages"][1]["content"]), {"transcript": "Llamante: No sé."})
        self.assertEqual(result["configuration"]["max_retries"], 0)
        self.assertEqual(result["results"][0]["request_attempts"], {"extraction": 1, "checklist": 0})
        self.assertEqual(result["not_selected"], 0)
        self.assertEqual(result["summary"]["attempt_diagnostics"]["attempts_recorded"], 1)


    def test_merge_keeps_errors_and_rejects_duplicate_cases_or_different_configs(self):
        common = {"report_version": 2, "cases_sha256": "frozen", "split": "evaluation",
                  "provider": "groq", "model": "test", "prompt_version": "v1", "configuration": {}}
        error = {"id": "one", "status": "error", "code": "invalid_provider_output",
                 "timings_seconds": {"extraction": 4, "checklist": None, "total": 4}}
        passed = {"id": "two", "status": "passed", "checks": [],
                  "timings_seconds": {"extraction": 3, "checklist": 2, "total": 5}}
        with TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.json", Path(folder) / "b.json"
            a.write_text(json.dumps({**common, "results": [error]}))
            b.write_text(json.dumps({**common, "results": [passed]}))
            combined = merge_reports([a, b])
            self.assertEqual(combined["counts"], {"passed": 1, "failed": 0, "error": 1, "skipped": 0})
            self.assertEqual(combined["summary"]["terminal_invalid_outputs"], 1)
            self.assertEqual(combined["summary"]["latency_seconds"]["checklist"]["samples"], 1)
            out = Path(folder) / "merged.json"
            with patch("sys.argv", ["evaluate.py", "--merge-reports", str(a), str(b),
                                    "--output", str(out)]), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 1)  # El error previo sigue contando.
            self.assertEqual(json.loads(out.read_text())["counts"], combined["counts"])
            with self.assertRaisesRegex(ValueError, "dos veces"):
                merge_reports([a, a])
            b.write_text(json.dumps({**common, "results": [error], "created_at": "other-run"}))
            with self.assertRaisesRegex(ValueError, "casos repetidos"):
                merge_reports([a, b])
            b.write_text(json.dumps({**common, "prompt_version": "v2", "results": [passed]}))
            with self.assertRaisesRegex(ValueError, "No se mezclan"):
                merge_reports([a, b])


    def test_extraction_only_skips_protocol_and_reports_recovered_validation(self):
        events = []
        class Provider:
            async def analyze(self, request):
                events.extend([
                    {"schema": "ExtractedIncident", "attempt": 1, "outcome": "local_validation",
                     "issues": [{"type": "evidence_not_found", "field": "summary"}]},
                    {"schema": "ExtractedIncident", "attempt": 2, "outcome": "valid", "issues": []}])
                return AnalysisResult(request=request, data=IncidentData(), provider="mock")
        class Engine:
            def apply(self, request):
                raise AssertionError("No debe ejecutar protocolos")
        suite = Suite(split="development", description="Prueba local.", cases=[
            Case(id="repair", transcript="Llamante: No sé.", fields={"priority": None})])
        results = asyncio.run(evaluate(suite, Provider(), Engine(), lambda: len(events),
                                       attempt_events=events, extract_only=True))
        self.assertEqual(results[0]["request_attempts"]["extraction"], 2)
        self.assertIsNone(results[0]["timings_seconds"]["checklist"])
        stats = summarize(results)["attempt_diagnostics"]
        self.assertEqual(stats["stages_recovered_after_retry"], 1)
        self.assertEqual(stats["first_attempt_validation_failures"], 1)
        self.assertEqual(stats["outcomes"], {"local_validation": 1, "valid": 1})


if __name__ == "__main__":
    unittest.main()
