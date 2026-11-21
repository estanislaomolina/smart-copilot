"""Contenido editable y metadatos controlados por el servidor."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from backend.domain.models import AnalysisRequest, AnalysisResult, CallCard, Contract, IncidentData, NonBlank
from backend.protocols.models import ProtocolResult


class PreparedQuestionState(Contract):
    id: NonBlank
    protocol_id: NonBlank
    prompt: NonBlank
    number: int = Field(ge=1)
    stage: Literal["prepared", "awaiting_reply"]


class QuestionUpdateState(Contract):
    id: NonBlank
    number: int = Field(ge=1)


class CallContext(Contract):
    analysis: AnalysisResult | None = None
    manual_mode: bool = False
    protocol: ProtocolResult | None = None
    manual_fields: list[Literal[
        "category", "priority", "location.street", "location.number",
        "location.intersection", "location.reference", "location.district",
    ]] = Field(default_factory=list)
    operator_turn: str = Field(default="", max_length=50_000)
    caller_turn: str = Field(default="", max_length=50_000)
    prepared_question: PreparedQuestionState | None = None
    question_update: QuestionUpdateState | None = None
    update_notices: list[NonBlank] = Field(default_factory=list)


class CallSnapshot(Contract):
    request: AnalysisRequest
    data: IncidentData
    operator_notes: str = Field(default="", max_length=10_000)
    context: CallContext = Field(default_factory=CallContext)

    @model_validator(mode="after")
    def check_consistency(self):
        self.data.validate_transcript(self.request.transcript, allow_operator=True)
        if self.context.analysis and self.context.analysis.request != self.request:
            raise ValueError("El análisis debe corresponder a la conversación guardada.")
        protocol = self.context.protocol
        if protocol is not None and protocol.questions != self.data.questions:
            raise ValueError("La carta y el checklist deben compartir las mismas preguntas.")
        if (protocol is None or protocol.protocol is None) and self.data.questions:
            raise ValueError("No hay preguntas sin un protocolo aplicado.")
        return self


class SaveCallRequest(Contract):
    expected_revision: int = Field(ge=0, strict=True)
    snapshot: CallSnapshot


class TransitionRequest(Contract):
    expected_revision: int = Field(ge=1, strict=True)
    acknowledged: Literal[True]


class ReferralReceipt(Contract):
    id: NonBlank
    mode: Literal["simulation"] = "simulation"
    destination: Literal["CAD simulado"] = "CAD simulado"
    reviewed_revision: int
    created_at: datetime


class StoredCall(Contract):
    card: CallCard
    context: CallContext
    updated_at: datetime
    referral: ReferralReceipt | None = None

    def snapshot(self) -> CallSnapshot:
        return CallSnapshot(request=self.card.request, data=self.card.data,
                            operator_notes=self.card.operator_notes, context=self.context)


class CallSummary(Contract):
    id: UUID
    revision: int
    status: Literal["draft", "reviewed", "referred"]
    updated_at: datetime
    category: str | None
    priority: str | None


class RevisionSummary(Contract):
    revision: int
    event: Literal["saved", "reviewed", "referred"]
    created_at: datetime


class CallStoreError(Exception):
    def __init__(self, code: Literal["call_not_found", "revision_conflict", "review_required", "invalid_call"]):
        self.code = code
        super().__init__(code)
