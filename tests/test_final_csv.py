"""Controles del runner de CSV, sin llamadas a servicios externos."""
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.evaluate_csv import COLUMNS, RequestGate, StopRequested, csv_suite, load_previous


class FinalCsvTests(unittest.TestCase):
    def test_adapter_keeps_original_and_does_not_invent_pending_question_labels(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "source.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=sorted(COLUMNS))
                writer.writeheader()
                for i in range(30):
                    writer.writerow({"id_registro": f"CALL-{i}", "transcripcion_cruda": "Llamante: Hay fuego.",
                                     "categoria": "INCENDIO_RESCATE", "subcategoria": "Referencia",
                                     "calle_detectada": "Fuente", "altura_detectada": "S/N",
                                     "interseccion_detectada": "",
                                     "preguntas_protocolo_mandatorias": "¿Hay personas? | ¿Hay gas?",
                                     "preguntas_respondidas_en_relato": "¿Hay personas? (Sí)",
                                     "preguntas_pendientes": "¿Hay otra información?"})
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            suite, references = csv_suite(path)
            self.assertEqual(len(suite.cases), 30)
            self.assertEqual(suite.split, "development")
            self.assertEqual(suite.cases[0].transcript, "Llamante: Hay fuego.")
            self.assertEqual([(q.text, q.status) for q in suite.cases[0].questions],
                             [("¿Hay personas?", "answered")])
            self.assertNotIn("priority", suite.cases[0].fields)
            self.assertNotIn("location.district", suite.cases[0].fields)
            self.assertEqual(references["source_sha256"], before)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_finished_errors_and_interrupted_requests_are_not_automatically_repeated(self):
        with TemporaryDirectory() as folder:
            report, marker = Path(folder) / "case.json", Path(folder) / "case.started"
            report.write_text(json.dumps({"id": "one", "status": "error", "code": "invalid_provider_output"}))
            self.assertEqual(load_previous(report, marker, "one")["code"], "invalid_provider_output")
            report.unlink()
            marker.write_text("{}")
            recovered = load_previous(report, marker, "one")
            self.assertEqual(recovered["code"], "run_interrupted")
            self.assertEqual(load_previous(report, marker, "one"), recovered)
            self.assertIsNone(recovered["request_attempts"]["extraction"])

    def test_request_spacing_and_budget_do_not_sleep_or_send_after_cancellation(self):
        clock = [0.]
        def sleep(seconds):
            clock[0] += seconds
        gate = RequestGate(45, 2, clock=lambda: clock[0], sleep=sleep)
        gate.before_request(None)
        gate.before_request(None)
        self.assertEqual(gate.last_wait, 45)
        self.assertEqual(gate.count, 2)
        with self.assertRaises(StopRequested):
            gate.before_request(None)
        self.assertEqual(gate.count, 2)
        cancelled = RequestGate(45, 2, should_stop=lambda: True)
        with self.assertRaises(StopRequested):
            cancelled.before_request(None)
        self.assertEqual(cancelled.count, 0)


if __name__ == "__main__":
    unittest.main()
