"""API de extracción mock parcial, salud y contratos."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from backend.domain.models import (
    AnalysisRequest, AnalysisResult, CallCard, Category, ErrorResponse, HealthResponse,
)
from backend.providers.base import ExtractionProvider, ProviderError
from backend.providers.mock import MockExtractionProvider
from backend.providers.checklist_mock import MockChecklistEvaluator
from backend.protocols.catalog import ProtocolCatalog
from backend.protocols.engine import ProtocolEngine
from backend.protocols.models import (
    ProtocolDefinition, ProtocolError, ProtocolRequest, ProtocolResult, ProtocolSummary,
)


def get_provider() -> ExtractionProvider:
    return MockExtractionProvider()


def create_app(frontend_dir: Path | None = None) -> FastAPI:
    if os.getenv("LLM_PROVIDER", "mock") != "mock":
        raise RuntimeError("Por ahora solo está implementado LLM_PROVIDER=mock.")

    app = FastAPI(
        title="Smart Copilot",
        version="0.4.0",
        description="Panel de operador, mock y protocolos de demostración. Persistencia pendiente.",
    )

    catalog = ProtocolCatalog()
    engine = ProtocolEngine(catalog, MockChecklistEvaluator())

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
        return {"service": "smart-copilot", "stage": "mock_analysis",
                "health": "/health", "docs": "/docs", "contracts": "/contracts",
                "analyze": "/api/analyze"}

    @app.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse()

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
