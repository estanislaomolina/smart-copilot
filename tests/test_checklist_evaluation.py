"""Regresión contextual y validación de la frontera del evaluador."""
import asyncio
import csv
import unittest
from pathlib import Path

from backend.domain.models import AnalysisRequest, ProtocolQuestion
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.protocols.evaluation import ChecklistEvaluationRequest, ChecklistEvaluationResult
from backend.protocols.models import ProtocolRequest
from backend.providers.base import ProviderError
from backend.providers.checklist_mock import MockChecklistEvaluator
from backend.providers.mock import MockExtractionProvider

class ChecklistEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ProtocolCatalog()
        self.evaluator = MockChecklistEvaluator()
        self.definition = self.catalog.get("sfx-demo-001").questions[0]

    def evaluate(self, text):
        return self.evaluator.evaluate(ChecklistEvaluationRequest(
            transcript=text, questions=[self.definition])).questions[0]

    def test_spontaneous_statements_uncertainty_and_corrections(self):
        cases = [
            ("Hay dos personas atrapadas.", "answered", "Hay dos personas atrapadas"),
            ("No hay nadie atrapado.", "answered", "No hay nadie atrapado"),
            ("No sé si quedó alguien.", "ambiguous", "No sé si quedó alguien"),
            ("Hay fuego en un edificio.", "pending", None),
            ("Hay dos personas atrapadas. No hay nadie atrapado.", "ambiguous", None),
            ("Hay dos personas atrapadas. Perdón, no hay nadie atrapado.", "answered", "Perdón, no hay nadie atrapado"),
        ]
        for text, status, answer in cases:
            with self.subTest(text=text):
                result = self.evaluate("Llamante: " + text)
                self.assertEqual(result.status, status)
                if answer is not None:
                    self.assertEqual(result.answer.strip(), answer)
                for span in result.evidence:
                    self.assertEqual(("Llamante: " + text)[span.start:span.end], span.text)
        self.assertEqual(self.evaluate("Operador: Hay dos personas atrapadas.").status, "pending")

    def test_fire_regression_recognizes_presence_without_claiming_entrapment(self):
        path = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            text = next(csv.DictReader(handle))["transcripcion_cruda"]
        result = self.evaluate(text)
        self.assertEqual(result.status, "ambiguous")
        self.assertNotEqual(result.answer, "Sí")
        self.assertTrue(any("adentro quedó el cocinero" in span.text.lower() for span in result.evidence))
        self.assertEqual(result.follow_up.version, "demo-follow-ups-v1")
        follow_up = result.follow_up.text
        clarified = self.evaluate(text + f"\nOperador: {follow_up}\nLlamante: No.")
        self.assertEqual(clarified.status, "answered")
        self.assertEqual(clarified.answer, "No.")
        self.assertIsNone(clarified.follow_up)
        analysis = asyncio.run(MockExtractionProvider().analyze(AnalysisRequest(transcript=text)))
        analysis.data.questions = [ProtocolQuestion(
            id=self.definition.id, text=self.definition.text, status="answered",
            answer="No.", origin="operator")]
        reviewed = ProtocolEngine(self.catalog, self.evaluator).apply(ProtocolRequest(
            request=analysis.request, data=analysis.data, protocol_id="sfx-demo-001"))
        self.assertEqual(reviewed.questions[0].origin, "operator")
        self.assertEqual(reviewed.questions[0].answer, "No.")
        self.assertTrue(reviewed.review_notices)

    def test_invalid_evaluator_output_is_rejected_before_manual_merge(self):
        definition = self.definition
        class InvalidEvaluator:
            def evaluate(self, request):
                questions = [ProtocolQuestion(id=q.id, text=q.text) for q in request.questions]
                questions[0] = ProtocolQuestion(
                    id=definition.id, text=definition.text, status="answered", answer="Sí",
                    origin="transcript", evidence=[{"text": "ZZ", "start": 0, "end": 2}])
                return ChecklistEvaluationResult(questions=questions)
        analysis = asyncio.run(MockExtractionProvider().analyze(AnalysisRequest(transcript="Llamante: Hola.")))
        with self.assertRaises(ProviderError) as error:
            ProtocolEngine(self.catalog, InvalidEvaluator()).apply(ProtocolRequest(
                request=analysis.request, data=analysis.data, protocol_id="sfx-demo-001"))
        self.assertEqual(error.exception.code, "invalid_provider_output")
