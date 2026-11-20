"""API inicial: salud y contratos; aún sin extracción ni persistencia."""

import os

from fastapi import FastAPI

from backend.domain.models import (
    AnalysisRequest, AnalysisResult, CallCard, ErrorResponse, HealthResponse,
)


def create_app() -> FastAPI:
    # Evita aparentar que un proveedor real funciona antes de implementarlo.
    provider = os.getenv("LLM_PROVIDER", "mock")
    if provider != "mock":
        raise RuntimeError("Este hito solo admite LLM_PROVIDER=mock; no hay extractor aún.")

    app = FastAPI(
        title="Smart Copilot",
        version="0.1.0",
        description="Base del servicio. Extracción, panel y persistencia aún pendientes.",
    )

    @app.get("/", tags=["service"])
    def root() -> dict[str, str]:
        return {"service": "smart-copilot", "stage": "foundation",
                "health": "/health", "docs": "/docs", "contracts": "/contracts"}

    @app.get("/health", response_model=HealthResponse, tags=["service"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/contracts", tags=["contracts"])
    def contracts() -> dict:
        return {
            model.__name__: model.model_json_schema()
            for model in (AnalysisRequest, AnalysisResult, CallCard, ErrorResponse)
        }

    return app


app = create_app()
