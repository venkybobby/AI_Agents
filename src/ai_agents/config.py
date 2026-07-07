"""Environment-backed configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .providers import ProviderError


@dataclass(frozen=True)
class OpenAISettings:
    """Configuration for the OpenAI provider."""

    api_key: str
    model: str
    timeout_seconds: float
    max_retries: int
    max_output_tokens: int


def load_openai_settings() -> OpenAISettings:
    """Load OpenAI provider settings from environment variables."""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ProviderError(
            "OPENAI_API_KEY is required when AI_AGENTS_PROVIDER=openai"
        )

    return OpenAISettings(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5",
        timeout_seconds=_float_env("OPENAI_TIMEOUT_SECONDS", 30.0),
        max_retries=_int_env("OPENAI_MAX_RETRIES", 2),
        max_output_tokens=_int_env("OPENAI_MAX_OUTPUT_TOKENS", 800),
    )


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ProviderError(f"{name} must be an integer") from exc

    if value < 0:
        raise ProviderError(f"{name} must be greater than or equal to 0")
    return value


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ProviderError(f"{name} must be a number") from exc

    if value <= 0:
        raise ProviderError(f"{name} must be greater than 0")
    return value
