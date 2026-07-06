"""Provider interfaces and built-in provider implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


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


def provider_from_name(name: str) -> AgentProvider:
    """Create a provider by name."""

    normalized_name = name.strip().lower()
    if normalized_name in {"", "dry-run", "dry_run", "dryrun"}:
        return DryRunProvider()

    raise ProviderError(
        f"unsupported provider '{name}'. Available providers: dry-run"
    )


def provider_from_env() -> AgentProvider:
    """Create provider using environment configuration."""

    return provider_from_name(os.getenv("AI_AGENTS_PROVIDER", "dry-run"))
