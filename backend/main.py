"""API de extracción mock parcial, salud y contratos."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend.calls.models import CallStoreError
from backend.calls.routes import call_routes
from backend.calls.store import CallStore

from backend.domain.models import (
    AnalysisRequest, AnalysisResult, CallCard, Category, ErrorResponse, HealthResponse,
)
from backend.providers.base import ExtractionProvider, ProviderError
from backend.providers.config import ProviderSettings
from backend.providers.haiku import HaikuGateway
from backend.providers.groq import GroqGateway
from backend.providers.llm import LLMExtractionProvider, LLMChecklistEvaluator
from backend.providers.mock import MockExtractionProvider
from backend.providers.checklist_mock import MockChecklistEvaluator
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.protocols.models import (
    ProtocolDefinition, ProtocolError, ProtocolRequest, ProtocolResult, ProtocolSummary,
)


def get_provider(request: Request) -> ExtractionProvider:
    return request.app.state.provider


def create_app(frontend_dir: Path | None = None, db_path: Path | None = None) -> FastAPI:
    settings = ProviderSettings.from_env()
    gateway = (GroqGateway(settings) if settings.provider == "groq" else
               HaikuGateway(settings) if settings.provider == "haiku" else None)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            if gateway:
                gateway.close()

    app = FastAPI(
        title="Smart Copilot",
        version="0.6.0", lifespan=lifespan,
        description="Panel de operador, cartas persistidas y derivación CAD simulada.",
    )

    catalog = ProtocolCatalog()
    app.state.provider = LLMExtractionProvider(gateway) if gateway else MockExtractionProvider()
    evaluator = LLMChecklistEvaluator(gateway) if gateway else MockChecklistEvaluator()
    engine = ProtocolEngine(catalog, evaluator)
    store = CallStore(db_path or Path(os.getenv("CALLS_DB_PATH", "data/private/calls.sqlite3")), catalog)
    app.include_router(call_routes(store))

    @app.exception_handler(CallStoreError)
    async def call_error(_request: Request, error: CallStoreError) -> JSONResponse:
        status, message = {
            "call_not_found": (404, "Llamada no encontrada."),
            "revision_conflict": (409, "Hay una versión más reciente. Recuperá la llamada antes de guardar."),
            "review_required": (409, "La carta requiere revisión explícita antes de derivar."),
            "invalid_call": (422, "Revisá protocolo, checklist y turnos sin incorporar antes de confirmar la carta."),
        }[error.code]
        return JSONResponse(status_code=status, content=ErrorResponse(code=error.code, message=message).model_dump())

    @app.exception_handler(ProtocolError)
    async def protocol_error(_request: Request, error: ProtocolError) -> JSONResponse:
        status, message = {
            "protocol_not_found": (404, "Protocolo no encontrado."),
            "protocol_category_mismatch": (409, "El protocolo no corresponde a la categoría; revisar los datos."),
        }[error.code]
        return JSONResponse(status_code=status, content=ErrorResponse(
            code=error.code, message=message,
        ).model_dump())

    @app.exception_handler(RequestValidationError)
    async def invalid_input(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # No repetir la transcripción ni otros valores de entrada en los errores.
        error = ErrorResponse(code="invalid_input", message="Entrada inválida; revisar el esquema en /docs.")
        return JSONResponse(status_code=422, content=error.model_dump())

    @app.exception_handler(ProviderError)
    async def provider_error(_request: Request, error: ProviderError) -> JSONResponse:
        status, message = {
            "provider_timeout": (504, "El proveedor excedió el tiempo de espera."),
            "provider_rate_limited": (429, "Se alcanzó el límite del proveedor. Esperá antes de reintentar o continuá manualmente."),
            "provider_unavailable": (503, "El proveedor no está disponible."),
            "invalid_provider_output": (502, "El proveedor devolvió un resultado inválido."),
        }[error.code]
        response = ErrorResponse(code=error.code, message=message, retryable=error.retryable)
        return JSONResponse(status_code=status, content=response.model_dump())

    # En Docker el build está junto al backend; en desarrollo Vite sirve el panel.
    panel_dir = frontend_dir if frontend_dir is not None else Path(__file__).resolve().parents[1] / "frontend/dist"
    if (panel_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=panel_dir / "assets"), name="panel-assets")

    @app.get("/", tags=["service"], response_model=None)
    def root() -> FileResponse | dict[str, str]:
        if (panel_dir / "index.html").is_file():
            return FileResponse(panel_dir / "index.html", headers={"Cache-Control": "no-store"})
        return {"service": "smart-copilot", "stage": "llm_analysis" if gateway else "mock_analysis",
                "health": "/health", "docs": "/docs", "contracts": "/contracts",
                "analyze": "/api/analyze"}

    @app.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse(stage="llm_analysis" if gateway else "mock_analysis", configured_provider=settings.provider,
                              configured_model=settings.model if gateway else None)

    @app.get("/api/config", response_model=HealthResponse, tags=["service"])
    def provider_config() -> HealthResponse:
        return health()

    @app.get("/contracts", tags=["contracts"])
    def contracts() -> dict:
        return {
            model.__name__: model.model_json_schema()
            for model in (AnalysisRequest, AnalysisResult, CallCard, ErrorResponse,
                          ProtocolRequest, ProtocolResult)
        }

    @app.post("/api/analyze", response_model=AnalysisResult, tags=["analysis"],
              responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse},
                         503: {"model": ErrorResponse}, 504: {"model": ErrorResponse}})
    async def analyze(
        request: AnalysisRequest,
        provider: Annotated[ExtractionProvider, Depends(get_provider)],
    ) -> AnalysisResult:
        try:
            result = AnalysisResult.model_validate(await provider.analyze(request))
            if result.request.transcript != request.transcript:
                raise ValueError("El proveedor cambió la transcripción original.")
            return result
        except (ValidationError, ValueError) as exc:
            raise ProviderError("invalid_provider_output", "Salida inválida.") from exc

    @app.get("/api/protocols", response_model=list[ProtocolSummary], tags=["protocols"])
    def list_protocols(category: Category | None = None) -> list[ProtocolSummary]:
        return catalog.summaries(category)

    @app.get("/api/protocols/{protocol_id}", response_model=ProtocolDefinition, tags=["protocols"],
             responses={404: {"model": ErrorResponse}})
    def get_protocol(protocol_id: str) -> ProtocolDefinition:
        return catalog.get(protocol_id)

    @app.post("/api/protocols/apply", response_model=ProtocolResult, tags=["protocols"],
              responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse},
                         422: {"model": ErrorResponse}})
    def apply_protocol(request: ProtocolRequest) -> ProtocolResult:
        return engine.apply(request)

    return app


app = create_app()
