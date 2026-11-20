"""Auditoría local y de solo lectura del CSV de SOFLEX; usa biblioteca estándar."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data/raw/dataset_challenge_soflex.csv"
EXPECTED_COLUMNS = (
    "id_registro", "timestamp_llamada", "origen_reporte", "categoria",
    "subcategoria", "prioridad_sugerida", "transcripcion_cruda", "calle_detectada",
    "altura_detectada", "interseccion_detectada", "barrio_comuna",
    "preguntas_protocolo_mandatorias", "preguntas_respondidas_en_relato",
    "preguntas_pendientes", "instrucciones_prearribo", "riesgos_detectados",
    "recursos_recomendados_despacho", "notas_operativas_despacho",
)
PRIORITIES = ("P1", "P2", "P3", "P4")


def normalize(text: str) -> str:
    """Ignora tildes, puntuación y diferencias de espacio; no infiere sinónimos."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        char for char in folded if not unicodedata.combining(char)
    )).split())


def literal_present(value: str, transcript: str) -> bool:
    """Busca tokens completos para no confundir altura 800 con 1800."""
    needle, haystack = normalize(value), normalize(transcript)
    return bool(needle) and f" {needle} " in f" {haystack} "


def questions(value: str) -> set[str]:
    # Compara formulaciones literales, no equivalencia semántica de preguntas.
    return {
        normalize(part.split("?", 1)[0])
        for part in value.split("|") if part.strip()
    }


