"""Contrato común del mock y del proveedor LLM; todavía sin implementaciones."""

from typing import Literal, Protocol

from backend.domain.models import AnalysisRequest, AnalysisResult


class ExtractionProvider(Protocol):
    name: Literal["mock", "real"]

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Devuelve datos validados y evidencia sobre el texto original."""
        ...


class ProviderError(Exception):
    """Fallo esperado que la capa HTTP puede traducir a ErrorResponse."""

    def __init__(
        self,
        code: Literal["provider_unavailable", "provider_timeout", "invalid_provider_output"],
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
