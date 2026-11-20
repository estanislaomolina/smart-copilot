"""Riesgos y prioridades de simulación, derivados de casos de desarrollo SOFLEX."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from backend.domain.models import Category, Evidence, FieldValue, Priority
from backend.domain.transcript import Segment, evidence


@dataclass(frozen=True)
class RiskRule:
    id: str
    label: str
    pattern: str
    source_cases: tuple[str, ...]
    origin: Literal["transcript", "inference"] = "inference"


@dataclass(frozen=True)
class PriorityRule:
    id: str
    priority: Priority
    requires: frozenset[str]
    explanation: str
    source_cases: tuple[str, ...]
    category: Category | None = None


# Señales de simulación. Los IDs y casos fuente permiten revisar cada decisión.
# No son diagnósticos ni procedimientos de atención.
RISK_RULES = (
    RiskRule("R-FIRE", "Posible exposición a fuego",
             r"\b(?:fuego|incendio|llamas|quema)\b", ("001", "002", "004", "025")),
    RiskRule("R-TRAPPED", "Presencia de personas informada en el relato",
             r"\b(?:personas?|cocinero|emplead[oa]s?)\s+"
             r"(?:(?:qued[oó]|quedaron|est[aá]n?)\s+)?(?:atrapad[oa]s?|adentro|dentro)\b|"
             r"\badentro\s+(?:qued[oó]|quedaron)\s+(?:(?:el|la|un|una)\s+)?"
             r"(?:cocinero|personas?|emplead[oa]s?)\b", ("001", "003"), origin="transcript"),
    RiskRule("R-SMOKE", "Posible afectación por humo",
             r"\bhumo(?:\s+(?:negro|blanco|gris|denso))?\b", ("001", "025", "030")),
    RiskRule("R-ELEVATOR", "Posible atrapamiento en ascensor",
             r"\b(?:trab[oó]|trabado)\s+el\s+ascensor\b|"
             r"\bascensor\s+(?:(?:est[aá]|qued[oó])\s+)?trabado\b", ("003",)),
    RiskRule("R-BREATHING", "Posible dificultad respiratoria",
             r"\bno\s+(?:le\s+entra\s+el\s+aire|puede\s+respirar)\b|"
             r"\b(?:se le est[aá] cerrando la garganta|labios morados)\b", ("009", "019")),
    RiskRule("R-GAS", "Posible escape de gas",
             r"\b(?:agujerearon|rompieron|perforaron)\s+un\s+ca[nñ]o de gas\b|"
             r"\b(?:fuga de gas|olor a gas)\b", ("012",)),
    RiskRule("R-LIVE-CABLE", "Posible contacto con cable eléctrico activo",
             r"\bcable\s+(?:grueso\s+)?chispeando\b", ("020",)),
    RiskRule("R-FUEL", "Posible derrame de combustible",
             r"\b(?:perdiendo|derramando)\s+gasoil\s+a\s+chorros\b|"
             r"\bderrame\s+de\s+(?:gasoil|combustible)\b", ("022",)),
    RiskRule("R-CONVULSION", "Posible lesión durante una convulsión",
             r"\b(?:convulsionando|convulsi[oó]n)\b", ("026",)),
    RiskRule("R-VEHICLE-TRAPPED", "Posible atrapamiento en un vehículo",
             r"\bconductor\s+est[aá]\s+atrapado\b|"
             r"\bqued[oó]\s+debajo\s+del\s+estribo\b", ("018", "029")),
    RiskRule("R-INJURY", "Posible lesión tras un traumatismo",
             r"\bse golpe[oó]\b|\bfractura expuesta\b", ("010", "023")),
    RiskRule("R-STRUCTURE", "Posible caída de elementos estructurales",
             r"\bse desprendieron[^.]{0,90}\bmarquesina\b|"
             r"\bse desmoron[oó][^.]{0,60}\b(?:pared|medianera)\b", ("014", "027")),
    RiskRule("R-INDOOR-FLOOD", "Posible inundación de espacios interiores",
             r"\bentrando\s+agua\s+a\s+(?:dos|\d+)\s+subsuelos\b", ("028",)),
    RiskRule("R-CONTAINER", "Posible propagación desde un contenedor de residuos",
             r"\b(?:fuego|llamas|incendio)[^.]{0,60}\bcontenedor\s+(?:negro\s+)?de\s+basura\b", ("002",)),
    RiskRule("R-SIGNALS", "Posible colisión por semáforos fuera de servicio",
             r"\bse apag[oó][^.]{0,60}\bsem[aá]foros\b|"
             r"\bsem[aá]foros\s+(?:apagados|fuera de servicio)\b", ("024",)),
)

PRIORITY_RULES = (
    PriorityRule("P-FIRE-TRAPPED", "P1", frozenset({"R-FIRE", "R-TRAPPED"}),
                 "Fuego y posible permanencia de personas en el lugar.", ("001",)),
    PriorityRule("P-BREATHING", "P1", frozenset({"R-BREATHING"}),
                 "Señal explícita de dificultad respiratoria.", ("009", "019")),
    PriorityRule("P-GAS", "P1", frozenset({"R-GAS"}),
                 "Señal reconocida de escape de gas.", ("012",)),
    PriorityRule("P-LIVE-CABLE", "P1", frozenset({"R-LIVE-CABLE"}),
                 "Cable reportado con chisporroteo activo.", ("020",)),
    PriorityRule("P-FUEL", "P1", frozenset({"R-FUEL"}),
                 "Señal reconocida de derrame de combustible.", ("022",)),
    PriorityRule("P-CONVULSION", "P1", frozenset({"R-CONVULSION"}),
                 "Convulsión reportada en el relato.", ("026",)),
    PriorityRule("P-VEHICLE-TRAPPED", "P1", frozenset({"R-VEHICLE-TRAPPED"}),
                 "Posible atrapamiento vinculado a un vehículo.", ("018", "029")),
    PriorityRule("P-ELEVATOR", "P2", frozenset({"R-ELEVATOR"}),
                 "Ascensor trabado reconocido por las reglas.", ("003",), "INCENDIO_RESCATE"),
    PriorityRule("P-INJURY", "P2", frozenset({"R-INJURY"}),
                 "Traumatismo reconocido en un incidente médico.", ("010", "023"), "EMERGENCIA_MEDICA"),
    PriorityRule("P-STRUCTURE", "P2", frozenset({"R-STRUCTURE"}),
                 "Desprendimiento o desmoronamiento reportado.", ("014", "027"), "DEFENSA_CIVIL"),
    PriorityRule("P-INDOOR-FLOOD", "P2", frozenset({"R-INDOOR-FLOOD"}),
                 "Entrada de agua a subsuelos reportada.", ("028",), "SERVICIOS_PUBLICOS"),
    PriorityRule("P-CONTAINER", "P3", frozenset({"R-FIRE", "R-CONTAINER"}),
                 "Fuego en contenedor según el escenario de referencia.", ("002",), "INCENDIO_RESCATE"),
    PriorityRule("P-SIGNALS", "P3", frozenset({"R-SIGNALS"}),
                 "Semáforos apagados según el escenario de referencia.", ("024",), "SERVICIOS_PUBLICOS"),
)

_NEGATIVE = re.compile(
    r"\b(?:no(?:\s+(?:hay|hubo|veo|se ve|est[aá]|sigue))?|sin)\s+"
    r"(?:\w+\s+){0,2}$", re.IGNORECASE,
)
_UNCERTAIN = re.compile(
    r"\b(?:no s[eé] si|no puedo confirmar si|creo que|dicen que|"
    r"quiz[aá]s?|tal vez|puede que|riesgo de|si)\s+(?:\w+\s+){0,3}$",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"\b(?:perd[oó]n|corrijo|correcci[oó]n|me equivoqu[eé]|en realidad)\b",
    re.IGNORECASE,
)
_CLAUSE = re.compile(r"[.!?;\n]|\b(?:pero|aunque)\b", re.IGNORECASE)


@dataclass
class RiskAssessment:
    signals: dict[str, FieldValue[str]]
    unresolved: set[str]
    warnings: list[str]


def extract_risks(segments: list[Segment]) -> RiskAssessment:
    signals: dict[str, FieldValue[str]] = {}
    unresolved: set[str] = set()
    warnings: list[str] = []
    for rule in RISK_RULES:
        occurrences: list[tuple[str, Evidence, bool]] = []
        for segment in segments:
            for match in re.finditer(rule.pattern, segment.text, re.IGNORECASE):
                prefix = _CLAUSE.split(segment.text[:match.start()])[-1]
                question = "¿" in prefix and "?" in segment.text[match.end():].split(".", 1)[0]
                state = ("uncertain" if question or _UNCERTAIN.search(prefix) else
                         "negative" if _NEGATIVE.search(prefix) else "positive")
                occurrences.append((state, evidence(segment, match), bool(_CORRECTION.search(prefix))))
        # Solo una corrección explícita permite reemplazar afirmaciones previas.
        corrections = [i for i, item in enumerate(occurrences) if item[2]]
        if corrections:
            occurrences = occurrences[corrections[-1]:]
        states = {item[0] for item in occurrences}
        if "uncertain" in states or {"positive", "negative"} <= states:
            unresolved.add(rule.id)
            warnings.append(f"{rule.id}: señal ambigua o contradictoria; confirmar con el llamante.")
        elif "positive" in states:
            signals[rule.id] = FieldValue[str](
                value=rule.label, origin=rule.origin,
                evidence=[item[1] for item in occurrences if item[0] == "positive"],
                rationale=(f"{rule.id}: información reportada por el llamante; no equivale a verificación independiente."
                           if rule.origin == "transcript"
                           else f"{rule.id}: señal interpretada por reglas del mock; requiere revisión."),
            )
    return RiskAssessment(signals, unresolved, warnings)


def suggest_priority(
    assessment: RiskAssessment, category: FieldValue[Category],
) -> tuple[FieldValue[Priority], list[str]]:
    if assessment.unresolved:
        return FieldValue[Priority](), [
            "Prioridad desconocida por señales ambiguas o contradictorias: "
            + ", ".join(sorted(assessment.unresolved))
        ]
    candidates = [
        rule for rule in PRIORITY_RULES
        if rule.requires <= assessment.signals.keys()
        and (rule.category is None or rule.category == category.value)
    ]
    if not candidates:
        return FieldValue[Priority](), [
            "Prioridad desconocida: no hay una regla de simulación aplicable."
        ]
    rank = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}
    highest = min(rank[rule.priority] for rule in candidates)
    selected = [rule for rule in candidates if rank[rule.priority] == highest]
    spans = {
        (span.start, span.end, span.text): span
        for rule in selected for risk_id in sorted(rule.requires)
        for span in assessment.signals[risk_id].evidence
    }
    return FieldValue[Priority](
        value=selected[0].priority, origin="inference",
        evidence=[spans[key] for key in sorted(spans)],
        rationale=" ".join(f"{rule.id}: {rule.explanation}" for rule in selected)
        + " Sugerencia de simulación, no un protocolo de prioridad validado.",
    ), []
