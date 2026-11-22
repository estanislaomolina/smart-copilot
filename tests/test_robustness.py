"""Transformaciones conocidas: preservan corpus, roles, negación y expectativas."""
import asyncio
import unittest

from scripts.evaluate import Case, Suite
from scripts.evaluate_robustness import variants, number_words, run


class RobustnessTests(unittest.TestCase):
    def test_variants_preserve_dialogue_and_do_not_rewrite_expectations(self):
        text = "Operador: ¿Hay heridos?\nLlamante: No, en Aurora 518.\nLlamante: Corrijo: 820."
        changed = variants(text)
        self.assertEqual(changed["original"], text)
        self.assertIn("Llamante: No", changed["espacios"].replace("  ", " "))
        self.assertIn("\nLlamante: Bueno, eh, No", changed["muletillas"])
        self.assertIn("quinientos dieciocho", changed["numeros_en_palabras"])
        self.assertIn("Corrijo: ochocientos veinte", changed["numeros_en_palabras"])
        self.assertEqual(changed["numeros_en_palabras"].count("\n"), 2)
        self.assertEqual(number_words(100), "cien")
        self.assertEqual(number_words(1540), "mil quinientos cuarenta")
        self.assertEqual(number_words(9999), "nueve mil novecientos noventa y nueve")
        self.assertIn("007", variants("Llamante: código 007, ruta 5/7.")["numeros_en_palabras"])
        self.assertEqual(variants(text), changed)

    def test_offline_runner_reports_every_variant_and_preserves_source(self):
        case = Case(id="known", transcript="Llamante: No sé la dirección.",
                    fields={"location.street": None})
        suite = Suite(split="development", description="Conocido.", cases=[case])
        before = suite.model_dump_json()
        report = asyncio.run(run(suite))
        self.assertEqual(suite.model_dump_json(), before)
        self.assertEqual(len(report), 5)
        for name, row in report.items():
            self.assertEqual(row["cases"], 1)
            self.assertEqual(sum(row["counts"].values()), 1)
            self.assertEqual(row["results"][0]["id"], "known/" + name)
            self.assertEqual(row["summary"]["literal_comparisons"]["location"]["compared"], 1)
