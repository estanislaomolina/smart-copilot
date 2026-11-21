"""Configuración validada; el modo mock no necesita credenciales."""
import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, model_validator

GROQ_MODEL = "openai/gpt-oss-120b"
HAIKU_MODEL = "claude-haiku-4-5-20251001"


class ProviderSettings(BaseModel):
    provider: Literal["mock", "haiku", "groq"] = "mock"
    model: str = Field(min_length=1, pattern=r"\S")
    api_key: SecretStr = SecretStr("")
    timeout: float = Field(default=20, ge=1, le=30)
    retries: int = Field(default=1, ge=0, le=1)
    reasoning_effort: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="before")
    @classmethod
    def default_model(cls, values):
        if isinstance(values, dict) and "model" not in values:
            return {**values, "model": GROQ_MODEL if values.get("provider") == "groq" else HAIKU_MODEL}
        return values

    @classmethod
    def from_env(cls):
        provider = os.getenv("LLM_PROVIDER", "mock")
        if provider not in ("mock", "haiku", "groq"):
            raise RuntimeError("LLM_PROVIDER debe ser mock, groq o haiku.")
        if provider == "mock":
            return cls()
        key_name = "GROQ_API_KEY" if provider == "groq" else "ANTHROPIC_API_KEY"
        model_name = "GROQ_MODEL" if provider == "groq" else "ANTHROPIC_MODEL"
        default_model = GROQ_MODEL if provider == "groq" else HAIKU_MODEL
        settings = cls(provider=provider, model=os.getenv(model_name, default_model),
                       api_key=os.getenv(key_name, ""),
                       timeout=os.getenv("LLM_TIMEOUT_SECONDS", "20"),
                       retries=os.getenv("LLM_MAX_RETRIES", "1"),
                       reasoning_effort=os.getenv("GROQ_REASONING_EFFORT", "medium") if provider == "groq" else "medium")
        if provider == "haiku" and not settings.model.startswith("claude-haiku-"):
            raise RuntimeError("ANTHROPIC_MODEL debe identificar un modelo Claude Haiku.")
        if not settings.api_key.get_secret_value().strip():
            raise RuntimeError(f"LLM_PROVIDER={provider} requiere {key_name}.")
        return settings
