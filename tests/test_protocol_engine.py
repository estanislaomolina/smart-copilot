"""Catálogo, selección conservadora y checklist con evidencia; sin llamadas externas."""

import asyncio
import csv
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.domain.models import AnalysisRequest, ProtocolQuestion
from backend.main import create_app
from backend.protocols.catalog import ProtocolCatalog, DEFAULT_CATALOG
from backend.protocols.engine import ProtocolEngine
from backend.protocols.models import ProtocolRequest
from backend.providers.mock import MockExtractionProvider
from scripts.build_protocol_catalog import build_catalog


class ProtocolEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = ProtocolCatalog()
        cls.engine = ProtocolEngine(cls.catalog)
        path = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            cls.transcript = next(csv.DictReader(handle))["transcripcion_cruda"]
        cls.analysis = asyncio.run(MockExtractionProvider().analyze(
            AnalysisRequest(transcript=cls.transcript)
        ))

    def apply(self, suffix="", protocol_id="sfx-demo-001", data=None):
        return self.engine.apply(ProtocolRequest(
            request=AnalysisRequest(transcript=self.transcript + suffix),
            data=data or self.analysis.data, protocol_id=protocol_id,
        ))

    def test_catalog_is_reproducible_and_does_not_import_call_answers(self):
        self.assertEqual(json.loads(DEFAULT_CATALOG.read_text()), build_catalog())
        self.assertEqual(len(self.catalog.protocols), 30)
        serialized = DEFAULT_CATALOG.read_text()
        for key in ("transcripcion_cruda", "preguntas_respondidas_en_relato",
                    "preguntas_pendientes", "prioridad_sugerida", "altura_detectada"):
            self.assertNotIn('"' + key + '":', serialized)

    def test_category_alone_keeps_selection_pending_and_does_not_copy_answers(self):
        pending = self.apply(protocol_id=None)
        self.assertEqual(pending.selection, "pending")
        self.assertGreater(len(pending.candidates), 1)
        self.assertEqual(pending.questions, [])
        self.assertEqual(pending.instructions, [])
        selected = self.apply()
        self.assertEqual(selected.selection, "selected")
        self.assertTrue(all(q.status == "pending" for q in selected.questions))
        self.assertEqual(selected.instructions[0].review_status, "demo_unverified")
        subtype = self.catalog.get("sfx-demo-001").subcategory
        data = self.analysis.data.model_copy(deep=True)
        data.subcategory.value = subtype
        data.subcategory.origin = "operator"
        self.assertEqual(self.apply(protocol_id=None, data=data).selection, "suggested")

    def test_negative_reply_is_answered_but_uncertain_or_multiple_questions_are_ambiguous(self):
        q1, q2 = self.catalog.get("sfx-demo-001").questions[:2]
        answered = self.apply(f" Operador: {q2.text} Llamante: No.")
        self.assertEqual(answered.questions[1].status, "answered")
        self.assertEqual(answered.questions[1].answer, "No.")
        span = answered.questions[1].evidence[0]
        text = self.transcript + f" Operador: {q2.text} Llamante: No."
        self.assertEqual(text[span.start:span.end], span.text)
        uncertain = self.apply(f" Operador: {q2.text} Llamante: No sé.")
        self.assertEqual(uncertain.questions[1].status, "ambiguous")
        multiple = self.apply(f" Operador: {q1.text} {q2.text} Llamante: Sí.")
        self.assertEqual([q.status for q in multiple.questions[:2]], ["ambiguous", "ambiguous"])

    def test_conflicting_replies_need_confirmation_unless_explicitly_corrected(self):
        question = self.catalog.get("sfx-demo-001").questions[1]
        prefix = f" Operador: {question.text} Llamante: Sí."
        conflicting = self.apply(prefix + f" Operador: {question.text} Llamante: No.")
        self.assertEqual(conflicting.questions[1].status, "ambiguous")
        corrected = self.apply(prefix + f" Operador: {question.text} Llamante: Perdón, no.")
        self.assertEqual(corrected.questions[1].status, "answered")
        self.assertEqual(corrected.questions[1].answer, "Perdón, no.")

    def test_manual_answers_survive_reapply_only_when_compatible(self):
        question = self.catalog.get("sfx-demo-001").questions[1]
        data = self.analysis.data.model_copy(deep=True)
        data.questions = [ProtocolQuestion(
            id=question.id, text=question.text, status="answered",
            answer="Confirmado por el operador.", origin="operator",
        )]
        reapplied = self.apply(data=data)
        self.assertEqual(reapplied.questions[1].origin, "operator")
        self.assertEqual(reapplied.questions[1].answer, "Confirmado por el operador.")
        switched = self.apply(data=data, protocol_id="sfx-demo-002")
        self.assertTrue(all(q.status == "pending" for q in switched.questions))
        self.assertTrue(any("no corresponden" in warning for warning in switched.warnings))

    def test_http_exposes_catalog_apply_and_selection_errors(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            app = create_app()
        with TestClient(app) as client:
            options = client.get("/api/protocols", params={"category": "INCENDIO_RESCATE"})
            self.assertEqual(options.status_code, 200)
            self.assertEqual(len(options.json()), 8)
            payload = {"request": {"transcript": self.transcript},
                       "data": self.analysis.data.model_dump(mode="json"),
                       "protocol_id": "sfx-demo-001"}
            selected = client.post("/api/protocols/apply", json=payload)
            self.assertEqual(selected.status_code, 200)
            self.assertEqual(len(selected.json()["questions"]), 3)
            payload["protocol_id"] = "sfx-demo-010"
            self.assertEqual(client.post("/api/protocols/apply", json=payload).status_code, 409)
            payload["protocol_id"] = "missing"
            self.assertEqual(client.post("/api/protocols/apply", json=payload).status_code, 404)
            self.assertEqual(client.get("/api/protocols/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
