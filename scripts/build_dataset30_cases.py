"""Genera casos de desarrollo desde los 30 registros del CSV provisto, sin modificarlo."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/dataset_challenge_soflex.csv"
DEFAULT_OUTPUT = ROOT / "artifacts/evaluation/dataset-30-cases.json"


def build_suite() -> dict:
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    cases = []
    for row in rows:
        fields = {
            "category": row["categoria"].strip() or None,
            "subcategory": row["subcategoria"].strip() or None,
            "location.street": row["calle_detectada"].strip() or None,
            "location.number": row["altura_detectada"].strip() or None,
            "location.intersection": row["interseccion_detectada"].strip() or None,
            "location.district": row["barrio_comuna"].strip() or None,
        }
        cases.append({
            "id": row["id_registro"],
            "focus": "registro_provisto_conocido",
            "transcript": row["transcripcion_cruda"],
            "fields": fields,
            "questions": [],
            "review_notes": [
                "Verificación sobre casos conocidos de desarrollo; no es evaluación independiente.",
                "Las etiquetas del CSV pueden incluir información enriquecida ausente del relato; ver docs/data-audit.md.",
                "La prioridad no se compara: el proveedor LLM no asigna P1-P4 sin política operativa.",
            ],
        })
    return {
        "split": "development",
        "description": (
            "Los 30 registros del CSV provisto. Expectativas literales tomadas de sus columnas, sin ajustar reglas "
            "ni prompts. Incluye etiquetas que pueden contener información enriquecida no presente en el relato. "
            "Solo extracción: la prioridad no se compara porque el proveedor LLM no la asigna. "
            "No se presenta como evaluación independiente."
        ),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("El destino ya existe; elegí otra ruta o --overwrite explícito.")
    suite = build_suite()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Casos generados: {len(suite['cases'])}; destino: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
