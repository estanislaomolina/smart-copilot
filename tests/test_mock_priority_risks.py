"""Riesgos y prioridades: regresión del CSV y límites de las reglas de simulación."""

import asyncio
import csv
import unittest
from pathlib import Path

from backend.domain.models import AnalysisRequest, Evidence, FieldValue
from backend.providers.mock import MockExtractionProvider
from backend.providers.mock_rules import RiskAssessment, suggest_priority

DATASET = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"

# Solo escenarios con reglas explícitas. Los demás NO reciben prioridad por defecto.
REVIEWED_PRIORITIES = {
    "001": "P1", "002": "P3", "003": "P2", "009": "P1", "010": "P2",
    "012": "P1", "014": "P2", "018": "P1", "019": "P1", "020": "P1",
    "022": "P1", "023": "P2", "024": "P3", "026": "P1", "027": "P2",
    "028": "P2", "029": "P1",
}


class MockRiskPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with DATASET.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = {row["id_registro"][-3:]: row for row in csv.DictReader(handle)}

    def analyze(self, text):
        return asyncio.run(MockExtractionProvider().analyze(AnalysisRequest(transcript=text)))

    def risk_ids(self, result):
        return {risk.rationale.split(":", 1)[0] for risk in result.data.risks}

    def test_priority_values_on_reviewed_csv_scenarios(self):
        for record_id, expected in REVIEWED_PRIORITIES.items():
            with self.subTest(record_id=record_id):
                row = self.rows[record_id]
                self.assertEqual(row["prioridad_sugerida"], expected)
                result = self.analyze(row["transcripcion_cruda"])
                self.assertEqual(result.data.priority.value, expected)
                self.assertEqual(result.data.priority.origin, "inference")
                self.assertTrue(result.data.priority.evidence)
                self.assertIn("P-", result.data.priority.rationale)

    def test_uncovered_calls_are_unknown_instead_of_default_priority(self):
        # No hay regla para quema junto a juegos o para síncope recuperado.
        for record_id in ("004", "008"):
            with self.subTest(record_id=record_id):
                result = self.analyze(self.rows[record_id]["transcripcion_cruda"])
                self.assertIsNone(result.data.priority.value)
                self.assertEqual(result.data.priority.origin, "unknown")
                self.assertTrue(any("no hay una regla" in w for w in result.warnings))

    def test_risks_are_supported_signals_not_copied_diagnoses(self):
        result = self.analyze(self.rows["009"]["transcripcion_cruda"])
        self.assertEqual([risk.value for risk in result.data.risks],
                         ["Posible dificultad respiratoria"])
        self.assertNotIn("hipoxemia", str(result.model_dump()).casefold())

    def test_negated_trapping_does_not_trigger_fire_trapped_priority(self):
        text = self.rows["001"]["transcripcion_cruda"].replace(
            "adentro quedó el cocinero", "no hay personas atrapadas"
        )
        result = self.analyze(text)
        self.assertNotIn("R-TRAPPED", self.risk_ids(result))
        self.assertIsNone(result.data.priority.value)

    def test_negated_fire_does_not_trigger_container_priority(self):
        text = self.rows["002"]["transcripcion_cruda"].replace(
            "prendieron fuego", "no hay fuego"
        ).replace("Las llamas ya tienen como dos metros", "No hay llamas")
        result = self.analyze(text)
        self.assertNotIn("R-FIRE", self.risk_ids(result))
        self.assertIsNone(result.data.priority.value)

    def test_negation_of_fire_does_not_hide_fuel_spill(self):
        result = self.analyze(self.rows["022"]["transcripcion_cruda"])
        self.assertIn("R-FUEL", self.risk_ids(result))
        self.assertNotIn("R-FIRE", self.risk_ids(result))
        self.assertIsNone(result.data.category.value)
        self.assertEqual(result.data.priority.value, "P1")

    def test_uncertain_convulsion_requires_confirmation(self):
        text = self.rows["026"]["transcripcion_cruda"].replace(
            "está convulsionando", "creo que está convulsionando"
        )
        result = self.analyze(text)
        self.assertNotIn("R-CONVULSION", self.risk_ids(result))
        self.assertIsNone(result.data.priority.value)
        self.assertTrue(any("ambigua" in w for w in result.warnings))

    def test_contradiction_without_explicit_correction_is_unknown(self):
        text = self.rows["026"]["transcripcion_cruda"] + " Llamante: No está convulsionando."
        result = self.analyze(text)
        self.assertNotIn("R-CONVULSION", self.risk_ids(result))
        self.assertIsNone(result.data.priority.value)
        self.assertTrue(any("contradictoria" in w for w in result.warnings))

    def test_explicit_correction_can_retract_a_signal(self):
        text = self.rows["026"]["transcripcion_cruda"] + " Llamante: Perdón, no está convulsionando."
        result = self.analyze(text)
        self.assertNotIn("R-CONVULSION", self.risk_ids(result))
        self.assertIsNone(result.data.priority.value)
        self.assertFalse(any("contradictoria" in w for w in result.warnings))

    def test_explicit_correction_can_confirm_a_signal(self):
        text = self.rows["026"]["transcripcion_cruda"].replace(
            "está convulsionando", "no está convulsionando"
        ) + " Llamante: Corrijo: está convulsionando."
        result = self.analyze(text)
        self.assertIn("R-CONVULSION", self.risk_ids(result))
        self.assertEqual(result.data.priority.value, "P1")

    def test_clause_order_does_not_change_fire_trapped_priority(self):
        body = self.rows["001"]["transcripcion_cruda"].split("Llamante:", 1)[1]
        text = "Llamante:" + ", ".join(reversed(body.split(",")))
        self.assertEqual(self.analyze(text).data.priority.value, "P1")

    def test_operator_question_is_not_a_risk_assertion(self):
        text = self.rows["026"]["transcripcion_cruda"].split("Llamante:", 1)[0]
        text += " Operador: ¿Está convulsionando?"
        result = self.analyze(text)
        self.assertEqual(result.data.risks, [])
        self.assertIsNone(result.data.priority.value)

    def test_priority_evidence_cites_all_required_signals(self):
        text = self.rows["001"]["transcripcion_cruda"]
        priority = self.analyze(text).data.priority
        fragments = [span.text for span in priority.evidence]
        self.assertIn("fuego", fragments)
        self.assertIn("adentro quedó el cocinero", fragments)
        for span in priority.evidence:
            self.assertEqual(text[span.start:span.end], span.text)


