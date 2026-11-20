"""Selección de protocolo y checklist; independiente del mock y del futuro LLM."""

from backend.domain.models import IncidentData
from backend.protocols.catalog import ProtocolCatalog, canonical
from backend.protocols.checklist import resolve_question
from backend.protocols.models import ProtocolError, ProtocolRequest, ProtocolResult


class ProtocolEngine:
    def __init__(self, catalog: ProtocolCatalog):
        self.catalog = catalog

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
                        if canonical(candidate.subcategory) == canonical(request.data.subcategory.value)]
            if len(matching) == 1:
                protocol = self.catalog.get(matching[0].id)
                origin = "subcategory"
        if protocol is None:
            return ProtocolResult(
                selection="pending", candidates=candidates,
                warnings=["La categoría sola no define un protocolo; seleccionar subtipo o protocolo."],
            )

        warnings = ["Catálogo de demostración derivado de datos sintéticos; instrucciones sin validación operativa."]
        if category is None:
            warnings.append("La categoría sigue desconocida; revisar su correspondencia con el protocolo.")
        previous = {question.id: question for question in request.data.questions}
        questions = []
        compatible_ids = set()
        for definition in protocol.questions:
            old = previous.get(definition.id)
            if (old is not None and old.origin == "operator"
                    and canonical(old.text) == canonical(definition.text)):
                questions.append(old.model_copy(deep=True))
                compatible_ids.add(old.id)
            else:
                questions.append(resolve_question(definition, request.request.transcript))
        if any(question.origin == "operator" and question.id not in compatible_ids
               for question in request.data.questions):
            warnings.append("Hay respuestas manuales que no corresponden a las preguntas del protocolo actual.")
        # Comprobar evidencia sobre la llamada actual; no copiar estados del catálogo.
        IncidentData(questions=questions).validate_transcript(
            request.request.transcript, allow_operator=True,
        )
        return ProtocolResult(
            selection="selected" if origin == "operator" else "suggested",
            selection_origin=origin, protocol=protocol.summary(), candidates=candidates,
            questions=questions,
            instructions=[item.model_copy(deep=True) for item in protocol.instructions],
            warnings=warnings,
        )
