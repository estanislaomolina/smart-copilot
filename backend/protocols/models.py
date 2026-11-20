"""Contratos del catálogo y su aplicación a los datos revisables de una llamada."""

from typing import Literal

from pydantic import Field, model_validator

from backend.domain.models import (
    AnalysisRequest, Category, Contract, IncidentData, NonBlank,
    FollowUpQuestion, PrearrivalInstruction, ProtocolQuestion,
)


class QuestionDefinition(Contract):
    id: NonBlank
    text: NonBlank
    answer_type: Literal["yes_no", "free_text"]
    follow_up: FollowUpQuestion | None = None


class FollowUpEntry(Contract):
    question_text: NonBlank
    follow_up: FollowUpQuestion


class FollowUpCatalog(Contract):
    entries: list[FollowUpEntry]


class ProtocolSummary(Contract):
    scope: Literal["general", "specific"] = "specific"
    id: NonBlank
    version: NonBlank
    category: Category
    subcategory: NonBlank
    review_status: Literal["demo_unverified"]


class ProtocolDefinition(ProtocolSummary):
    source_record: NonBlank
    questions: list[QuestionDefinition]
    instructions: list[PrearrivalInstruction]

    @model_validator(mode="after")
    def unique_questions(self) -> "ProtocolDefinition":
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("El protocolo contiene preguntas duplicadas.")
        return self

    def summary(self) -> ProtocolSummary:
        return ProtocolSummary(**self.model_dump(include=set(ProtocolSummary.model_fields)))


class CatalogFile(Contract):
    version: NonBlank
    source_file: NonBlank
    protocols: list[ProtocolDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_protocols(self) -> "CatalogFile":
        ids = [protocol.id for protocol in self.protocols]
        if len(ids) != len(set(ids)):
            raise ValueError("El catálogo contiene protocolos duplicados.")
        return self


class ProtocolRequest(Contract):
    request: AnalysisRequest
    data: IncidentData
    protocol_id: NonBlank | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "ProtocolRequest":
        self.data.validate_transcript(self.request.transcript, allow_operator=True)
        return self


class ProtocolResult(Contract):
    selection: Literal["pending", "general", "suggested", "selected"]
    selection_origin: Literal["category", "subcategory", "operator"] | None = None
    protocol: ProtocolSummary | None = None
    candidates: list[ProtocolSummary] = Field(default_factory=list)
    questions: list[ProtocolQuestion] = Field(default_factory=list)
    instructions: list[PrearrivalInstruction] = Field(default_factory=list)
    warnings: list[NonBlank] = Field(default_factory=list)
    review_notices: list[NonBlank] = Field(default_factory=list)


class ProtocolError(Exception):
    def __init__(self, code: Literal["protocol_not_found", "protocol_category_mismatch"]):
        self.code = code
        super().__init__(code)
