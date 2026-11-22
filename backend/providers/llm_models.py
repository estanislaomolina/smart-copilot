"""Salida reducida del modelo; los offsets y contratos públicos se construyen localmente."""
from typing import Literal, get_args

from pydantic import Field, PrivateAttr, TypeAdapter, ValidationError, ValidationInfo, model_validator
from pydantic_core import PydanticCustomError
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
            raise PydanticCustomError("evidence_not_found", "La cita literal no existe en la transcripción.")
        if transcript.find(self.text, start + 1) >= 0:
            raise PydanticCustomError("evidence_not_unique", "Cita repetida: incluir más contexto para identificar la evidencia.")
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
    street: ExtractedField = Field(description="Vía principal sustentada por el contexto de dirección; desconocida si el tipo del nombre no se puede determinar.")
    number: ExtractedField
    intersection: ExtractedField = Field(description=(
        "Vía transversal mencionada como cruce o proximidad a un cruce con la calle principal. "
        "No exige que el incidente esté exactamente en la esquina; no es la localidad."))
    reference: ExtractedField = Field(description="Referencia o nombre de ubicación sin tipo determinado. Preservar el nombre ambiguo sin asignarlo a calle o localidad.")
    district: ExtractedField = Field(description="Localidad o municipio identificado como tal en el relato. Un topónimo aislado no confirma localidad.")



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


class ExtractedCategory(Contract):
    """Una sola forma remota; las mismas invariantes de estado se verifican localmente."""
    value: Category | None
    origin: Literal["unknown", "transcript", "inference"]
    quotes: list[Quote]
    rationale: str | None

    @model_validator(mode="after")
    def validate_state(self, info: ValidationInfo):
        # Evitar tres objetos anyOf casi idénticos en el decodificador remoto.
        # Se conservan enum, nulabilidad y toda la validación previa de citas/procedencia.
        TypeAdapter(UnknownField | ReportedCategory | InferredCategory).validate_python(
            self.model_dump(), context=info.context)
        return self


class ExtractedIncident(Contract):
    location: ExtractedLocation
    category: ExtractedCategory
    subcategory: ExtractedField
    risks: list[ReportedRisk | InferredField]
    summary: ExtractedField
    questions: list["EvaluatedQuestion"] = Field(default_factory=list)
    _discarded: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="wrap")
    @classmethod
    def preserve_valid_fields(cls, raw, handler, info: ValidationInfo):
        try:
            return handler(raw)
        except ValidationError as original:
            required = {"location", "category", "subcategory", "risks", "summary"}
            if (not isinstance(raw, dict) or not required <= raw.keys()
                    or raw.keys() - cls.model_fields.keys()
                    or not isinstance(raw["location"], dict)
                    or set(raw["location"]) != set(ExtractedLocation.model_fields)
                    or not isinstance(raw["risks"], list)
                    or not isinstance(raw.get("questions", []), list)):
                raise original
            clean = dict(raw)
            discarded = []
            unknown = {"value": None, "origin": "unknown", "quotes": [], "rationale": None}

            def check(value, kind, path, fallback):
                try:
                    return TypeAdapter(kind).validate_python(value, context=info.context).model_dump()
                except ValidationError:
                    discarded.append(path)
                    return fallback

            clean["location"] = {key: check(value, ExtractedField, "location." + key, unknown)
                                 for key, value in raw["location"].items()}
            for key, kind in (("category", ExtractedCategory), ("subcategory", ExtractedField),
                              ("summary", ExtractedField)):
                clean[key] = check(raw[key], kind, key, unknown)
            clean["risks"] = [value for index, item in enumerate(raw["risks"])
                              if (value := check(item, ReportedRisk | InferredField,
                                                 f"risks[{index}]", None)) is not None]
            clean["questions"] = [value for index, item in enumerate(raw.get("questions", []))
                                  if (value := check(item, EvaluatedQuestion,
                                                     f"questions[{index}]", None)) is not None]
            result = handler(clean)
            fields = [*(field for _, field in result.location), result.category,
                      result.subcategory, result.summary, *result.risks]
            if discarded and not any(field.value is not None for field in fields):
                raise original
            result._discarded = discarded
            return result

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


ExtractedIncident.model_rebuild()
