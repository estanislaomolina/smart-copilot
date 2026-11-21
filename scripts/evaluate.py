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
from typing import Callable, Literal
from statistics import median

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
    focus: NonBlank | None = None
    review_notes: list[NonBlank] = Field(default_factory=list)
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


def compare(case: Case, data: IncidentData, protocol: ProtocolResult | None) -> list[dict]:
    """Comparaciones literales: no usar un juez LLM ni inferir equivalencias."""
    checks = []
    for path, expected in case.fields.items():
        field = data
        for part in path.split("."):
            field = getattr(field, part)
        checks.append({"kind": "field", "target": path, "expected": expected, "actual": field.value,
                       "passed": field.value == expected})
    if protocol is None:
        return checks
    by_text = {q.text: q for q in protocol.questions}
    for expected in case.questions:
        actual = by_text.get(expected.text)
        checks.append({"kind": "question_status", "target": expected.text + " / status", "expected": expected.status,
                       "actual": actual.status if actual else None,
                       "passed": actual is not None and actual.status == expected.status})
        if expected.answer is not None:
            answer = actual.answer if actual else None
            # Solo mayúsculas y espacios; no equipara paráfrasis.
            checks.append({"kind": "question_answer", "target": expected.text + " / answer", "expected": expected.answer,
                           "actual": answer, "passed": answer is not None
                           and answer.strip().casefold() == expected.answer.strip().casefold()})
    return checks


def review_entries(data: IncidentData, protocol: ProtocolResult | None) -> list[dict]:
    """Unidades de revisión humana, no afirmaciones atómicas ni juicios automáticos."""
    fields = [(key, getattr(data, key)) for key in ("category", "subcategory", "priority", "summary")]
    fields += [("location." + key, value) for key, value in data.location]
    fields += [(f"risks.{i}", value) for i, value in enumerate(data.risks)]
    entries = []
    for target, value in fields:
        if value.value is not None:
            entries.append({"target": target, **value.model_dump(),
                            "verdict": "pending", "reviewer_notes": ""})
    for question in protocol.questions if protocol else []:
        if question.status != "pending":
            entries.append({"target": "question." + question.id, "text": question.text,
                            "value": {"status": question.status, "answer": question.answer},
                            "origin": question.origin, "rationale": question.rationale,
                            "evidence": [e.model_dump() for e in question.evidence],
                            "verdict": "pending", "reviewer_notes": ""})
    return entries


def summarize_review(results: list[dict]) -> dict:
    counts = {key: 0 for key in ("pending", "supported", "unsupported", "uncertain")}
    for result in results:
        for entry in result.get("human_review", {}).get("entries", []):
            verdict = entry.get("verdict", "pending")
            if verdict not in counts:
                raise ValueError("Veredicto de revisión no permitido.")
            counts[verdict] += 1
    return {"unit": "Entradas de revisión; pueden contener varias afirmaciones.",
            "total": sum(counts.values()), **counts}


def summarize(results: list[dict]) -> dict:
    groups = {}
    errors = {}
    for result in results:
        if result.get("code"):
            errors[result["code"]] = errors.get(result["code"], 0) + 1
        for check in result.get("checks", []):
            key = ("location" if check["target"].startswith("location.") else
                   check["target"] if check["kind"] == "field" else check["kind"])
            group = groups.setdefault(key, {"compared": 0, "matched": 0})
            group["compared"] += 1
            group["matched"] += int(check["passed"])
    latency = {}
    for stage in ("extraction", "checklist", "total"):
        values = [r["timings_seconds"][stage] for r in results
                  if r.get("timings_seconds", {}).get(stage) is not None]
        latency[stage] = ({"samples": len(values), "min": min(values),
                           "median": round(median(values), 6), "max": max(values)} if values else None)
    locations = [[c for c in r.get("checks", []) if c["target"].startswith("location.")]
                 for r in results]
    locations = [checks for checks in locations if checks]
    return {"literal_comparisons": groups,
            "location_cases": {"with_compared_fields": len(locations),
                               "all_compared_fields_matched": sum(all(c["passed"] for c in checks)
                                                                 for checks in locations)},
            "errors_by_code": errors,
            "terminal_invalid_outputs": errors.get("invalid_provider_output", 0),
            "latency_seconds": latency, "human_review": summarize_review(results)}


