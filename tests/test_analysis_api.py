"""Entrada HTTP, integración del mock y fallos del contrato de proveedor."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import create_app, get_provider
from backend.providers.base import ProviderError


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            self.app = create_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_analyze_returns_mock_result_and_keeps_original_whitespace(self):
        text = "  Llamante: En Av. Corrientes 1540 hay fuego.  "
        response = self.client.post("/api/analyze", json={"transcript": text})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["request"]["transcript"], text)
        self.assertEqual(result["provider"], "mock")
        self.assertEqual(result["data"]["location"]["number"]["value"], "1540")
        self.assertEqual(result["data"]["category"]["value"], "INCENDIO_RESCATE")
        self.assertIsNone(result["data"]["priority"]["value"])

    def test_csv_call_returns_risks_and_priority_through_http(self):
        import csv
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            text = next(csv.DictReader(handle))["transcripcion_cruda"]
        response = self.client.post("/api/analyze", json={"transcript": text})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["model"], "rules-v2")
        self.assertEqual(result["data"]["priority"]["value"], "P1")
        self.assertIn("P-FIRE-TRAPPED", result["data"]["priority"]["rationale"])
        self.assertTrue(result["data"]["risks"])
        for field in [*result["data"]["risks"], result["data"]["priority"]]:
            self.assertEqual(field["origin"], "inference")
            for span in field["evidence"]:
                self.assertEqual(text[span["start"]:span["end"]], span["text"])

    def test_invalid_inputs_are_rejected_without_echoing_the_input(self):
        payloads = [
            {}, {"transcript": ""}, {"transcript": "   "},
            {"transcript": 123}, {"transcript": "x" * 50_001},
            {"transcript": "private-marker", "unexpected": True},
        ]
        for payload in payloads:
            with self.subTest(payload_keys=list(payload)):
                response = self.client.post("/api/analyze", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["code"], "invalid_input")
                self.assertNotIn("private-marker", response.text)

    def test_provider_errors_have_explicit_status_and_no_internal_message(self):
        for code, status in (("provider_timeout", 504), ("provider_unavailable", 503),
                             ("invalid_provider_output", 502)):
            with self.subTest(code=code):
                class FailingProvider:
                    async def analyze(self, request):
                        raise ProviderError(code, "private-provider-detail", retryable=True)

                self.app.dependency_overrides[get_provider] = FailingProvider
                response = self.client.post("/api/analyze", json={"transcript": "hola"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["code"], code)
                self.assertTrue(response.json()["retryable"])
                self.assertNotIn("private-provider-detail", response.text)

    def test_malformed_provider_output_is_not_returned_as_success(self):
        class InvalidProvider:
            async def analyze(self, request):
                return {"unexpected": "private-provider-detail"}

        self.app.dependency_overrides[get_provider] = InvalidProvider
        response = self.client.post("/api/analyze", json={"transcript": "hola"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["code"], "invalid_provider_output")
        self.assertNotIn("private-provider-detail", response.text)

    def test_provider_cannot_replace_the_requested_transcript(self):
        class WrongTranscriptProvider:
            async def analyze(self, request):
                return {"request": {"transcript": "otro texto"}, "data": {}, "provider": "mock"}

        self.app.dependency_overrides[get_provider] = WrongTranscriptProvider
        response = self.client.post("/api/analyze", json={"transcript": "texto original"})
        self.assertEqual(response.status_code, 502)

    def test_health_and_openapi_expose_the_new_stage_and_endpoint(self):
        self.assertEqual(self.client.get("/health").json()["stage"], "mock_analysis")
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/analyze", schema["paths"])

    def test_unimplemented_provider_is_rejected_at_startup(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "real"}):
            with self.assertRaisesRegex(RuntimeError, "solo está implementado"):
                create_app()


if __name__ == "__main__":
    unittest.main()
