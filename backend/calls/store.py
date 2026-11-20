"""SQLite: snapshots, control de versión y comprobante idempotente local."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from backend.calls.models import (
    CallSnapshot, CallStoreError, CallSummary, ReferralReceipt, RevisionSummary, StoredCall,
)
from backend.domain.models import CallCard
from backend.protocols.catalog import ProtocolCatalog


class CallStore:
    def __init__(self, path: Path, catalog: ProtocolCatalog):
        self.path = path
        self.catalog = catalog
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    call_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    event TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (call_id, revision)
                );
                CREATE TABLE IF NOT EXISTS referrals (
                    call_id TEXT NOT NULL, reviewed_revision INTEGER NOT NULL,
                    receipt TEXT NOT NULL,
                    PRIMARY KEY (call_id, reviewed_revision)
                );
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def _read(self, db, call_id: UUID) -> StoredCall | None:
        row = db.execute("SELECT payload FROM calls WHERE id=?", (str(call_id),)).fetchone()
        return StoredCall.model_validate_json(row[0]) if row else None

    def _write(self, db, item: StoredCall, event: str) -> StoredCall:
        payload = item.model_dump_json()
        key, revision, timestamp = str(item.card.id), item.card.revision, item.updated_at.isoformat()
        db.execute("INSERT INTO calls VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                   "revision=excluded.revision,payload=excluded.payload,updated_at=excluded.updated_at",
                   (key, revision, payload, timestamp))
        db.execute("INSERT INTO revisions VALUES (?,?,?,?,?)", (key, revision, event, payload, timestamp))
        return item

    def get(self, call_id: UUID) -> StoredCall:
        with closing(self.connect()) as db:
            item = self._read(db, call_id)
        if item is None:
            raise CallStoreError("call_not_found")
        return item

    def list_calls(self) -> list[CallSummary]:
        with closing(self.connect()) as db:
            rows = db.execute("SELECT payload FROM calls ORDER BY updated_at DESC LIMIT 50").fetchall()
        items = [StoredCall.model_validate_json(row[0]) for row in rows]
        return [CallSummary(id=item.card.id, revision=item.card.revision, status=item.card.status,
                            updated_at=item.updated_at, category=item.card.data.category.value,
                            priority=item.card.data.priority.value) for item in items]

    def history(self, call_id: UUID) -> list[RevisionSummary]:
        self.get(call_id)
        with closing(self.connect()) as db:
            rows = db.execute("SELECT revision,event,created_at FROM revisions WHERE call_id=? "
                              "ORDER BY revision DESC LIMIT 100", (str(call_id),)).fetchall()
        return [RevisionSummary(revision=row[0], event=row[1], created_at=row[2]) for row in rows]

    def _validate_catalog(self, snapshot: CallSnapshot) -> CallSnapshot:
        snapshot = snapshot.model_copy(deep=True)
        protocol = snapshot.context.protocol
        if protocol and protocol.protocol:
            definition = self.catalog.get(protocol.protocol.id)
            if (protocol.protocol != definition.summary()
                    or (snapshot.data.category.value is not None
                        and definition.category != snapshot.data.category.value)):
                raise CallStoreError("invalid_call")
            expected = {question.id: question for question in definition.questions}
            if len(snapshot.data.questions) != len(expected):
                raise CallStoreError("invalid_call")
            for question in snapshot.data.questions:
                entry = expected.get(question.id)
                if (entry is None or entry.text != question.text
                        or (question.follow_up is not None and question.follow_up != entry.follow_up)):
                    raise CallStoreError("invalid_call")
            # Las instrucciones persistidas proceden del catálogo, no del cliente.
            protocol.instructions = [item.model_copy(deep=True) for item in definition.instructions]
            protocol.candidates = self.catalog.summaries(snapshot.data.category.value)
        elif protocol:
            protocol.instructions = []
            protocol.candidates = self.catalog.summaries(snapshot.data.category.value)
        if snapshot.context.question_update:
            update = snapshot.context.question_update
            questions = protocol.questions if protocol else []
            if update.number > len(questions) or questions[update.number - 1].id != update.id:
                raise CallStoreError("invalid_call")
        if snapshot.context.prepared_question:
            prepared = snapshot.context.prepared_question
            if protocol is None or protocol.protocol is None or prepared.protocol_id != protocol.protocol.id:
                raise CallStoreError("invalid_call")
            questions = protocol.questions
            if (prepared.number > len(questions) or questions[prepared.number - 1].id != prepared.id
                    or prepared.prompt not in (questions[prepared.number - 1].text,
                                              getattr(questions[prepared.number - 1].follow_up, "text", None))):
                raise CallStoreError("invalid_call")
        return snapshot

    def save(self, call_id: UUID, snapshot: CallSnapshot, expected_revision: int) -> StoredCall:
        snapshot = self._validate_catalog(snapshot)
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = self._read(db, call_id)
            # Reintentar un guardado idéntico no invalida la revisión ni duplica versiones.
            if old and old.snapshot() == snapshot:
                return old
            if (old.card.revision if old else 0) != expected_revision:
                raise CallStoreError("revision_conflict")
            now = datetime.now(timezone.utc)
            card = CallCard(
                id=call_id, revision=old.card.revision + 1 if old else 1, status="draft",
                request=snapshot.request, data=snapshot.data,
                instructions=snapshot.context.protocol.instructions if snapshot.context.protocol else [],
                operator_notes=snapshot.operator_notes, created_at=old.card.created_at if old else now,
            )
            item = StoredCall(card=card, context=snapshot.context, updated_at=now)
            return self._write(db, item, "saved")

    def transition(self, call_id: UUID, expected_revision: int, action: str) -> StoredCall:
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = self._read(db, call_id)
            if old is None:
                raise CallStoreError("call_not_found")
            if action == "refer" and old.card.status == "referred" and old.referral:
                if expected_revision in (old.card.revision, old.referral.reviewed_revision):
                    return old
            if action == "review" and old.card.status == "reviewed":
                if expected_revision in (old.card.revision, old.card.revision - 1):
                    return old
            if old.card.revision != expected_revision:
                raise CallStoreError("revision_conflict")
            now = datetime.now(timezone.utc)
            values = old.card.model_dump()
            values["revision"] += 1
            if action == "review":
                if old.context.operator_turn.strip() or old.context.caller_turn.strip():
                    raise CallStoreError("invalid_call")
                if old.card.status != "draft":
                    raise CallStoreError("review_required")
                values.update(status="reviewed", reviewed_at=now, referred_at=None)
                receipt = None
            else:
                if old.card.status != "reviewed":
                    raise CallStoreError("review_required")
                receipt = ReferralReceipt(id="SIM-CAD-" + str(uuid4()), reviewed_revision=old.card.revision,
                                          created_at=now)
                db.execute("INSERT INTO referrals VALUES (?,?,?)",
                           (str(call_id), old.card.revision, receipt.model_dump_json()))
                values.update(status="referred", referred_at=now)
            item = StoredCall(card=CallCard.model_validate(values), context=old.context,
                              updated_at=now, referral=receipt)
            return self._write(db, item, "reviewed" if action == "review" else "referred")
