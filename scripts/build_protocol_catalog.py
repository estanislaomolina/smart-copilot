"""Deriva un catálogo de demostración sin respuestas ni datos de llamadas."""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/dataset_challenge_soflex.csv"
OUTPUT = ROOT / "data/protocols/demo.json"


def canonical(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w]+", " ", "".join(
        char for char in folded if not unicodedata.combining(char)
    )).split())


def build_catalog(source: Path = SOURCE) -> dict:
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    protocols = []
    for row in rows:
        protocol_id = "sfx-demo-" + row["id_registro"].rsplit("-", 1)[-1]
        questions = []
        for text in row["preguntas_protocolo_mandatorias"].split("|"):
            text = text.strip()
            normalized = canonical(text)
            first = normalized.split()[0]
            yes_no = first in {
                "hay", "el", "la", "los", "las", "se", "tiene", "lleva", "alguna",
                "algun", "puede", "pudo", "sufrio", "cuenta", "esta", "existe",
            }
            questions.append({
                "id": "q-" + hashlib.sha256(normalized.encode()).hexdigest()[:12],
                "text": text, "answer_type": "yes_no" if yes_no else "free_text",
            })
        protocols.append({
            "id": protocol_id, "version": "demo-v1",
            "category": row["categoria"], "subcategory": row["subcategoria"],
            "source_record": row["id_registro"], "review_status": "demo_unverified",
            "questions": questions,
            "instructions": [{
                "id": protocol_id + "-prearrival", "protocol_id": protocol_id,
                "protocol_version": "demo-v1", "text": row["instrucciones_prearribo"],
                "source": "SOFLEX dataset sintético: " + row["id_registro"],
                "review_status": "demo_unverified",
            }],
        })
    return {"version": "demo-v1", "source_file": "data/raw/dataset_challenge_soflex.csv",
            "protocols": protocols}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.output.resolve() == SOURCE.resolve():
        parser.error("El catálogo no puede sobrescribir el CSV original.")
    result = json.dumps(build_catalog(), ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(f"Catálogo generado: {args.output}")


if __name__ == "__main__":
    main()
