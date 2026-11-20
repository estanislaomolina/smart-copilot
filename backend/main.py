"""API de extracción mock parcial, salud y contratos."""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.domain.models import (
    AnalysisRequest, AnalysisResult, CallCard, ErrorResponse, HealthResponse,
)
from backend.providers.base import ExtractionProvider, ProviderError
from backend.providers.mock import MockExtractionProvider


def get_provider() -> ExtractionProvider:
    return MockExtractionProvider()


def create_app() -> FastAPI:
    if os.getenv("LLM_PROVIDER", "mock") != "mock":
        raise RuntimeError("Por ahora solo está implementado LLM_PROVIDER=mock.")

    app = FastAPI(
        title="Smart Copilot",
        version="0.2.0",
        description="Extracción mock parcial de ubicación y categoría. Panel y persistencia pendientes.",
    )

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

    @app.get("/", tags=["service"])
    def root() -> dict[str, str]:
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
            for model in (AnalysisRequest, AnalysisResult, CallCard, ErrorResponse)
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

    return app


app = create_app()
