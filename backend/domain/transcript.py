"""Segmentación y evidencia compartidas por las reglas del mock."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.domain.models import Evidence

_SPEAKER = re.compile(r"\b(?P<role>Operador|Llamante)\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class Segment:
    text: str
    start: int


def caller_segments(transcript: str) -> list[Segment]:
    """Mantiene offsets originales y excluye las preguntas del operador."""
    turns = list(_SPEAKER.finditer(transcript))
    if not turns:
        return [Segment(transcript, 0)]
    return [
        Segment(transcript[turn.end():end], turn.end())
        for turn, end in zip(turns, [t.start() for t in turns[1:]] + [len(transcript)])
        if turn["role"].casefold() == "llamante"
    ]


def evidence(segment: Segment, match: re.Match[str], group: str | int = 0) -> Evidence:
    start, end = match.span(group)
    return Evidence(text=segment.text[start:end],
                    start=segment.start + start, end=segment.start + end)