class PriorityDecisionTests(unittest.TestCase):
    """Aísla la decisión de prioridad del reconocimiento de expresiones."""

    def signal(self):
        return FieldValue[str](
            value="señal", origin="inference",
            evidence=[Evidence(text="señal", start=0, end=5)],
            rationale="Dato de prueba del contrato de decisión.",
        )

    def test_highest_recognized_priority_wins_without_hiding_other_risks(self):
        signals = {code: self.signal() for code in ("R-SIGNALS", "R-CONVULSION")}
        assessment = RiskAssessment(signals, set(), [])
        priority, _ = suggest_priority(
            assessment, FieldValue(value="SERVICIOS_PUBLICOS", origin="operator"),
        )
        self.assertEqual(priority.value, "P1")
        self.assertEqual(set(assessment.signals), {"R-SIGNALS", "R-CONVULSION"})

    def test_lower_priority_needs_the_expected_category(self):
        assessment = RiskAssessment({"R-INJURY": self.signal()}, set(), [])
        priority, _ = suggest_priority(assessment, FieldValue())
        self.assertIsNone(priority.value)

    def test_ambiguous_signal_blocks_an_automatic_lower_priority(self):
        assessment = RiskAssessment({"R-SIGNALS": self.signal()}, {"R-CONVULSION"}, [])
        priority, _ = suggest_priority(
            assessment, FieldValue(value="SERVICIOS_PUBLICOS", origin="operator"),
        )
        self.assertIsNone(priority.value)


if __name__ == "__main__":
    unittest.main()
