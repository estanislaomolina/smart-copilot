"""Regresión de desarrollo sobre el CSV provisto, no evaluación independiente."""

import asyncio
import csv
import unittest
from pathlib import Path

from backend.domain.models import AnalysisRequest, AnalysisResult
from backend.providers.mock import MockExtractionProvider

DATASET = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"

# Expectativas revisadas contra el relato, no copiadas de etiquetas enriquecidas.
# ID: (calle literal, altura explícita, referencia/intersección literal, categoría).
REVIEWED = {
    "001": ("Av. Corrientes", "1540", "Montevideo", "INCENDIO_RESCATE"),
    "002": ("Scalabrini Ortiz", "800", "Vera y Velasco", "INCENDIO_RESCATE"),
    "003": ("Billinghurst", "1845", None, "INCENDIO_RESCATE"),
    "005": ("Av. San Juan", None, "Av. San Juan y Entre Ríos", "ACCIDENTE_VIAL"),
    "009": ("Av. Directorio", "2140", None, "EMERGENCIA_MEDICA"),
    "012": ("Thames", "1900", "Nicaragua y Costa Rica", "DEFENSA_CIVIL"),
    "016": ("Sarmiento", None, "Sarmiento y Bulnes", "CONVIVENCIA_SEGURIDAD"),
    "018": ("Billinghurst", None, "Billinghurst y Gorriti", "ACCIDENTE_VIAL"),
    "019": ("Honduras", "4800", None, "EMERGENCIA_MEDICA"),
    "024": ("Av. Juan de Garay", None, "Av. Juan de Garay y Av. Boedo", "SERVICIOS_PUBLICOS"),
    "027": ("Paraguay", "3800", "Salguero y Vidt", "DEFENSA_CIVIL"),
    "028": ("Av. Montes de Oca", "1100", "Rocha", "SERVICIOS_PUBLICOS"),
}


class MockAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with DATASET.open(encoding="utf-8-sig", newline="") as handle:
            cls.rows = {row["id_registro"][-3:]: row for row in csv.DictReader(handle)}

    def analyze(self, transcript):
        return asyncio.run(MockExtractionProvider().analyze(
            AnalysisRequest(transcript=transcript)
        ))

    def test_reviewed_csv_values(self):
        for record_id, expected in REVIEWED.items():
            with self.subTest(record_id=record_id):
                result = self.analyze(self.rows[record_id]["transcripcion_cruda"])
                location = result.data.location
                actual = (location.street.value, location.number.value,
                          location.intersection.value, result.data.category.value)
                self.assertEqual(actual, expected)
                self.assertEqual(result.data.category.origin, "inference")

    def test_all_original_calls_respect_contract_and_evidence(self):
        for record_id, row in self.rows.items():
            with self.subTest(record_id=record_id):
                text = row["transcripcion_cruda"]
                result = self.analyze(text)
                self.assertEqual(result, self.analyze(text))
                AnalysisResult.model_validate_json(result.model_dump_json())
                for item in result.data.fields():
                    self.assertNotEqual(item.origin, "operator")
                    for span in item.evidence:
                        self.assertEqual(text[span.start:span.end], span.text)
                for risk in result.data.risks:
                    self.assertEqual(risk.origin, "inference")
                    self.assertTrue(risk.evidence)
                    self.assertTrue(risk.rationale)
                if result.data.priority.value is not None:
                    self.assertEqual(result.data.priority.origin, "inference")
                    self.assertTrue(result.data.priority.evidence)
                    self.assertTrue(result.data.priority.rationale)
                self.assertEqual(result.data.questions, [])

    def test_changed_address_is_processed_instead_of_original_row(self):
        text = self.rows["001"]["transcripcion_cruda"].replace(
            "Av. Corrientes 1540", "Av. Libertador 2750"
        )
        location = self.analyze(text).data.location
        self.assertEqual(location.street.value, "Av. Libertador")
        self.assertEqual(location.number.value, "2750")

    def test_explicit_correction_changes_number(self):
        text = self.rows["001"]["transcripcion_cruda"].replace(
            "1540", "1540, perdón, 1450", 1
        )
        location = self.analyze(text).data.location
        self.assertEqual(location.number.value, "1450")
        self.assertEqual(location.number.evidence[0].text, "1450")

    def test_correction_of_people_count_does_not_change_address(self):
        text = self.rows["001"]["transcripcion_cruda"] + " Llamante: Perdón, 3 personas quedaron adentro."
        self.assertEqual(self.analyze(text).data.location.number.value, "1540")

    def test_person_name_and_age_do_not_replace_address(self):
        text = self.rows["003"]["transcripcion_cruda"].replace(
            "Hay cuatro personas adentro", "Hay una señora llamada Alicia 82 años adentro"
        )
        location = self.analyze(text).data.location
        self.assertEqual(location.street.value, "Billinghurst")
        self.assertEqual(location.number.value, "1845")

    def test_conflicting_numbers_are_unknown(self):
        text = self.rows["001"]["transcripcion_cruda"].replace(
            "1540", "1540 o Av. Corrientes 1450", 1
        )
        result = self.analyze(text)
        self.assertIsNone(result.data.location.number.value)
        self.assertTrue(any("varias alturas" in warning for warning in result.warnings))

    def test_negated_fire_is_not_positive_category_evidence(self):
        text = self.rows["001"]["transcripcion_cruda"].replace(
            "se prendió fuego", "no hay fuego"
        )
        self.assertIsNone(self.analyze(text).data.category.value)

    def test_operator_questions_do_not_count_as_caller_facts(self):
        # Solo conserva el turno original del operador.
        text = self.rows["001"]["transcripcion_cruda"].split("Llamante:", 1)[0]
        result = self.analyze(text)
        self.assertIsNone(result.data.category.value)
        self.assertIsNone(result.data.location.street.value)

    def test_multiple_category_signals_require_confirmation(self):
        # La cisterna volcada con derrame es un caso real del dataset con señales mixtas.
        result = self.analyze(self.rows["022"]["transcripcion_cruda"])
        self.assertIsNone(result.data.category.value)
        self.assertTrue(any("varias categorías" in warning for warning in result.warnings))
        self.assertIsNone(result.data.location.number.value)  # 27 es parte del nombre.

    def test_plain_text_without_speaker_labels(self):
        text = self.rows["012"]["transcripcion_cruda"].split("Llamante:", 1)[1]
        result = self.analyze(text)
        self.assertEqual(result.data.location.street.value, "Thames")
        self.assertEqual(result.data.category.value, "DEFENSA_CIVIL")


if __name__ == "__main__":
    unittest.main()
