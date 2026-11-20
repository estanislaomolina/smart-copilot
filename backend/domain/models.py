"""Contratos iniciales: evidencia textual, sugerencias y revisión humana."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Priority = Literal["P1", "P2", "P3", "P4"]
Category = Literal[
    "INCENDIO_RESCATE", "ACCIDENTE_VIAL", "EMERGENCIA_MEDICA",
    "DEFENSA_CIVIL", "SERVICIOS_PUBLICOS", "CONVIVENCIA_SEGURIDAD",
]
T = TypeVar("T")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Contract):
    """Offsets de caracteres Python sobre el texto original; end es exclusivo."""

    text: NonBlank
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)

    @model_validator(mode="after")
    def check_length(self) -> Evidence:
        if self.end - self.start != len(self.text):
            raise ValueError("Los offsets deben coincidir con la longitud de la evidencia.")
        return self


class FieldValue(Contract, Generic[T]):
    value: T | None = None
    origin: Literal["unknown", "transcript", "inference", "operator"] = "unknown"
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: NonBlank | None = None

    @model_validator(mode="after")
    def check_origin(self) -> FieldValue[T]:
        if self.origin == "unknown":
            if self.value is not None or self.evidence:
                raise ValueError("Un dato desconocido no tiene valor ni evidencia.")
        else:
            if self.value is None:
                raise ValueError("Un dato conocido requiere un valor.")
            if self.origin in ("transcript", "inference") and not self.evidence:
                raise ValueError("Extracciones e inferencias requieren evidencia.")
            if self.origin == "inference" and not self.rationale:
                raise ValueError("Una inferencia requiere justificación.")
        return self


class Location(Contract):
    # Altura admite texto: S/N, kilómetro o un número normalizado, sin inventar datos.
    street: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    number: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    intersection: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    reference: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    district: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])


class FollowUpQuestion(Contract):
    id: NonBlank
    text: NonBlank
    version: NonBlank
    source: NonBlank
    review_status: Literal["demo_unverified"] = "demo_unverified"


class ProtocolQuestion(Contract):
    id: NonBlank
    text: NonBlank
    status: Literal["pending", "answered", "ambiguous", "not_applicable"] = "pending"
    follow_up: FollowUpQuestion | None = None
    answer: NonBlank | None = None
    origin: Literal["transcript", "operator"] | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: NonBlank | None = None

    @model_validator(mode="after")
    def check_state(self) -> ProtocolQuestion:
        if self.status == "pending":
            if self.answer is not None or self.origin not in (None, "operator") or self.evidence:
                raise ValueError("Una pregunta pendiente no tiene respuesta ni evidencia.")
            if self.origin == "operator" and not self.rationale:
                raise ValueError("Reabrir una pregunta requiere justificación del operador.")
        else:
            if self.origin is None:
                raise ValueError("Un estado resuelto o ambiguo requiere procedencia.")
            if self.origin == "transcript" and not self.evidence:
                raise ValueError("Una respuesta del relato requiere evidencia.")
            if self.status == "answered" and self.answer is None:
                raise ValueError("Una pregunta respondida requiere respuesta, incluso negativa.")
            if self.status in ("ambiguous", "not_applicable") and not self.rationale:
                raise ValueError("Ambigüedad y no aplicabilidad requieren justificación.")
        return self


class IncidentData(Contract):
    location: Location = Field(default_factory=Location)
    category: FieldValue[Category] = Field(default_factory=FieldValue[Category])
    subcategory: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    priority: FieldValue[Priority] = Field(default_factory=FieldValue[Priority])
    risks: list[FieldValue[NonBlank]] = Field(default_factory=list)
    summary: FieldValue[NonBlank] = Field(default_factory=FieldValue[NonBlank])
    questions: list[ProtocolQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_question_ids(self) -> IncidentData:
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Los identificadores de preguntas deben ser únicos.")
        return self

    def fields(self) -> list[FieldValue]:
        return [
            self.location.street, self.location.number, self.location.intersection,
            self.location.reference, self.location.district, self.category,
            self.subcategory, self.priority, self.summary, *self.risks,
        ]

    def validate_transcript(self, transcript: str, *, allow_operator: bool) -> None:
        for item in [*self.fields(), *self.questions]:
            if not allow_operator and item.origin == "operator":
                raise ValueError("Un proveedor no puede atribuir datos al operador.")
            for span in item.evidence:
                if transcript[span.start:span.end] != span.text:
                    raise ValueError("La evidencia no coincide con el texto original.")


class AnalysisRequest(Contract):
    # No recortar ni normalizar este texto: invalidaría los offsets de evidencia.
    transcript: NonBlank = Field(max_length=50_000)


class AnalysisResult(Contract):
    request: AnalysisRequest
    data: IncidentData
    provider: Literal["mock", "real"]
    model: NonBlank | None = None
    warnings: list[NonBlank] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_evidence(self) -> AnalysisResult:
        self.data.validate_transcript(self.request.transcript, allow_operator=False)
        return self


class PrearrivalInstruction(Contract):
    """Contenido de catálogo, no texto libre generado por el proveedor."""

    id: NonBlank
    protocol_id: NonBlank
    protocol_version: NonBlank
    text: NonBlank
    source: NonBlank
    review_status: Literal["demo_unverified", "reviewed"] = "demo_unverified"


class CallCard(Contract):
    id: UUID = Field(default_factory=uuid4)
    revision: int = Field(default=1, ge=1, strict=True)
    status: Literal["draft", "reviewed", "referred"] = "draft"
    request: AnalysisRequest
    data: IncidentData
    instructions: list[PrearrivalInstruction] = Field(default_factory=list)
    operator_notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = None
    referred_at: datetime | None = None

    @model_validator(mode="after")
    def check_review(self) -> CallCard:
        self.data.validate_transcript(self.request.transcript, allow_operator=True)
        for timestamp in (self.created_at, self.reviewed_at, self.referred_at):
            if timestamp is not None and timestamp.utcoffset() is None:
                raise ValueError("Las fechas de la carta requieren zona horaria.")
        if self.status == "draft" and (self.reviewed_at or self.referred_at):
            raise ValueError("Un borrador no tiene fechas de revisión o derivación.")
        if self.status in ("reviewed", "referred") and self.reviewed_at is None:
            raise ValueError("La carta requiere revisión humana antes de derivarse.")
        if self.reviewed_at and self.reviewed_at < self.created_at:
            raise ValueError("La revisión no puede ser anterior a la creación.")
        if self.status == "reviewed" and self.referred_at is not None:
            raise ValueError("Una carta revisada aún no tiene fecha de derivación.")
        if self.status == "referred":
            if self.referred_at is None or self.referred_at < self.reviewed_at:
                raise ValueError("La derivación requiere una fecha posterior a la revisión.")
        return self


class ErrorResponse(Contract):
    code: Literal[
        "invalid_input", "provider_unavailable", "provider_timeout",
        "invalid_provider_output", "unsupported_provider",
        "protocol_not_found", "protocol_category_mismatch",
        "call_not_found", "revision_conflict", "review_required", "invalid_call",
    ]
    message: NonBlank
    retryable: bool = False


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    stage: Literal["mock_analysis"] = "mock_analysis"
    configured_provider: Literal["mock"] = "mock"
