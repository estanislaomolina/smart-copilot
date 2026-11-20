"""Extracción parcial por reglas; sin red, catálogo de respuestas ni acceso al CSV."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from backend.domain.models import (
    AnalysisRequest, AnalysisResult, Category, Evidence, FieldValue, IncidentData,
    Location,
)
from backend.domain.transcript import Segment, caller_segments, evidence
from backend.providers.mock_rules import extract_risks, suggest_priority

# Nombres propios y conectores frecuentes. No intenta resolver geografía ni aliases.
_WORD = r"(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ]+|[A-ZÁÉÍÓÚÑ]\.?)"
_NAME = rf"(?!(?:En|Desde|Hola)\b)(?:\d{{1,2}}\s+(?:de\s+)?{_WORD}|{_WORD})(?:\s+(?:(?:de|del|la|los|las)\s+)?{_WORD}){{0,4}}"
_STREET = rf"(?:(?i:av\.?|avenida|calle|autopista)\s+)?{_NAME}"
_ADDRESS = re.compile(rf"(?P<street>{_STREET})\s+(?i:al\s+)?(?P<number>\d{{1,5}})\b")
_INTERSECTION = re.compile(rf"(?P<street>{_STREET})\s+y\s+(?P<cross>{_STREET})")
_NEARBY = re.compile(rf"(?i:casi|entre|cerca de|esquina de)\s+(?P<cross>{_STREET}(?:\s+y\s+{_STREET})?)")
_REFERENCE = re.compile(rf"(?P<street>(?i:av\.?|avenida|autopista)\s+{_NAME})(?:\s+(?i:altura)\s+(?P<reference>{_NAME}))?")
_CORRECTION = re.compile(
    r"(?:perd[oó]n[, :]+|(?P<explicit>(?:la\s+)?altura correcta es\s+)|corrijo[, :]+)"
    r"(?P<number>\d{1,5})\b", re.IGNORECASE,
)
_UNCERTAIN_NUMBER = re.compile(
    r"\b(?:no s[eé] si|no distingo si|no puedo confirmar|no puedo leer|"
    r"no s[eé] la altura|creo que|tal vez)\b", re.IGNORECASE,
)
_NEGATED = re.compile(
    r"\b(?:no hay|no hubo|no veo|no se ve|sin)\s+(?:\w+\s+){0,2}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CategoryRule:
    category: Category
    pattern: str


# Reglas de desarrollo, no protocolos operativos ni reglas de prioridad.
_CATEGORY_RULES = (
    CategoryRule("INCENDIO_RESCATE",
                 r"\b(?:incendio|fuego|llamas|quema|gasoil a chorros)\b|"
                 r"\b(?:trab[oó]|trabado)[^.]{0,40}\bascensor\b|"
                 r"\bascensor[^.]{0,40}\b(?:trab[oó]|trabado)\b|"
                 r"\bhumo[^.]{0,100}\btablero\b|"
                 r"\bsubestaci[oó]n[^!]{0,180}\b(?:explosi[oó]n|humo)\b"),
    CategoryRule("ACCIDENTE_VIAL",
                 r"\b(?:choque|colisi[oó]n|volcado|volc[oó]|atropell[oó])\b|"
                 r"\bchoc[oó][^.]{0,60}\b(?:taxi|moto|auto|colectivo|camioneta)\b|"
                 r"\bcolectivo[^.]{0,60}\btir[oó] al piso\b|"
                 r"\bcami[oó]n[^.]{0,250}\bencajado\b"),
    CategoryRule("EMERGENCIA_MEDICA",
                 r"\b(?:convulsionando|convulsi[oó]n|broncoespasmo|desmay[oó]|"
                 r"fractura|al[eé]rgico)\b|\bse golpe[oó]\b"),
    CategoryRule("DEFENSA_CIVIL",
                 r"\b(?:ca[nñ]o de gas|olor a gas|marquesina|medianera|"
                 r"inund[oó]|anegamiento)\b|"
                 r"\b(?:[aá]rbol|tipa)[^.]{0,70}\b(?:ca[ií]do|colaps[oó])\b|"
                 r"\bcolapsar[^.]{0,30}\btipa\b"),
    CategoryRule("SERVICIOS_PUBLICOS",
                 r"\b(?:sem[aá]foros|socav[oó]n|ca[nñ]o maestro)\b|"
                 r"\bpozo[^.]{0,70}\bagua\b|"
                 r"\bcable[^.]{0,40}\bchispeando\b"),
    CategoryRule("CONVIVENCIA_SEGURIDAD",
                 r"\bpelea\b|\bperro[^.]{0,80}\b(?:sin bozal|gru[nñ]endo|agresivo)\b"),
)


def extracted(span: Evidence) -> FieldValue[str]:
    return FieldValue[str](value=span.text, origin="transcript", evidence=[span])


def extract_location(segments: list[Segment]) -> tuple[Location, list[str]]:
    location = Location()
    warnings: list[str] = []
    addresses: list[tuple[Evidence, Evidence, Segment, int]] = []
    for segment in segments:
        for match in _ADDRESS.finditer(segment.text):
            # No confundir nombres de autopista/avenida con su altura.
            if match["street"].rstrip(".").casefold() in ("av", "avenida", "calle", "autopista"):
                continue
            has_prefix = re.match(r"(?i:av\.?|avenida|calle|autopista)\s+", match["street"])
            locative = re.search(r"(?:^|\b(?:en|de|desde|por|sobre|dirección))\s*$",
                                 segment.text[:match.start()], re.IGNORECASE)
            if not has_prefix and not locative:
                continue  # Un nombre seguido de edad o cantidad no basta para ubicar.
            addresses.append((evidence(segment, match, "street"),
                              evidence(segment, match, "number"), segment, match.end()))

    unique_streets = {item[0].text.casefold() for item in addresses}
    unique_numbers = {item[1].text for item in addresses}
    if len(unique_streets) == 1:
        street, number, segment, end = addresses[0]
        location.street = extracted(street)
        corrections = [
            evidence(part, match, "number")
            for part in segments for match in _CORRECTION.finditer(part.text)
            if part.start + match.start() > number.start
            and (match["explicit"] or (
                part.start <= number.end <= part.start + match.start()
                and not part.text[number.end - part.start:match.start()].strip(" ,;:")
            ))
        ]
        uncertain = any(_UNCERTAIN_NUMBER.search(part.text) for part in segments)
        if uncertain:
            warnings.append("La altura requiere confirmación: el relato expresa incertidumbre.")
        elif corrections:
            location.number = extracted(corrections[-1])
        elif len(unique_numbers) == 1:
            location.number = extracted(number)
        else:
            warnings.append("Hay varias alturas sin corrección reconocida; confirmar con el llamante.")
        nearby = _NEARBY.search(segment.text, end)
        if nearby:
            location.intersection = extracted(evidence(segment, nearby, "cross"))
    elif len(unique_streets) > 1:
        warnings.append("Hay varias direcciones posibles; la ubicación requiere confirmación.")

    if not addresses:
        intersections = [
            (part, match) for part in segments
            for match in _INTERSECTION.finditer(part.text)
        ]
        distinct = {(m["street"].casefold(), m["cross"].casefold())
                    for _, m in intersections}
        if len(distinct) == 1:
            part, match = intersections[0]
            location.street = extracted(evidence(part, match, "street"))
            location.intersection = extracted(evidence(part, match))
        elif len(distinct) > 1:
            warnings.append("Hay varias intersecciones posibles; confirmar ubicación.")
        else:
            references = [(part, match) for part in segments
                          for match in _REFERENCE.finditer(part.text)]
            if len({m["street"].casefold() for _, m in references}) == 1:
                part, match = references[0]
                location.street = extracted(evidence(part, match, "street"))
                if match["reference"]:
                    location.reference = extracted(evidence(part, match, "reference"))
    if location.street.value is None:
        warnings.append("No se reconoció una ubicación única con las reglas disponibles.")
    if location.number.value is None:
        warnings.append("Altura desconocida; no se completa desde información externa.")
    return location, warnings


def extract_category(segments: list[Segment]) -> tuple[FieldValue[Category], list[str]]:
    matches: dict[Category, list[Evidence]] = {}
    for rule in _CATEGORY_RULES:
        for segment in segments:
            for match in re.finditer(rule.pattern, segment.text, re.IGNORECASE):
                if not _NEGATED.search(segment.text[max(0, match.start() - 60):match.start()]):
                    matches.setdefault(rule.category, []).append(evidence(segment, match))
    if len(matches) == 1:
        category, spans = next(iter(matches.items()))
        return FieldValue[Category](
            value=category, origin="inference", evidence=spans,
            rationale="Categoría sugerida por coincidencias de reglas léxicas; requiere revisión.",
        ), []
    if matches:
        return FieldValue[Category](), [
            "Se detectaron señales de varias categorías: " + ", ".join(sorted(matches))
            + ". Confirmar el tipo de incidente."
        ]
    return FieldValue[Category](), ["No se reconoció una categoría con las reglas disponibles."]


class MockExtractionProvider:
    name: Literal["mock"] = "mock"

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        segments = caller_segments(request.transcript)
        location, location_warnings = extract_location(segments)
        category, category_warnings = extract_category(segments)
        assessment = extract_risks(segments)
        priority, priority_warnings = suggest_priority(assessment, category)
        return AnalysisResult(
            request=request,
            data=IncidentData(location=location, category=category,
                              risks=list(assessment.signals.values()), priority=priority),
            provider=self.name, model="rules-v2",
            warnings=[
                "Mock de simulación: sugerencias no validadas para uso operativo. "
                "Revisar el protocolo mediante el motor de catálogo separado.",
                *location_warnings, *category_warnings,
                *assessment.warnings, *priority_warnings,
            ],
        )
