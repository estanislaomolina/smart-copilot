"""Conversión común del LLM a contratos públicos; transporte independiente."""
from typing import Protocol, TypeVar
from collections import OrderedDict
from hashlib import sha256
from threading import Lock

from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from backend.domain.models import AnalysisRequest, AnalysisResult, FieldValue, IncidentData, Location, ProtocolQuestion
from backend.protocols.evaluation import ChecklistEvaluationRequest, ChecklistEvaluationResult
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.models import QuestionDefinition
from backend.providers.base import ProviderError
from backend.providers.config import ProviderSettings
from backend.providers.llm_models import ExtractedCategory, ExtractedField, ExtractedIncident, EvaluatedChecklist, EvaluatedQuestion
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

    def __init__(self, gateway: StructuredGateway, checklist: "LLMChecklistEvaluator | None" = None):
        self.gateway = gateway
        self.checklist = checklist
        self.questions: list[QuestionDefinition] = []
        if checklist is not None:
            catalog = ProtocolCatalog()
            self.questions = list({q.id: q for protocol in catalog.general_by_category.values()
                                   for q in protocol.questions}.values())

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        payload = {"transcript": request.transcript}
        if self.checklist is not None:
            payload["questions"] = question_payload(self.questions)
        output = await run_in_threadpool(self.gateway.complete, ExtractedIncident, EXTRACTION, payload)
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
            result = AnalysisResult(request=request, data=data, provider="real", model=self.gateway.settings.model,
                                  warnings=["Proveedor remoto: " + ("Groq" if self.gateway.settings.provider == "groq" else "Anthropic") + " · " + PROMPT_VERSION,
                                            "Interpretación no validada para uso operativo; revisar datos y riesgos.",
                                            "Prioridad sin asignación automática: requiere revisión del operador."])
            if output._discarded:
                result.warnings.append("Análisis parcial: datos inválidos descartados; revisar: "
                                       + ", ".join(output._discarded) + ".")
            if self.checklist is not None:
                if not self.checklist.remember(request.transcript, self.questions, output.questions):
                    result.warnings.append("Análisis parcial: respuestas con IDs ajenos o repetidos descartadas; "
                                           "el checklist se evaluará por separado.")
            return result
        except (ValueError, ValidationError) as error:
            raise ProviderError("invalid_provider_output", "Extracción sin evidencia válida.") from error


def question_payload(questions: list[QuestionDefinition]) -> list[dict]:
    return [{"id": q.id, "text": q.text, "answer_type": q.answer_type,
             "follow_up": q.follow_up.text if q.follow_up else None} for q in questions]


class LLMChecklistEvaluator:
    def __init__(self, gateway: StructuredGateway):
        self.gateway = gateway
        # Bounded, process-local facts: never reuse across a transcript change.
        self._facts: OrderedDict[tuple[str, str], ProtocolQuestion] = OrderedDict()
        self._lock = Lock()

    def _key(self, transcript: str, question: QuestionDefinition) -> tuple[str, str]:
        return (sha256(transcript.encode()).hexdigest(), question.model_dump_json())

    def remember(self, transcript: str, definitions: list[QuestionDefinition],
                 results: list[EvaluatedQuestion]) -> bool:
        by_id = {q.id: q for q in definitions}
        ids = [q.id for q in results]
        if len(ids) != len(set(ids)) or set(ids) - by_id.keys():
            return False  # Unknown/duplicate IDs never populate trusted facts.
        entries = []
        for result in results:
            definition = by_id[result.id]
            question = self._convert(result, definition, transcript)
            check = ChecklistEvaluationResult(questions=[question])
            check.validate_against(ChecklistEvaluationRequest(transcript=transcript, questions=[definition]))
            entries.append((self._key(transcript, definition), question))
        with self._lock:
            for key, question in entries:
                self._facts[key] = question.model_copy(deep=True)
                self._facts.move_to_end(key)
            while len(self._facts) > 256:
                self._facts.popitem(last=False)
        return True

    @staticmethod
    def _convert(result: EvaluatedQuestion, definition: QuestionDefinition,
                 transcript: str) -> ProtocolQuestion:
        return ProtocolQuestion(
            id=result.id, text=definition.text, status=result.status,
            answer=result.answer, origin=None if result.status == "pending" else "transcript",
            evidence=[quote.resolve(transcript) for quote in result.quotes],
            rationale=result.rationale,
            follow_up=definition.follow_up if result.status == "ambiguous" else None,
        )

    def evaluate(self, request: ChecklistEvaluationRequest) -> ChecklistEvaluationResult:
        with self._lock:
            known = {q.id: self._facts[self._key(request.transcript, q)].model_copy(deep=True)
                     for q in request.questions if self._key(request.transcript, q) in self._facts}
        missing = [q for q in request.questions if q.id not in known]
        output = self.gateway.complete(EvaluatedChecklist, CHECKLIST, {
            "transcript": request.transcript,
            "questions": question_payload(missing),
        }) if missing else EvaluatedChecklist(questions=[])
        try:
            definitions = {q.id: q for q in missing}
            if len(output.questions) != len(missing) or {q.id for q in output.questions} != set(definitions):
                raise ValueError("Deben devolverse exactamente las preguntas faltantes.")
            for result in output.questions:
                definition = definitions.get(result.id)
                if definition is None:
                    raise ValueError("ID ajeno al catálogo.")
                known[result.id] = self._convert(result, definition, request.transcript)
            evaluated = ChecklistEvaluationResult(questions=[known[q.id] for q in request.questions])
            evaluated.validate_against(request)
            self.remember(request.transcript, missing, output.questions)
            return evaluated
        except (ValueError, ValidationError) as error:
            raise ProviderError("invalid_provider_output", "Checklist sin evidencia válida.") from error
