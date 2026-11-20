"""Contrato del evaluador contextual, independiente de la selección."""

from typing import Protocol

from pydantic import Field

from backend.domain.models import Contract, IncidentData, NonBlank, ProtocolQuestion
from backend.protocols.models import QuestionDefinition


class ChecklistEvaluationRequest(Contract):
    transcript: NonBlank = Field(max_length=50_000)
    questions: list[QuestionDefinition]


class ChecklistEvaluationResult(Contract):
    questions: list[ProtocolQuestion]

    def validate_against(self, request: ChecklistEvaluationRequest) -> None:
        expected = {question.id: question for question in request.questions}
        ids = [question.id for question in self.questions]
        if len(ids) != len(set(ids)) or set(ids) != set(expected):
            raise ValueError("El evaluador debe devolver exactamente las preguntas recibidas.")
        for question in self.questions:
            definition = expected[question.id]
            if question.text != definition.text or question.status == "not_applicable":
                raise ValueError("Pregunta o estado automático no permitido.")
            if question.follow_up is not None and (question.follow_up != definition.follow_up
                                                    or question.status != "ambiguous"):
                raise ValueError("La aclaración debe pertenecer al catálogo recibido.")
        IncidentData(questions=self.questions).validate_transcript(request.transcript, allow_operator=False)


class ChecklistEvaluator(Protocol):
    def evaluate(self, request: ChecklistEvaluationRequest) -> ChecklistEvaluationResult:
        """Recibe toda la conversación y preguntas del catálogo, sin etiquetas del CSV."""
        ...
