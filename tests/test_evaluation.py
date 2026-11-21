"""Integridad del evaluador, sin red ni juicios de precisión del modelo."""
import asyncio
from types import SimpleNamespace
import unittest

from backend.domain.models import AnalysisResult, IncidentData
from backend.protocols.models import ProtocolResult
from backend.providers.base import ProviderError
from scripts.evaluate import Case, Suite, compare, evaluate


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
            Case(id="not-for-provider", transcript="Llamante: No sé.", fields={"priority": None})])
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


if __name__ == "__main__":
    unittest.main()