def audit_dataset(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    try:
        columns = next(reader)
    except StopIteration as exc:
        raise ValueError("El archivo no tiene encabezado.") from exc
    if len(columns) != len(set(columns)):
        raise ValueError("El encabezado contiene columnas duplicadas.")
    if set(columns) != set(EXPECTED_COLUMNS):
        missing = sorted(set(EXPECTED_COLUMNS) - set(columns))
        extra = sorted(set(columns) - set(EXPECTED_COLUMNS))
        raise ValueError(f"Esquema inválido. Faltantes: {missing}; extras: {extra}")

    rows = []
    for values in reader:
        if len(values) != len(columns):
            raise ValueError(f"Fila terminada en línea {reader.line_num}: "
                             f"se esperaban {len(columns)} celdas y hay {len(values)}.")
        rows.append(dict(zip(columns, values)))
    if not rows:
        raise ValueError("El archivo no contiene registros.")

    findings: list[dict[str, Any]] = []

    def add(severity: str, code: str, record: str, field: str, detail: str) -> None:
        findings.append(dict(severity=severity, code=code, record=record,
                             field=field, detail=detail))

    for field, code in (("id_registro", "duplicate_id"),
                        ("transcripcion_cruda", "duplicate_transcript")):
        groups: dict[str, list[str]] = {}
        for index, row in enumerate(rows, start=2):
            value = normalize(row[field])
            if value:
                groups.setdefault(value, []).append(f"fila {index}: {row['id_registro']}")
        for records in groups.values():
            if len(records) > 1:
                add("error", code, "; ".join(records), field,
                    "Coincidencia tras normalizar tildes, puntuación y espacios.")

    for index, row in enumerate(rows, start=2):
        record = row["id_registro"] or f"fila {index}"
        transcript = row["transcripcion_cruda"]
        for field, value in row.items():
            if not value.strip():
                add("error", "empty_cell", record, field, "Celda vacía.")
        if row["prioridad_sugerida"] not in PRIORITIES:
            add("error", "invalid_priority", record, "prioridad_sugerida",
                "Se esperaba P1, P2, P3 o P4.")
        try:
            datetime.fromisoformat(row["timestamp_llamada"])
        except ValueError:
            add("error", "invalid_timestamp", record, "timestamp_llamada",
                "No es un timestamp ISO válido.")

        # S/N y kilómetros no son alturas de calle: requieren otra representación.
        height = row["altura_detectada"].strip()
        if re.fullmatch(r"\d+", height):
            kind = "numeric"
        elif re.match(r"\d+\s*\(", height):
            kind = "numeric_with_context"
        elif height.casefold().startswith("km"):
            kind = "kilometer_reference"
        elif height.casefold().startswith("s/n"):
            kind = "without_number"
        else:
            kind = "other"
        if kind != "numeric":
            add("review", "non_simple_height", record, "altura_detectada",
                f"Formato: {kind}; valor: {height}")
        if kind in ("numeric", "numeric_with_context"):
            number = re.match(r"\d+", height).group()
            if not literal_present(number, transcript):
                add("review", "height_not_literal", record, "altura_detectada",
                    f"La altura {number} no aparece como token en el relato.")

        for field in ("calle_detectada", "barrio_comuna"):
            if row[field].strip() and not literal_present(row[field], transcript):
                add("review", "location_not_literal", record, field,
                    "La etiqueta completa no coincide literalmente; puede ser "
                    "normalización o enriquecimiento, no necesariamente un error.")
        for part in re.split(r"\s+y\s+|\s*/\s*", row["interseccion_detectada"]):
            if part.strip() and not literal_present(part, transcript):
                add("review", "intersection_part_not_literal", record,
                    "interseccion_detectada", f"Parte sin coincidencia literal: {part}")

        mandatory = questions(row["preguntas_protocolo_mandatorias"])
        answered = questions(row["preguntas_respondidas_en_relato"])
        pending = questions(row["preguntas_pendientes"])
        if mandatory - answered != pending:
            add("review", "checklist_not_literal_partition", record,
                "preguntas_pendientes",
                "Las listas no forman obligatorias menos respondidas por formulación "
                "literal. Requiere revisar semántica e identidad de preguntas.")

    distributions = {
        field: dict(sorted(Counter(row[field] for row in rows).items()))
        for field in ("categoria", "subcategoria", "prioridad_sugerida", "origen_reporte")
    }
    missing_priorities = [p for p in PRIORITIES
                          if p not in distributions["prioridad_sugerida"]]
    return {
        "source": {"file": path.name, "sha256": hashlib.sha256(raw).hexdigest()},
        "rows": len(rows),
        "columns": columns,
        "empty_cells": sum(not value.strip() for row in rows for value in row.values()),
        "unique_ids": len({row["id_registro"] for row in rows}),
        "unique_transcripts": len({normalize(row["transcripcion_cruda"]) for row in rows}),
        "transcript_characters": {
            "min": min(len(row["transcripcion_cruda"]) for row in rows),
            "max": max(len(row["transcripcion_cruda"]) for row in rows),
        },
        "distributions": distributions,
        "missing_priorities": missing_priorities,
        "finding_counts": dict(sorted(Counter(f["code"] for f in findings).items())),
        "errors": sum(f["severity"] == "error" for f in findings),
        "review_flags": sum(f["severity"] == "review" for f in findings),
        "findings": findings,
        "limitations": [
            "Coincidencia literal no verifica verdad geográfica ni equivalencia semántica.",
            "Un flag de revisión no implica que la etiqueta sea incorrecta.",
            "No se validan clínicamente prioridades, riesgos ni instrucciones de prearribo.",
            "Esta auditoría no mide la calidad de un modelo.",
        ],
    }


def summary(report: dict[str, Any]) -> str:
    lines = [
        f"Fuente: {report['source']['file']}",
        f"SHA-256: {report['source']['sha256']}",
        f"Registros: {report['rows']}; columnas: {len(report['columns'])}",
        f"Celdas vacías: {report['empty_cells']}",
        f"IDs únicos: {report['unique_ids']}; relatos únicos normalizados: "
        f"{report['unique_transcripts']}",
        "Categorías: " + json.dumps(report["distributions"]["categoria"], ensure_ascii=False),
        "Prioridades: " + json.dumps(report["distributions"]["prioridad_sugerida"]),
        "Prioridades ausentes: " + ", ".join(report["missing_priorities"]),
        f"Errores estructurales/de valores: {report['errors']}",
        f"Señales para revisión (no errores confirmados): {report['review_flags']}",
    ]
    lines.extend(f"  {code}: {count}" for code, count in report["finding_counts"].items())
    lines.extend(["Límites:"] + [f"  {item}" for item in report["limitations"]])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--json", action="store_true", help="Detalle determinista en JSON.")
    args = parser.parse_args()
    try:
        report = audit_dataset(args.dataset)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        print(f"No se pudo auditar el dataset: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else summary(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
