"""Corrida pausada del CSV conocido; resultados inmutables por caso, sin filtrar etiquetas."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evaluate import Case, Suite, evaluate, summarize
from backend.protocols.catalog import ProtocolCatalog, canonical
from backend.protocols.engine import ProtocolEngine
from backend.providers.checklist_mock import MockChecklistEvaluator
from backend.providers.mock import MockExtractionProvider

COLUMNS = {"id_registro", "transcripcion_cruda", "categoria", "subcategoria",
           "calle_detectada", "altura_detectada", "interseccion_detectada",
           "preguntas_protocolo_mandatorias", "preguntas_respondidas_en_relato",
           "preguntas_pendientes"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def question_keys(value: str) -> set[str]:
    return {canonical(part.split("?", 1)[0] + "?") for part in value.split("|") if "?" in part}


def csv_suite(path: Path) -> tuple[Suite, dict]:
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if not COLUMNS <= set(reader.fieldnames or []):
        raise ValueError("Faltan columnas requeridas del CSV.")
    rows = list(reader)
    if len(rows) != 30:
        raise ValueError("La corrida final requiere los 30 registros completos.")
    cases, references = [], []
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Fila CSV desalineada o incompleta.")
        answered = question_keys(row["preguntas_respondidas_en_relato"])
        pending = question_keys(row["preguntas_pendientes"])
        expectations, unmapped = [], []
        for text in row["preguntas_protocolo_mandatorias"].split("|"):
            text = text.strip()
            if not text:
                continue
            key = canonical(text)
            if (key in answered) != (key in pending):
                expectations.append({"text": text, "status": "answered" if key in answered else "pending"})
            else:
                unmapped.append(text)
        fields = {"category": row["categoria"], "subcategory": row["subcategoria"]}
        for column, target in (("calle_detectada", "location.street"),
                               ("altura_detectada", "location.number"),
                               ("interseccion_detectada", "location.intersection")):
            fields[target] = row[column].strip() or None
        cases.append(Case(id=row["id_registro"], transcript=row["transcripcion_cruda"],
                          fields=fields, questions=expectations,
                          review_notes=["Referencias originales no validadas semánticamente. No interpretar diferencias como precisión.",
                                        "Preguntas ausentes pueden deberse a la selección de protocolo; no se fuerza el subtipo del CSV."]))
        references.append({"id": row["id_registro"],
            "mandatory_questions_without_unambiguous_status_reference": unmapped,
            "csv_annotations": {k: v for k, v in row.items() if k != "transcripcion_cruda"}})
    suite = Suite(split="development",
        description="30 casos SOFLEX conocidos. Comparaciones literales con anotaciones no validadas; no evaluación independiente.",
        cases=cases)
    return suite, {"source_sha256": hashlib.sha256(raw).hexdigest(), "references": references,
                   "not_scored": {"priority": "Modo LLM sin clasificación automática P1-P4.",
                                  "district": "barrio_comuna no equivale necesariamente a localidad/municipio.",
                                  "risks": "Requieren revisión semántica; sin juez LLM."}}


class StopRequested(Exception):
    pass


class RequestGate:
    def __init__(self, interval: float, budget: int, should_stop=lambda: False,
                 clock=time.monotonic, sleep=time.sleep):
        self.interval, self.budget = interval, budget
        self.should_stop, self.clock, self.sleep = should_stop, clock, sleep
        self.last_started = None
        self.count = 0
        self.last_wait = 0.0

    def before_request(self, _request) -> None:
        if self.count >= self.budget:
            raise StopRequested("request_budget")
        start = self.clock()
        remaining = max(0, self.interval - (start - self.last_started)) if self.last_started is not None else 0
        while remaining > 0:
            if self.should_stop():
                raise StopRequested("cancelled")
            self.sleep(min(1, remaining))
            remaining = max(0, self.interval - (self.clock() - self.last_started))
        if self.should_stop():
            raise StopRequested("cancelled")
        self.last_wait = self.clock() - start
        self.last_started = self.clock()
        self.count += 1


def load_previous(report: Path, marker: Path, case_id: str) -> dict | None:
    if report.exists():
        value = json.loads(report.read_text())
        if value["id"] != case_id:
            raise ValueError("El reporte previo no corresponde al caso.")
        return value
    if marker.exists():
        # No repetir una solicitud que pudo haberse enviado antes de una interrupción.
        value = {"id": case_id, "status": "error", "code": "run_interrupted",
                 "checks": [], "request_attempts": {"extraction": None, "checklist": None},
                 "timings_seconds": {"extraction": None, "checklist": None, "total": None}}
        atomic_json(report, value)
        return value
    return None


def run(args) -> int:
    import fcntl
    from backend.providers.config import ProviderSettings
    from backend.providers.llm_prompts import PROMPT_VERSION

    suite, reference = csv_suite(args.dataset)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    lock = (args.output_dir / ".lock").open("a")
    # Mantener el descriptor vivo durante la corrida: un segundo proceso no envía solicitudes.
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest_path = args.output_dir / "manifest.json"
    if manifest_path.exists() and not args.resume:
        raise ValueError("La corrida ya existe; usar otra carpeta o --resume.")
    if any(args.output_dir.glob("case-*.json")) and not manifest_path.exists():
        raise ValueError("Hay reportes sin manifiesto; no se sobrescriben.")
    import os
    os.environ["LLM_PROVIDER"] = args.provider
    settings = ProviderSettings.from_env().model_copy(update={"retries": args.max_retries})
    suite_raw = suite.model_dump_json().encode()
    code_files = {"runner": Path(__file__), "evaluate": Path(__file__).with_name("evaluate.py")}
    from backend.providers import groq, llm_models, llm_prompts
    code_files.update(groq=Path(groq.__file__), models=Path(llm_models.__file__), prompts=Path(llm_prompts.__file__))
    manifest = {"provider": args.provider, "model": settings.model if args.provider == "groq" else None,
                "prompt_version": PROMPT_VERSION if args.provider == "groq" else None,
                "source_sha256": reference["source_sha256"],
                "suite_sha256": hashlib.sha256(suite_raw).hexdigest(),
                "max_retries": args.max_retries, "min_request_interval_seconds": args.interval,
                "max_requests": 30 * 2 * (args.max_retries + 1), "code_revision": args.code_revision,
                "code_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in code_files.items()}}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if any(previous.get(key) != value for key, value in manifest.items()):
            raise ValueError("No se puede retomar con datos, código o configuración distintos.")
    else:
        atomic_json(manifest_path, {**manifest, "created_at": now()})
        atomic_json(args.output_dir / "cases.json", suite.model_dump())
        atomic_json(args.output_dir / "references.json", reference)

    stop = [False]
    def cancel(_signal, _frame):
        stop[0] = True
    previous_signals = {sig: signal.signal(sig, cancel) for sig in (signal.SIGTERM, signal.SIGINT)}
    gate = RequestGate(args.interval if args.provider == "groq" else 0, manifest["max_requests"], lambda: stop[0])
    events = []
    def observe(event):
        events.append({**event, "pacing_wait_seconds": round(gate.last_wait, 6)})
    gateway = None
    if args.provider == "groq":
        import httpx
        from backend.providers.groq import GroqGateway
        from backend.providers.llm import LLMExtractionProvider, LLMChecklistEvaluator
        client = httpx.Client(timeout=httpx.Timeout(settings.timeout, connect=min(5, settings.timeout)),
                              follow_redirects=False, event_hooks={"request": [gate.before_request]})
        gateway = GroqGateway(settings, client, on_attempt=observe)
        provider, evaluator = LLMExtractionProvider(gateway), LLMChecklistEvaluator(gateway)
    else:
        provider, evaluator = MockExtractionProvider(), MockChecklistEvaluator()
    engine = ProtocolEngine(ProtocolCatalog(), evaluator)
    results = []
    state = "running"
    def checkpoint(current=None):
        progress = {"state": state, "updated_at": now(), "total": len(suite.cases),
                    "completed": len(results), "current_case": current,
                    "counts": {s: sum(r["status"] == s for r in results) for s in ("passed", "failed", "error")},
                    "requests_this_process": gate.count}
        atomic_json(args.output_dir / "progress.json", progress)
        atomic_json(args.output_dir / "summary.json",
                    {**manifest, "progress": progress, "summary": summarize(results), "results": results})
    try:
        checkpoint()
        for index, case in enumerate(suite.cases, 1):
            report = args.output_dir / f"case-{index:03}.json"
            marker = args.output_dir / f"case-{index:03}.started"
            old = load_previous(report, marker, case.id)
            if old is not None:
                results.append(old)
                continue
            if stop[0]:
                state = "stopped"
                break
            checkpoint(case.id)
            atomic_json(marker, {"id": case.id, "started_at": now()})
            try:
                selected = suite.model_copy(update={"cases": [case]})
                result = asyncio.run(evaluate(selected, provider, engine, lambda: gate.count, events))[0]
            except StopRequested:
                result = {"id": case.id, "status": "error", "code": "run_interrupted", "checks": [],
                          "timings_seconds": {"extraction": None, "checklist": None, "total": None}}
                state = "stopped"
            except Exception as error:
                result = {"id": case.id, "status": "error", "code": "runner_error",
                          "exception_type": type(error).__name__, "checks": [],
                          "timings_seconds": {"extraction": None, "checklist": None, "total": None}}
                state = "runner_error"
            pacing = {stage: sum(e.get("pacing_wait_seconds", 0) for e in result.get("attempt_diagnostics") or []
                                  if e["schema"] == schema)
                      for stage, schema in (("extraction", "ExtractedIncident"), ("checklist", "EvaluatedChecklist"))}
            result["pacing_wait_seconds"] = pacing
            result["reference_only"] = True
            atomic_json(report, result)
            marker.unlink(missing_ok=True)
            results.append(result)
            if result.get("code") == "provider_rate_limited":
                state = "stopped_rate_limit"
            checkpoint()
            print(json.dumps({"completed": len(results), "total": 30, "id": case.id,
                              "status": result["status"], "code": result.get("code")}), flush=True)
            if state != "running":
                break
        if len(results) == len(suite.cases) and state == "running":
            state = "completed"
    finally:
        if gateway:
            gateway.close()
        checkpoint()
        lock.close()
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)
    print(json.dumps({"state": state, "completed": len(results), "total": 30}), flush=True)
    return 0 if state == "completed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/raw/dataset_challenge_soflex.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=("mock", "groq"), default="mock")
    parser.add_argument("--interval", type=float, default=45, help="Segundos mínimos entre solicitudes Groq.")
    parser.add_argument("--max-retries", type=int, choices=(0, 1), default=1)
    parser.add_argument("--code-revision", default="unrecorded")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.interval < 0 or (args.provider == "groq" and args.interval < 30):
        parser.error("Groq requiere un intervalo mínimo de 30 segundos.")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
