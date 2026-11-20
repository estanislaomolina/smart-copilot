"""Selección de protocolo y checklist; independiente del mock y del futuro LLM."""

from backend.domain.models import IncidentData
from backend.protocols.catalog import ProtocolCatalog, canonical
from pydantic import ValidationError

from backend.providers.base import ProviderError
from backend.protocols.evaluation import ChecklistEvaluator, ChecklistEvaluationRequest, ChecklistEvaluationResult
from backend.protocols.models import ProtocolError, ProtocolRequest, ProtocolResult


class ProtocolEngine:
    def __init__(self, catalog: ProtocolCatalog, evaluator: ChecklistEvaluator):
        self.catalog = catalog
        self.evaluator = evaluator

    def apply(self, request: ProtocolRequest) -> ProtocolResult:
        category = request.data.category.value
        candidates = self.catalog.summaries(category)
        protocol = None
        origin = None
        if request.protocol_id:
            protocol = self.catalog.get(request.protocol_id)
            if category is not None and protocol.category != category:
                raise ProtocolError("protocol_category_mismatch")
            origin = "operator"
        elif category is not None and request.data.subcategory.value:
            matching = [candidate for candidate in candidates
                        if candidate.scope == "specific"
                        and canonical(candidate.subcategory) == canonical(request.data.subcategory.value)]
            if len(matching) == 1:
                protocol = self.catalog.get(matching[0].id)
                origin = "subcategory"
        if protocol is None and category is not None:
            protocol = self.catalog.general_for(category)
            if protocol is not None:
                origin = "category"
        if protocol is None:
            return ProtocolResult(
                selection="pending", candidates=candidates,
                warnings=["Confirmar la categoría para iniciar una guía general o seleccionar un protocolo."],
            )

        warnings = ["Catálogos de demostración; instrucciones sin validación operativa."]
        if protocol.scope == "general":
            warnings.append("Guía general por categoría; no determina ni confirma un subtipo.")
        if category is None:
            warnings.append("La categoría sigue desconocida; revisar su correspondencia con el protocolo.")
        evaluation_request = ChecklistEvaluationRequest(
            transcript=request.request.transcript, questions=protocol.questions,
        )
        try:
            output = self.evaluator.evaluate(evaluation_request.model_copy(deep=True))
            payload = output.model_dump() if isinstance(output, ChecklistEvaluationResult) else output
            evaluated = ChecklistEvaluationResult.model_validate(payload)
            evaluated.validate_against(evaluation_request)
        except (ValidationError, ValueError) as exc:
            raise ProviderError("invalid_provider_output", "Evaluación de checklist inválida.") from exc
        automatic_questions = {question.id: question for question in evaluated.questions}
        previous = {question.id: question for question in request.data.questions}
        questions = []
        review_notices = []
        compatible_ids = set()
        for definition in protocol.questions:
            old = previous.get(definition.id)
            automatic = automatic_questions[definition.id]
            if (old is not None and old.origin == "operator"
                    and canonical(old.text) == canonical(definition.text)):
                reviewed = old.model_copy(deep=True)
                reviewed.follow_up = automatic.follow_up if old.status in ("pending", "ambiguous") else None
                questions.append(reviewed)
                compatible_ids.add(old.id)
                if (automatic.status != "pending"
                        and (old.status != automatic.status
                             or canonical(old.answer or "") != canonical(automatic.answer or ""))):
                    review_notices.append(
                        f'{definition.text} El relato aporta una respuesta distinta o incierta; '
                        'se conserva la revisión manual. Revisar antes de continuar.'
                    )
            else:
                questions.append(automatic)
        if any(question.origin == "operator" and question.id not in compatible_ids
               for question in request.data.questions):
            warnings.append("Hay respuestas manuales que no corresponden a las preguntas del protocolo actual.")
        # Comprobar evidencia sobre la llamada actual; no copiar estados del catálogo.
        IncidentData(questions=questions).validate_transcript(
            request.request.transcript, allow_operator=True,
        )
        return ProtocolResult(
            selection=("selected" if origin == "operator" else "general" if origin == "category" else "suggested"),
            selection_origin=origin, protocol=protocol.summary(), candidates=candidates,
            questions=questions,
            instructions=[item.model_copy(deep=True) for item in protocol.instructions],
            warnings=warnings, review_notices=review_notices,
        )
