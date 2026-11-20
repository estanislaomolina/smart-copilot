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
from backend.providers.checklist_mock import MockChecklistEvaluator
from scripts.build_protocol_catalog import build_catalog


class ProtocolEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = ProtocolCatalog()
        cls.engine = ProtocolEngine(cls.catalog, MockChecklistEvaluator())
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
        self.assertEqual(sum(p.scope == "specific" for p in self.catalog.protocols.values()), 30)
        self.assertEqual(sum(p.scope == "general" for p in self.catalog.protocols.values()), 6)
        serialized = DEFAULT_CATALOG.read_text()
        for key in ("transcripcion_cruda", "preguntas_respondidas_en_relato",
                    "preguntas_pendientes", "prioridad_sugerida", "altura_detectada"):
            self.assertNotIn('"' + key + '":', serialized)

    def test_category_alone_starts_general_guide_without_copying_answers(self):
        pending = self.apply(protocol_id=None)
        self.assertEqual(pending.selection, "general")
        self.assertEqual(pending.selection_origin, "category")
        self.assertEqual(pending.protocol.scope, "general")
        self.assertGreater(len(pending.candidates), 1)
        self.assertTrue(pending.questions)
        self.assertTrue(pending.instructions)
        self.assertTrue(all(question.status != "answered" for question in pending.questions))
        selected = self.apply()
        self.assertEqual(selected.selection, "selected")
        self.assertEqual(selected.questions[0].status, "ambiguous")
        self.assertIsNotNone(selected.questions[0].follow_up)
        self.assertTrue(all(q.status == "pending" for q in selected.questions[1:]))
        self.assertEqual(selected.instructions[0].review_status, "demo_unverified")
        subtype = self.catalog.get("sfx-demo-001").subcategory
        data = self.analysis.data.model_copy(deep=True)
        data.subcategory.value = subtype
        data.subcategory.origin = "operator"
        self.assertEqual(self.apply(protocol_id=None, data=data).selection, "suggested")

    def test_general_guides_cover_categories_without_guessing_an_unknown_category(self):
        from typing import get_args
        from backend.domain.models import Category, FieldValue, IncidentData

        text = "Llamante: Necesito ayuda."
        for category in get_args(Category):
            with self.subTest(category=category):
                data = IncidentData(category=FieldValue(value=category, origin="operator"))
                result = self.engine.apply(ProtocolRequest(
                    request=AnalysisRequest(transcript=text), data=data))
                self.assertEqual(result.selection, "general")
                self.assertEqual(result.protocol.category, category)
                self.assertEqual(result.protocol.scope, "general")
                self.assertEqual(result.protocol.version, "general-demo-v1")
                self.assertTrue(all(q.status == "pending" for q in result.questions))
                self.assertTrue(all(i.review_status == "demo_unverified" for i in result.instructions))
                self.assertTrue(all("Curaduría propia" in i.source for i in result.instructions))
        unknown = self.engine.apply(ProtocolRequest(
            request=AnalysisRequest(transcript=text), data=IncidentData()))
        self.assertEqual(unknown.selection, "pending")
        self.assertIsNone(unknown.protocol)
        self.assertFalse(unknown.questions)
        self.assertFalse(unknown.instructions)

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

    def test_manual_pending_survives_a_reply_and_requires_a_reason(self):
        from pydantic import ValidationError

        question = self.catalog.get("sfx-demo-001").questions[1]
        data = self.analysis.data.model_copy(deep=True)
        data.questions = [ProtocolQuestion(
            id=question.id, text=question.text, status="pending",
            origin="operator", rationale="Necesito volver a confirmar.",
        )]
        result = self.apply(f" Operador: {question.text} Llamante: No.", data=data)
        self.assertEqual(result.questions[1].status, "pending")
        self.assertEqual(result.questions[1].origin, "operator")
        self.assertTrue(result.review_notices)
        with self.assertRaises(ValidationError):
            ProtocolQuestion(id=question.id, text=question.text, status="pending", origin="operator")

    def test_manual_answer_is_not_overwritten_when_the_dialogue_differs(self):
        question = self.catalog.get("sfx-demo-001").questions[1]
        data = self.analysis.data.model_copy(deep=True)
        data.questions = [ProtocolQuestion(
            id=question.id, text=question.text, status="answered", answer="No.",
            origin="operator",
        )]
        result = self.apply(f" Operador: {question.text} Llamante: Sí.", data=data)
        self.assertEqual(result.questions[1].answer, "No.")
        self.assertIn(question.text, result.review_notices[0])
        matching = self.apply(f" Operador: {question.text} Llamante: No.", data=data)
        self.assertEqual(matching.review_notices, [])

    def test_http_exposes_catalog_apply_and_selection_errors(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            app = create_app()
        with TestClient(app) as client:
            options = client.get("/api/protocols", params={"category": "INCENDIO_RESCATE"})
            self.assertEqual(options.status_code, 200)
            self.assertEqual(sum(option["scope"] == "specific" for option in options.json()), 8)
            self.assertEqual(sum(option["scope"] == "general" for option in options.json()), 1)
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
