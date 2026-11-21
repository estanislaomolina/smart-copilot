"""Evaluación de desarrollo: expectativas locales, nunca enviadas al proveedor."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domain.models import AnalysisRequest, Contract, IncidentData, NonBlank
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.protocols.models import ProtocolRequest, ProtocolResult
from backend.providers.checklist_mock import MockChecklistEvaluator
from backend.providers.base import ExtractionProvider, ProviderError
from backend.providers.mock import MockExtractionProvider
from backend.providers.llm_prompts import PROMPT_VERSION

FIELD_PATHS = {
    "category", "subcategory", "priority",
    "location.street", "location.number", "location.intersection",
    "location.reference", "location.district",
}


class ExpectedQuestion(Contract):
    text: NonBlank
    status: Literal["pending", "answered", "ambiguous"]
    # None omite la comparación de texto, pero no la de estado.
    answer: NonBlank | None = None


class Case(Contract):
    id: NonBlank
    transcript: NonBlank = Field(max_length=50_000)
    fields: dict[str, str | None] = Field(default_factory=dict)
    questions: list[ExpectedQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_checks(self):
        if not self.fields and not self.questions:
            raise ValueError("Cada caso necesita al menos una expectativa.")
        if set(self.fields) - FIELD_PATHS:
            raise ValueError("Campo de evaluación no permitido.")
        texts = [q.text for q in self.questions]
        if len(texts) != len(set(texts)):
            raise ValueError("Preguntas esperadas duplicadas.")
        return self


class Suite(Contract):
    split: Literal["development", "evaluation"]
    description: NonBlank
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de casos duplicados.")
        return self


def compare(case: Case, data: IncidentData, protocol: ProtocolResult) -> list[dict]:
    """Comparaciones literales: no usar un juez LLM ni inferir equivalencias."""
    checks = []
    for path, expected in case.fields.items():
        field = data
        for part in path.split("."):
            field = getattr(field, part)
        checks.append({"target": path, "expected": expected, "actual": field.value,
                       "passed": field.value == expected})
    by_text = {q.text: q for q in protocol.questions}
    for expected in case.questions:
        actual = by_text.get(expected.text)
        checks.append({"target": expected.text + " / status", "expected": expected.status,
                       "actual": actual.status if actual else None,
                       "passed": actual is not None and actual.status == expected.status})
        if expected.answer is not None:
            answer = actual.answer if actual else None
            # Solo mayúsculas y espacios; no equipara paráfrasis.
            checks.append({"target": expected.text + " / answer", "expected": expected.answer,
                           "actual": answer, "passed": answer is not None
                           and answer.strip().casefold() == expected.answer.strip().casefold()})
    return checks


async def evaluate(suite: Suite, provider: ExtractionProvider, engine: ProtocolEngine) -> list[dict]:
    results = []
    stopped = False
    for case in suite.cases:
        if stopped:
            results.append({"id": case.id, "status": "skipped", "reason": "provider_rate_limited"})
            continue
        start = time.monotonic()
        stage = "extraction"
        try:
            # Las expectativas, IDs y demás metadatos nunca llegan al extractor.
            analysis = await provider.analyze(AnalysisRequest(transcript=case.transcript))
            analysis.data.validate_transcript(case.transcript, allow_operator=False)
            stage = "checklist"
            protocol = engine.apply(ProtocolRequest(request=analysis.request, data=analysis.data))
            checks = compare(case, analysis.data, protocol)
            results.append({"id": case.id, "status": "passed" if all(c["passed"] for c in checks) else "failed",
                            "seconds": round(time.monotonic() - start, 3), "checks": checks})
        except ProviderError as error:
            # Sin textos externos, claves, salida completa ni transcripción en el reporte.
            results.append({"id": case.id, "status": "error", "stage": stage, "code": error.code,
                            "seconds": round(time.monotonic() - start, 3)})
            stopped = error.code == "provider_rate_limited"
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data/evaluation/development.json")
    parser.add_argument("--provider", choices=("mock", "groq"), default="mock",
                        help="Mock por defecto, incluso si el entorno selecciona Groq.")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluation/development.json")
    args = parser.parse_args()
    if args.output.resolve() == args.cases.resolve():
        parser.error("El reporte no puede sobrescribir los casos de entrada.")
    raw = args.cases.read_bytes()
    suite = Suite.model_validate_json(raw)
    gateway = None
    model = None
    if args.provider == "mock":
        provider, evaluator = MockExtractionProvider(), MockChecklistEvaluator()
    else:
        from backend.providers.config import ProviderSettings
        from backend.providers.groq import GroqGateway
        from backend.providers.llm import LLMExtractionProvider, LLMChecklistEvaluator
        # La selección explícita del CLI tiene precedencia; las credenciales siguen locales.
        os.environ["LLM_PROVIDER"] = "groq"
        settings = ProviderSettings.from_env()
        gateway = GroqGateway(settings)
        model = settings.model
        provider, evaluator = LLMExtractionProvider(gateway), LLMChecklistEvaluator(gateway)
    try:
        results = asyncio.run(evaluate(suite, provider, ProtocolEngine(ProtocolCatalog(), evaluator)))
    finally:
        if gateway:
            gateway.close()
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("passed", "failed", "error", "skipped")}
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "split": suite.split, "description": suite.description,
        "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "provider": args.provider, "model": model,
        "prompt_version": PROMPT_VERSION if gateway else None,
        "configuration": ({"reasoning_effort": settings.reasoning_effort,
                           "timeout_seconds": settings.timeout, "max_retries": settings.retries}
                          if gateway else {}),
        "comparison": "Valores exactos; respuestas ignoran solo mayúsculas y espacios exteriores.",
        "usage": None, "usage_note": "El contrato actual no expone consumo; no se estima.",
        "counts": counts, "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"provider": args.provider, "split": suite.split, **counts}, ensure_ascii=False))
    print(f"Reporte: {args.output}")
    return 1 if counts["failed"] or counts["error"] or counts["skipped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
