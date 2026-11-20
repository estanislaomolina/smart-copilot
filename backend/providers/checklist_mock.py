"""Evaluación contextual limitada; no selecciona protocolos ni prioridades."""

import re

from backend.domain.models import Evidence, ProtocolQuestion
from backend.domain.transcript import caller_segments
from backend.protocols.catalog import canonical
from backend.protocols.checklist import Answer, direct_answers, resolve_answers
from backend.protocols.evaluation import ChecklistEvaluationRequest, ChecklistEvaluationResult
from backend.protocols.models import QuestionDefinition
from backend.providers.mock_rules import extract_risks

_PEOPLE_TRAPPED = re.compile(
    r"\b(?:personas?|nadie|alguien|gente)\s+"
    r"(?:(?:est[aá]n?|qued[oó]|quedaron|siguen?)\s+)?atrapad[oa]s?\b", re.IGNORECASE)
_UNCERTAIN_PRESENCE = re.compile(
    r"\b(?:no s[eé]|no puedo confirmar|no estoy segur[oa])\s+(?:si\s+)?"
    r"(?:qued[oó]|quedaron|hay|siguen?)\s+(?:alguien|personas?|gente|nadie)\b", re.IGNORECASE)
_UNCERTAIN = re.compile(r"\b(?:no s[eé]|no puedo confirmar|no estoy segur[oa]|creo que|tal vez|quiz[aá]s?|si)\b", re.IGNORECASE)
_NEGATIVE = re.compile(r"\b(?:no\s+(?:hay|veo|quedan?|est[aá]n?)|sin)\s*(?:(?:una?|ninguna?|dos|tres|\d+)\s+)?$", re.IGNORECASE)
_CORRECTION = re.compile(r"\b(?:perd[oó]n|corrijo|en realidad|me equivoqu[eé])\b", re.IGNORECASE)
_CLAUSE = re.compile(r"[.!?;\n]|\b(?:pero|aunque)\b", re.IGNORECASE)


class MockChecklistEvaluator:
    def evaluate(self, request: ChecklistEvaluationRequest) -> ChecklistEvaluationResult:
        result = ChecklistEvaluationResult(questions=[
            self._evaluate(question, request.transcript) for question in request.questions])
        result.validate_against(request)
        return result

    def _evaluate(self, question: QuestionDefinition, transcript: str) -> ProtocolQuestion:
        answers = direct_answers(question, transcript)
        people_trapped = {"personas", "atrapadas"} <= set(canonical(question.text).split())
        if people_trapped:
            if question.follow_up:
                follow_up = QuestionDefinition(id=question.id, text=question.follow_up.text, answer_type="yes_no")
                answers.extend(direct_answers(follow_up, transcript))
            segments = caller_segments(transcript)
            for segment in segments:
                for match in _PEOPLE_TRAPPED.finditer(segment.text):
                    prefix = _CLAUSE.split(segment.text[:match.start()])[-1]
                    uncertain = bool(_UNCERTAIN.search(prefix)) or "?" in segment.text[match.end():].split(".", 1)[0]
                    polarity = None if uncertain else (
                        "no" if canonical(match.group()).startswith("nadie ") or _NEGATIVE.search(prefix) else "si")
                    start = segment.start + match.start() - len(prefix)
                    end = segment.start + match.end()
                    span = Evidence(text=transcript[start:end], start=start, end=end)
                    answers.append(Answer(span.text.strip(), span, polarity, bool(_CORRECTION.search(prefix))))
                for match in _UNCERTAIN_PRESENCE.finditer(segment.text):
                    start, end = segment.start + match.start(), segment.start + match.end()
                    span = Evidence(text=transcript[start:end], start=start, end=end)
                    answers.append(Answer(span.text, span, None, False, contextual=True))
            # Reutiliza evidencia de una señal existente; no agrega reglas por
            # ocupación ni asume que estar dentro implica atrapamiento.
            presence = extract_risks(segments).signals.get("R-TRAPPED")
            if presence:
                for span in presence.evidence:
                    if not any(answer.evidence.start <= span.start and answer.evidence.end >= span.end
                               for answer in answers):
                        answers.append(Answer(span.text, span, None, False, contextual=True))
            # Una contestación concreta posterior puede aclarar una presencia
            # anterior; las afirmaciones contradictorias siguen siendo ambiguas.
            definitive = [answer for answer in answers if not answer.contextual and answer.polarity is not None]
            if definitive:
                last = max(answer.evidence.start for answer in definitive)
                answers = [answer for answer in answers if not answer.contextual or answer.evidence.start > last]
        resolved = resolve_answers(question, answers)
        if resolved.status == "ambiguous":
            if people_trapped:
                resolved.rationale = (
                    "Hay información relacionada, pero no confirma una respuesta inequívoca. "
                    "Permanecer dentro no demuestra atrapamiento; confirmar si puede salir por sus propios medios.")
            resolved.follow_up = question.follow_up
        return resolved
