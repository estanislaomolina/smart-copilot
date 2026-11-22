"""Conversión común del LLM a contratos públicos; transporte independiente."""
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from backend.domain.models import AnalysisRequest, AnalysisResult, FieldValue, IncidentData, Location, ProtocolQuestion
from backend.protocols.evaluation import ChecklistEvaluationRequest, ChecklistEvaluationResult
from backend.providers.base import ProviderError
from backend.providers.config import ProviderSettings
from backend.providers.llm_models import ExtractedCategory, ExtractedField, ExtractedIncident, EvaluatedChecklist
from backend.providers.llm_prompts import EXTRACTION, CHECKLIST, PROMPT_VERSION

T = TypeVar("T", bound=BaseModel)


class StructuredGateway(Protocol):
    settings: ProviderSettings

    def complete(self, schema: type[T], system: str, payload: dict) -> T: ...


def field_from_output(field: ExtractedField | ExtractedCategory, transcript: str) -> FieldValue:
    return FieldValue(value=field.value, origin=field.origin,
                      evidence=[quote.resolve(transcript) for quote in field.quotes],
                      rationale=field.rationale)


class LLMExtractionProvider:
    name = "real"

    def __init__(self, gateway: StructuredGateway):
        self.gateway = gateway

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        output = await run_in_threadpool(self.gateway.complete, ExtractedIncident, EXTRACTION,
                                         {"transcript": request.transcript})
        try:
            location = Location.model_validate({
                key: field_from_output(field, request.transcript)
                for key, field in output.location
            })
            data = IncidentData.model_validate({
                "location": location,
                "category": field_from_output(output.category, request.transcript),
                "subcategory": field_from_output(output.subcategory, request.transcript),
                "summary": field_from_output(output.summary, request.transcript),
                "risks": [field_from_output(field, request.transcript) for field in output.risks],
            })
            return AnalysisResult(request=request, data=data, provider="real", model=self.gateway.settings.model,
                                  warnings=["Proveedor remoto: " + ("Groq" if self.gateway.settings.provider == "groq" else "Anthropic") + " · " + PROMPT_VERSION,
                                            "Interpretación no validada para uso operativo; revisar datos y riesgos.",
                                            "Prioridad sin asignación automática: requiere revisión del operador."])
        except (ValueError, ValidationError) as error:
            raise ProviderError("invalid_provider_output", "Extracción sin evidencia válida.") from error


class LLMChecklistEvaluator:
    def __init__(self, gateway: StructuredGateway):
        self.gateway = gateway

    def evaluate(self, request: ChecklistEvaluationRequest) -> ChecklistEvaluationResult:
        output = self.gateway.complete(EvaluatedChecklist, CHECKLIST, {
            "transcript": request.transcript,
            "questions": [{"id": q.id, "text": q.text, "answer_type": q.answer_type,
                           "follow_up": q.follow_up.text if q.follow_up else None}
                          for q in request.questions],
        })
        try:
            definitions = {q.id: q for q in request.questions}
            questions = []
            for result in output.questions:
                definition = definitions.get(result.id)
                if definition is None:
                    raise ValueError("ID ajeno al catálogo.")
                questions.append(ProtocolQuestion(
                    id=result.id, text=definition.text, status=result.status,
                    answer=result.answer, origin=None if result.status == "pending" else "transcript",
                    evidence=[quote.resolve(request.transcript) for quote in result.quotes],
                    rationale=result.rationale,
                    follow_up=definition.follow_up if result.status == "ambiguous" else None,
                ))
            evaluated = ChecklistEvaluationResult(questions=questions)
            evaluated.validate_against(request)
            return evaluated
        except (ValueError, ValidationError) as error:
            raise ProviderError("invalid_provider_output", "Checklist sin evidencia válida.") from error
