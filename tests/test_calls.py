"""Persistencia real en SQLite temporal; versiones, revisión y reintentos HTTP."""
import copy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.providers.base import ProviderError


class CallWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "calls.sqlite3"
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            self.client = TestClient(create_app(db_path=self.db))
        self.addCleanup(self.client.close)
        self.id = str(uuid4())
        self.url = "/api/calls/" + self.id
        text = "Llamante: Hay fuego en Av. Corrientes 1540."
        analysis = self.client.post("/api/analyze", json={"transcript": text}).json()
        protocol = self.client.post("/api/protocols/apply", json={
            "request": analysis["request"], "data": analysis["data"],
        }).json()
        data = copy.deepcopy(analysis["data"])
        data["questions"] = protocol["questions"]
        data["priority"] = {"value": "P2", "origin": "operator", "evidence": [],
                            "rationale": "Corrección del operador de demostración."}
        question = data["questions"][0]
        question.update(status="answered", answer="Respuesta revisada", origin="operator",
                        evidence=[], rationale="Confirmado durante la llamada.")
        protocol["questions"] = copy.deepcopy(data["questions"])
        self.snapshot = {"request": analysis["request"], "data": data,
                         "operator_notes": "Observación de prueba",
                         "context": {"analysis": analysis, "manual_mode": False, "protocol": protocol,
                                     "manual_fields": ["priority"], "operator_turn": "",
                                     "caller_turn": "", "prepared_question": None,
                                     "question_update": None, "update_notices": []}}

    def save(self, snapshot=None, revision=0):
        return self.client.put(self.url, json={
            "expected_revision": revision, "snapshot": snapshot or self.snapshot})

    def transition(self, action, revision):
        return self.client.post(self.url + "/" + action, json={
            "expected_revision": revision, "acknowledged": True})

    def test_restart_recovers_all_state_and_history(self):
        self.snapshot["context"]["manual_fields"] += [
            "location.street", "location.number", "location.intersection", "location.reference", "location.district",
        ]
        self.snapshot["data"]["location"]["number"] = {
            "value": "1600", "origin": "operator", "evidence": [], "rationale": "Altura corregida.",
        }
        self.snapshot["data"]["location"]["street"] = {
            "value": None, "origin": "unknown", "evidence": [], "rationale": None,
        }
        self.snapshot["context"]["caller_turn"] = "Turno todavía sin incorporar"
        saved = self.save()
        self.assertEqual(saved.status_code, 200, saved.text)
        item = saved.json()
        with patch.dict(os.environ, {"LLM_PROVIDER": "mock"}):
            with TestClient(create_app(db_path=self.db)) as restarted:
                recovered = restarted.get(self.url).json()
                self.assertEqual(recovered, item)
                self.assertEqual(restarted.get("/api/calls").json()[0]["id"], self.id)
        self.assertEqual(item["card"]["data"], self.snapshot["data"])
        self.assertEqual(item["context"], self.snapshot["context"])
        self.assertEqual(self.client.get(self.url + "/revisions").json()[0]["event"], "saved")

    def test_call_workflow_does_not_depend_on_groq_availability(self):
        class FailingGateway:
            settings = None

            def complete(self, *_args, **_kwargs):
                raise ProviderError("provider_unavailable", "Proveedor caído")

            def close(self):
                pass

        self.assertEqual(self.save().status_code, 200)  # Revisión 1: estado inicial para operar.
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "clave-local-falsa"}), \
                patch("backend.main.GroqGateway", return_value=FailingGateway()):
            with TestClient(create_app(db_path=self.db)) as client:
                failed = client.post("/api/analyze", json={"transcript": "Llamante: Hay fuego en Av. Corrientes 1540."})
                self.assertEqual(failed.status_code, 503)
                self.assertEqual(failed.json()["code"], "provider_unavailable")
                # Listado e historial también durante la caída, no solo antes.
                self.assertEqual(client.get("/api/calls").status_code, 200)
                self.assertEqual(client.get(self.url + "/revisions").status_code, 200)
                # Guardado con la revisión vigente, antes de revisar y derivar.
                edited = copy.deepcopy(self.snapshot)
                edited["operator_notes"] = "Nota guardada durante la caída de Groq"
                saved = client.put(self.url, json={"expected_revision": 1, "snapshot": edited})
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertEqual(saved.json()["card"]["revision"], 2)
                reviewed = client.post(self.url + "/review", json={
                    "expected_revision": 2, "acknowledged": True})
                self.assertEqual(reviewed.status_code, 200, reviewed.text)
                referred = client.post(self.url + "/refer", json={
                    "expected_revision": 3, "acknowledged": True})
                self.assertEqual(referred.status_code, 200, referred.text)
                recovered = client.get(self.url).json()
                self.assertEqual(recovered["card"]["data"]["priority"]["origin"], "operator")
                self.assertEqual(recovered["card"]["status"], "referred")
                self.assertEqual(recovered["card"]["operator_notes"], edited["operator_notes"])
                self.assertTrue(recovered["referral"]["id"].startswith("SIM-CAD-"))
                self.assertEqual([item["event"] for item in client.get(self.url + "/revisions").json()],
                                 ["referred", "reviewed", "saved", "saved"])
                self.assertEqual(client.get("/api/calls").json()[0]["id"], self.id)

    def test_review_and_referral_are_explicit_and_idempotent(self):
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.transition("refer", 1).status_code, 409)
        denied = self.client.post(self.url + "/review", json={
            "expected_revision": 1, "acknowledged": False})
        self.assertEqual(denied.status_code, 422)
        reviewed = self.transition("review", 1).json()
        self.assertEqual(reviewed["card"]["status"], "reviewed")
        self.assertEqual(reviewed["card"]["data"]["priority"]["origin"], "operator")
        # Revisar la carta no convierte otras sugerencias en confirmaciones.
        self.assertEqual(reviewed["card"]["data"]["category"]["origin"],
                         self.snapshot["data"]["category"]["origin"])
        self.assertEqual(self.transition("review", 1).json(), reviewed)
        self.assertEqual(self.save(revision=1).json(), reviewed)
        referred = self.transition("refer", 2).json()
        self.assertEqual(referred["card"]["status"], "referred")
        self.assertEqual(referred["referral"]["mode"], "simulation")
        self.assertTrue(referred["referral"]["id"].startswith("SIM-CAD-"))
        self.assertEqual(self.transition("refer", 2).json(), referred)
        self.assertEqual(self.transition("refer", 3).json(), referred)
        self.assertEqual(len(self.client.get(self.url + "/revisions").json()), 3)

    def test_edit_invalidates_review_and_conflicting_writer_cannot_overwrite(self):
        self.save()
        self.transition("review", 1)
        previous = self.transition("refer", 2).json()
        changed = copy.deepcopy(self.snapshot)
        changed["operator_notes"] = "Corrección posterior"
        self.assertEqual(self.save(changed, revision=1).status_code, 409)
        self.assertEqual(self.client.get(self.url).json(), previous)
        draft = self.save(changed, revision=3).json()
        self.assertEqual(draft["card"]["status"], "draft")
        self.assertIsNone(draft["card"]["reviewed_at"])
        self.assertIsNone(draft["card"]["referred_at"])
        self.assertIsNone(draft["referral"])
        self.assertEqual(self.transition("refer", 4).status_code, 409)
        self.transition("review", 4)
        again = self.transition("refer", 5).json()
        self.assertNotEqual(again["referral"]["id"], previous["referral"]["id"])
        events = self.client.get(self.url + "/revisions").json()
        self.assertEqual([event["event"] for event in events],
                         ["referred", "reviewed", "saved", "referred", "reviewed", "saved"])

    def test_unsent_turns_evidence_and_catalog_are_checked(self):
        invalid = copy.deepcopy(self.snapshot)
        invalid["data"]["location"]["street"]["evidence"][0]["text"] = "Inventado"
        self.assertEqual(self.save(invalid).status_code, 422)
        invalid = copy.deepcopy(self.snapshot)
        invalid["context"]["protocol"]["questions"][0]["text"] = "Pregunta inventada"
        invalid["data"]["questions"][0]["text"] = "Pregunta inventada"
        self.assertEqual(self.save(invalid).status_code, 422)
        tampered = copy.deepcopy(self.snapshot)
        tampered["context"]["protocol"]["instructions"][0]["text"] = "Instrucción ajena"
        stored = self.save(tampered).json()
        self.assertEqual(stored["card"]["instructions"],
                         self.snapshot["context"]["protocol"]["instructions"])
        changed = copy.deepcopy(self.snapshot)
        changed["context"]["caller_turn"] = "Hay información nueva"
        self.assertEqual(self.save(changed, 1).status_code, 200)
        self.assertEqual(self.transition("review", 2).status_code, 422)
        self.assertEqual(self.client.get(self.url).json()["card"]["status"], "draft")

    def test_missing_call_and_invalid_followup_reference(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.url + "/revisions").status_code, 404)
        changed = copy.deepcopy(self.snapshot)
        changed["context"]["prepared_question"] = {
            "id": "inventado", "protocol_id": changed["context"]["protocol"]["protocol"]["id"],
            "prompt": "Texto sin autorización", "number": 1, "stage": "prepared"}
        self.assertEqual(self.save(changed).status_code, 422)


if __name__ == "__main__":
    unittest.main()
