"""Variantes deterministas de desarrollo; nunca modifican el corpus original."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate import Suite, evaluate, summarize
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.providers.mock import MockExtractionProvider
from backend.providers.checklist_mock import MockChecklistEvaluator


def number_words(number: int) -> str:
    small = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece "
             "catorce quince dieciséis diecisiete dieciocho diecinueve veinte veintiuno "
             "veintidós veintitrés veinticuatro veinticinco veintiséis veintisiete "
             "veintiocho veintinueve").split()
    if number < 30:
        return small[number]
    if number < 100:
        tens = ("", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa")
        return tens[number // 10] + (" y " + small[number % 10] if number % 10 else "")
    if number == 100:
        return "cien"
    if number < 1000:
        hundreds = ("", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos",
                    "seiscientos", "setecientos", "ochocientos", "novecientos")
        return hundreds[number // 100] + (" " + number_words(number % 100) if number % 100 else "")
    return ("mil" if number // 1000 == 1 else number_words(number // 1000) + " mil") + (
        " " + number_words(number % 1000) if number % 1000 else "")


def variants(text: str) -> dict[str, str]:
    # Preserve line boundaries and speaker roles: short answers depend on them.
    return {
        "original": text,
        "minusculas": text.lower(),
        "espacios": re.sub(r"[ \t]+", "  ", text),
        "muletillas": re.sub(r"(?i)\b(llamante|ciudadano):", r"\1: Bueno, eh,", text),
        "numeros_en_palabras": re.sub(
            r"(?<![\w/-])(?<!\d\.)(?:0|[1-9]\d{0,3})(?![\w/-]|\.\d)",
            lambda match: number_words(int(match.group())), text),
    }


async def run(suite: Suite) -> dict:
    groups = {}
    for name in variants(suite.cases[0].transcript):
        cases = [case.model_copy(update={
            "id": case.id + "/" + name,
            "transcript": variants(case.transcript)[name],
        }, deep=True) for case in suite.cases]
        derived = Suite(split="development", description="Variaciones de casos conocidos.", cases=cases)
        results = await evaluate(derived, MockExtractionProvider(),
                                 ProtocolEngine(ProtocolCatalog(), MockChecklistEvaluator()))
        groups[name] = {
            "cases": len(cases),
            "changed": sum(a.transcript != b.transcript for a, b in zip(suite.cases, cases)),
            "counts": {status: sum(r["status"] == status for r in results)
                       for status in ("passed", "failed", "error", "skipped")},
            "summary": summarize(results),
            "results": results,
        }
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data/evaluation/development.json")
    parser.add_argument("--csv", type=Path, help="CSV original conocido; expectativas literales sin validar.")
    parser.add_argument("--export-cases", type=Path,
                        help="Exportar variantes para el evaluador existente; no consulta proveedores remotos.")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluation/robustness-mock.json")
    args = parser.parse_args()
    source = args.csv or args.cases
    if args.output.exists() or args.output.resolve() == source.resolve():
        parser.error("Elegí una salida nueva; no se sobrescriben entradas ni resultados.")
    if args.export_cases and (args.export_cases.exists() or args.export_cases.resolve() in
                             {source.resolve(), args.output.resolve()}):
        parser.error("La suite derivada necesita una ruta nueva y distinta del reporte.")
    if args.csv:
        from scripts.evaluate_csv import csv_suite
        suite, _ = csv_suite(source)
    else:
        suite = Suite.model_validate_json(source.read_bytes())
        if suite.split != "development":
            parser.error("Usá casos de desarrollo; no transformar un conjunto reservado.")
    if args.export_cases:
        derived = Suite(split="development", description="Variantes conocidas; no evaluación independiente.", cases=[
            case.model_copy(update={"id": case.id + "/" + name, "transcript": text}, deep=True)
            for case in suite.cases for name, text in variants(case.transcript).items()])
        args.export_cases.parent.mkdir(parents=True, exist_ok=True)
        args.export_cases.write_text(derived.model_dump_json(indent=2) + "\n")
    report = {
        "provider": "mock", "split": "development",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Variantes derivadas de casos conocidos: no son evaluación independiente.",
            "Comparaciones literales: una diferencia no demuestra error semántico.",
            "No se probaron proveedores remotos ni se midió su precisión.",
            "Los números en palabras pueden cambiar la grafía esperada aunque conserven el significado.",
        ],
        "groups": asyncio.run(run(suite)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({name: {"changed": row["changed"], **row["counts"]}
                      for name, row in report["groups"].items()}, ensure_ascii=False))
    print("Reporte:", args.output)
    return 1 if any(row["counts"]["error"] or row["counts"]["failed"]
                    for row in report["groups"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
