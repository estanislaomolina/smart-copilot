"""Segmentación y evidencia sobre la transcripción original, sin reglas de clasificación."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.domain.models import Evidence

_SPEAKER = re.compile(r"\b(?P<role>Operador|Llamante)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class Segment:
    text: str
    start: int


@dataclass(frozen=True)
class DialogueTurn:
    role: str
    text: str
    start: int


def dialogue_turns(transcript: str) -> list[DialogueTurn]:
    turns = list(_SPEAKER.finditer(transcript))
    if not turns:
        return [DialogueTurn("llamante", transcript, 0)]
    return [
        DialogueTurn(turn["role"].casefold(), transcript[turn.end():end], turn.end())
        for turn, end in zip(turns, [t.start() for t in turns[1:]] + [len(transcript)])
    ]


def caller_segments(transcript: str) -> list[Segment]:
    """Mantiene offsets originales y excluye las preguntas del operador."""
    return [Segment(turn.text, turn.start) for turn in dialogue_turns(transcript)
            if turn.role == "llamante"]


def evidence(segment: Segment, match: re.Match[str], group: str | int = 0) -> Evidence:
    start, end = match.span(group)
    return Evidence(text=segment.text[start:end],
                    start=segment.start + start, end=segment.start + end)
