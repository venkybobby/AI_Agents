"""Provider interfaces and built-in provider implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Raised when provider configuration or execution fails."""


@dataclass(frozen=True)
class ProviderRequest:
    """Request passed to a provider."""

    goal: str
    prompt: str


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized provider response."""

    provider: str
    content: str
    dry_run: bool

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "provider": self.provider,
            "content": self.content,
            "dry_run": self.dry_run,
        }


class AgentProvider(Protocol):
    """Provider contract for model-backed or deterministic agents."""

    name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        """Return a provider response for the request."""


class DryRunProvider:
    """Deterministic provider used for local development and tests."""

    name = "dry-run"

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider=self.name,
            content=(
                "Dry-run provider selected. No external model was called. "
                f"Ready to execute plan for: {request.goal}"
            ),
            dry_run=True,
        )


class OpenAIProvider:
    """OpenAI Responses API provider.

    The OpenAI dependency is imported lazily so local dry-run usage does not
    require installing provider extras.
    """

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        max_output_tokens: int,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._client = client or self._build_client(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        try:
            response = self._client.responses.create(
                model=self._model,
                input=request.prompt,
                max_output_tokens=self._max_output_tokens,
            )
        except Exception as exc:  # pragma: no cover - SDK-specific subclasses vary.
            raise ProviderError(f"OpenAI provider request failed: {exc}") from exc

        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("OpenAI provider returned an empty text response")

        return ProviderResponse(
            provider=self.name,
            content=content.strip(),
            dry_run=False,
        )

    @staticmethod
    def _build_client(
        *, api_key: str, timeout_seconds: float, max_retries: int
    ) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "OpenAI provider requires the optional dependency: "
                'python -m pip install -e ".[openai]"'
            ) from exc

        return OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )


def provider_from_name(name: str) -> AgentProvider:
    """Create a provider by name."""

    normalized_name = name.strip().lower()
    if normalized_name in {"", "dry-run", "dry_run", "dryrun"}:
        return DryRunProvider()
    if normalized_name == "openai":
        from .config import load_openai_settings

        settings = load_openai_settings()
        return OpenAIProvider(
            api_key=settings.api_key,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
            max_retries=settings.max_retries,
            max_output_tokens=settings.max_output_tokens,
        )

    raise ProviderError(
        f"unsupported provider '{name}'. Available providers: dry-run, openai"
    )


def provider_from_env() -> AgentProvider:
    """Create provider using environment configuration."""

    return provider_from_name(os.getenv("AI_AGENTS_PROVIDER", "dry-run"))
