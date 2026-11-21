"""Adaptador Anthropic: salida estructurada, evidencia local y errores acotados."""
import json
import time
from typing import TypeVar

import anthropic
import httpx
from pydantic import BaseModel, ValidationError

from backend.providers.base import ProviderError
from backend.providers.config import ProviderSettings

T = TypeVar("T", bound=BaseModel)


class HaikuGateway:
    def __init__(self, settings: ProviderSettings, client: anthropic.Anthropic | None = None):
        self.settings = settings
        self.client = client or anthropic.Anthropic(
            api_key=settings.api_key.get_secret_value(), max_retries=0,
            timeout=httpx.Timeout(settings.timeout, connect=min(5, settings.timeout)),
        )

    def close(self):
        self.client.close()

    def complete(self, schema: type[T], system: str, payload: dict) -> T:
        for attempt in range(self.settings.retries + 1):
            try:
                response = self.client.messages.parse(
                    model=self.settings.model, max_tokens=6000, temperature=0,
                    system=system, messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                    output_format=schema,
                )
                if response.stop_reason != "end_turn" or response.parsed_output is None:
                    raise ProviderError("invalid_provider_output", "Salida incompleta o rechazada.")
                return schema.model_validate(response.parsed_output.model_dump(), context=payload)
            except anthropic.APITimeoutError:
                code, transient = "provider_timeout", True
            except anthropic.APIConnectionError:
                code, transient = "provider_unavailable", True
            except anthropic.APIStatusError as error:
                code = "provider_unavailable"
                transient = error.status_code in (408, 409, 429) or error.status_code >= 500
            except (ValidationError, ValueError, anthropic.APIResponseValidationError) as error:
                raise ProviderError("invalid_provider_output", "Salida estructurada inválida.") from error
            if not transient or attempt == self.settings.retries:
                # Nunca exponer cuerpo, prompt, transcripción ni credenciales del error remoto.
                raise ProviderError(code, "No se pudo consultar Haiku.", retryable=transient) from None
            time.sleep(.25)
        raise AssertionError("Bucle de reintentos agotado")
