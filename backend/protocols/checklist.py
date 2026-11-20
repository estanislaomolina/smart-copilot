"""Resolución conservadora de preguntas explícitas y revisión manual."""

import re
from dataclasses import dataclass

from backend.domain.models import Evidence, ProtocolQuestion
from backend.domain.transcript import dialogue_turns
from backend.protocols.catalog import canonical
from backend.protocols.models import QuestionDefinition

_UNCERTAIN = re.compile(
    r"\b(?:no s[eé]|no veo|no puedo confirmar|no estoy segur[oa]|creo que|tal vez)\b",
    re.IGNORECASE,
)
_YES_NO = re.compile(r"^(?:s[ií]|no)\b", re.IGNORECASE)
_CORRECTION = re.compile(r"^(?:perd[oó]n|corrijo|en realidad)\s*[,.:]?\s*", re.IGNORECASE)


@dataclass
class Answer:
    text: str
    evidence: Evidence
    polarity: str | None
    corrected: bool


def resolve_question(question: QuestionDefinition, transcript: str) -> ProtocolQuestion:
    turns = dialogue_turns(transcript)
    expected = canonical(question.text.split("?", 1)[0])
    answers: list[Answer] = []
    for turn, reply in zip(turns, turns[1:]):
        if turn.role != "operador" or reply.role != "llamante":
            continue
        # No usa la similitud con una llamada de referencia para inferir respuestas.
        if f" {expected} " not in f" {canonical(turn.text)} ":
            continue
        text = reply.text.strip()
        if not text:
            continue
        corrected = bool(_CORRECTION.match(text))
        cleaned = _CORRECTION.sub("", text)
        prefix = _YES_NO.match(cleaned)
        polarity = None
        if (question.answer_type == "yes_no" and prefix
                and not _UNCERTAIN.search(cleaned) and turn.text.count("?") == 1
                and "?" not in cleaned):
            polarity = canonical(prefix.group())
        start, end = turn.start, reply.start + len(reply.text)
        answers.append(Answer(text, Evidence(text=transcript[start:end], start=start, end=end),
                              polarity, corrected))
    corrections = [index for index, answer in enumerate(answers) if answer.corrected]
    if corrections:
        answers = answers[corrections[-1]:]
    if not answers:
        return ProtocolQuestion(id=question.id, text=question.text)
    polarities = {answer.polarity for answer in answers}
    ambiguous = None in polarities or len(polarities) != 1
    return ProtocolQuestion(
        id=question.id, text=question.text,
        status="ambiguous" if ambiguous else "answered",
        answer=answers[-1].text, origin="transcript",
        evidence=[answer.evidence for answer in answers],
        rationale=("Hay diálogo relacionado, pero las reglas no permiten una respuesta inequívoca."
                   if ambiguous else None),
    )
