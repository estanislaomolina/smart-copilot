"""Salida reducida del modelo; los offsets y contratos públicos se construyen localmente."""
from typing import Literal, get_args

from pydantic import Field, ValidationInfo, model_validator
from backend.domain.models import Contract, Evidence, NonBlank, Category


class Quote(Contract):
    text: NonBlank = Field(description="Fragmento literal único del transcript; agregar contexto si se repite.")

    @model_validator(mode="after")
    def verify_source(self, info: ValidationInfo):
        if info.context and "transcript" in info.context:
            self.resolve(info.context["transcript"])
        return self

    def resolve(self, transcript: str) -> Evidence:
        start = transcript.find(self.text)
        if start < 0:
            raise ValueError("La cita literal no existe en la transcripción.")
        if transcript.find(self.text, start + 1) >= 0:
            raise ValueError("Cita repetida: incluir más contexto para identificar la evidencia.")
        return Evidence(text=self.text, start=start, end=start + len(self.text))

class UnknownField(Contract):
    value: None
    origin: Literal["unknown"]
    quotes: list[Quote] = Field(max_length=0)
    rationale: str | None


class ReportedField(Contract):
    value: NonBlank
    origin: Literal["transcript"]
    quotes: list[Quote] = Field(min_length=1)
    rationale: str | None


class InferredField(Contract):
    value: NonBlank
    origin: Literal["inference"]
    quotes: list[Quote] = Field(min_length=1)
    rationale: NonBlank


# anyOf en el esquema remoto: nunca ofrecer la combinación dato conocido + citas vacías.
ExtractedField = UnknownField | ReportedField | InferredField

class ExtractedLocation(Contract):
    street: ExtractedField
    number: ExtractedField
    intersection: ExtractedField = Field(description=(
        "Vía transversal mencionada como cruce o proximidad a un cruce con la calle principal. "
        "No exige que el incidente esté exactamente en la esquina; no es la localidad."))
    reference: ExtractedField
    district: ExtractedField



class ReportedCategory(ReportedField):
    value: Category


class InferredCategory(InferredField):
    value: Category



class ReportedRisk(ReportedField):
    value: NonBlank = Field(description="Fragmento literal de una cita; no una interpretación ni diagnóstico.")

    @model_validator(mode="after")
    def literal_report(self):
        if not any(self.value in quote.text for quote in self.quotes):
            raise ValueError("Una señal reportada debe ser literal. Las interpretaciones usan origin=inference.")
        return self


class ExtractedIncident(Contract):
    location: ExtractedLocation
    category: UnknownField | ReportedCategory | InferredCategory
    subcategory: ExtractedField
    risks: list[ReportedRisk | InferredField]
    summary: ExtractedField

    @model_validator(mode="after")
    def known_category(self):
        if self.category.value is not None and self.category.value not in get_args(Category):
            raise ValueError("Categoría fuera del contrato.")
        return self


class PendingQuestion(Contract):
    id: NonBlank
    status: Literal["pending"]
    answer: None
    quotes: list[Quote] = Field(max_length=0)
    rationale: None


class AnsweredQuestion(Contract):
    id: NonBlank
    status: Literal["answered"] = Field(description="La evidencia responde la condición exacta y completa.")
    answer: NonBlank
    quotes: list[Quote] = Field(min_length=1)
    rationale: str | None


class AmbiguousQuestion(Contract):
    id: NonBlank
    status: Literal["ambiguous"] = Field(description="Hay información relacionada pero falta confirmar la condición.")
    answer: str | None
    quotes: list[Quote] = Field(min_length=1)
    rationale: NonBlank


EvaluatedQuestion = PendingQuestion | AnsweredQuestion | AmbiguousQuestion

class EvaluatedChecklist(Contract):
    questions: list[EvaluatedQuestion]

    @model_validator(mode="after")
    def received_ids(self, info: ValidationInfo):
        if info.context and "questions" in info.context:
            expected = {q["id"] for q in info.context["questions"]}
            ids = [q.id for q in self.questions]
            if len(ids) != len(set(ids)) or set(ids) != expected:
                raise ValueError("Deben devolverse exactamente los IDs recibidos.")
        return self