async def evaluate(
    suite: Suite, provider: ExtractionProvider, engine: ProtocolEngine,
    request_count: Callable[[], int] | None = None,
) -> list[dict]:
    results = []
    stopped = False
    for case in suite.cases:
        if stopped:
            results.append({"id": case.id, "status": "skipped", "reason": "provider_rate_limited"})
            continue
        start = time.monotonic()
        timings = {"extraction": None, "checklist": None, "total": None}
        attempts = {"extraction": None, "checklist": None}
        stage = "extraction"
        analysis, protocol = None, None
        result = {"id": case.id}
        try:
            stage_start = time.monotonic()
            before = request_count() if request_count else None
            try:
                # Solo la transcripción: nunca expectativas, IDs ni notas de revisión.
                analysis = await provider.analyze(AnalysisRequest(transcript=case.transcript))
                analysis.data.validate_transcript(case.transcript, allow_operator=False)
            finally:
                timings[stage] = round(time.monotonic() - stage_start, 6)
                attempts[stage] = request_count() - before if request_count else None
            stage = "checklist"
            stage_start = time.monotonic()
            before = request_count() if request_count else None
            try:
                protocol = engine.apply(ProtocolRequest(request=analysis.request, data=analysis.data))
            finally:
                timings[stage] = round(time.monotonic() - stage_start, 6)
                attempts[stage] = request_count() - before if request_count else None
            checks = compare(case, analysis.data, protocol)
            result.update(status="passed" if all(c["passed"] for c in checks) else "failed", checks=checks)
        except ProviderError as error:
            result.update(status="error", stage=stage, code=error.code,
                          checks=compare(case, analysis.data, None) if analysis else [])
            stopped = error.code == "provider_rate_limited"
        timings["total"] = round(time.monotonic() - start, 6)
        result.update(timings_seconds=timings, request_attempts=attempts,
                      retries={key: max(0, value - 1) if value is not None else None
                               for key, value in attempts.items()},
                      selected_protocol=protocol.protocol.id if protocol and protocol.protocol else None,
                      human_review={"status": "pending" if analysis else "unavailable",
                                    "case_notes": case.review_notes,
                                    "entries": review_entries(analysis.data, protocol) if analysis else []})
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "data/evaluation/development.json")
    parser.add_argument("--provider", choices=("mock", "groq"), default="mock",
                        help="Mock por defecto, incluso si el entorno selecciona Groq.")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/evaluation/development.json")
    parser.add_argument("--case", dest="case_ids", action="append",
                        help="Seleccionar un ID; se puede repetir.")
    parser.add_argument("--limit", type=int, default=2, help="Máximo de casos por corrida (por defecto 2).")
    parser.add_argument("--summarize-review", type=Path,
                        help="Contar veredictos de un reporte revisado; no ejecuta proveedores.")
    args = parser.parse_args()
    if args.summarize_review:
        report = json.loads(args.summarize_review.read_text(encoding="utf-8"))
        print(json.dumps(summarize_review(report["results"]), ensure_ascii=False, indent=2))
        return 0
    if args.limit < 1:
        parser.error("--limit debe ser positivo.")
    if args.output.resolve() == args.cases.resolve():
        parser.error("El reporte no puede sobrescribir los casos de entrada.")
    raw = args.cases.read_bytes()
    suite = Suite.model_validate_json(raw)
    available = suite.cases
    if args.case_ids:
        unknown = set(args.case_ids) - {case.id for case in available}
        if unknown:
            parser.error("IDs inexistentes: " + ", ".join(sorted(unknown)))
        available = [case for case in available if case.id in args.case_ids]
    selected = suite.model_copy(update={"cases": available[:args.limit]})
    gateway = None
    request_attempts = [0]
    def count_request(_request):
        request_attempts[0] += 1
    model = None
    if args.provider == "mock":
        provider, evaluator = MockExtractionProvider(), MockChecklistEvaluator()
    else:
        from backend.providers.config import ProviderSettings
        from backend.providers.groq import GroqGateway
        from backend.providers.llm import LLMExtractionProvider, LLMChecklistEvaluator
        # La selección explícita del CLI tiene precedencia; las credenciales siguen locales.
        os.environ["LLM_PROVIDER"] = "groq"
        import httpx
        # Evaluación conservadora: un solo intento por etapa, sin corrección automática.
        settings = ProviderSettings.from_env().model_copy(update={"retries": 0})
        client = httpx.Client(timeout=httpx.Timeout(settings.timeout, connect=min(5, settings.timeout)),
                              follow_redirects=False, event_hooks={"request": [count_request]})
        gateway = GroqGateway(settings, client)
        model = settings.model
        provider, evaluator = LLMExtractionProvider(gateway), LLMChecklistEvaluator(gateway)
    try:
        results = asyncio.run(evaluate(selected, provider, ProtocolEngine(ProtocolCatalog(), evaluator),
                                       request_count=lambda: request_attempts[0]))
    finally:
        if gateway:
            gateway.close()
    counts = {status: sum(r["status"] == status for r in results)
              for status in ("passed", "failed", "error", "skipped")}
    report = {
        "report_version": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "selected_case_ids": [case.id for case in selected.cases],
        "not_selected": len(suite.cases) - len(selected.cases),
        "split": suite.split, "description": suite.description,
        "cases_sha256": hashlib.sha256(raw).hexdigest(),
        "provider": args.provider, "model": model,
        "prompt_version": PROMPT_VERSION if gateway else None,
        "configuration": ({"reasoning_effort": settings.reasoning_effort,
                           "timeout_seconds": settings.timeout, "max_retries": settings.retries}
                          if gateway else {}),
        "comparison": "Valores exactos; respuestas ignoran solo mayúsculas y espacios exteriores.",
        "usage": None, "usage_note": "El contrato actual no expone consumo; no se estima.",
        "counts": counts, "summary": summarize(results), "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"provider": args.provider, "split": suite.split, **counts}, ensure_ascii=False))
    print(f"Reporte: {args.output}")
    return 1 if counts["failed"] or counts["error"] or counts["skipped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
