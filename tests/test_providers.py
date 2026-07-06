import pytest

from ai_agents.providers import (
    DryRunProvider,
    ProviderError,
    ProviderRequest,
    provider_from_name,
)


def test_dry_run_provider_returns_normalized_response():
    provider = DryRunProvider()

    response = provider.complete(
        ProviderRequest(goal="ship MVP", prompt="Goal: ship MVP")
    )

    assert response.provider == "dry-run"
    assert response.dry_run is True
    assert "No external model was called" in response.content


def test_provider_from_name_accepts_dry_run_aliases():
    assert provider_from_name("dry-run").name == "dry-run"
    assert provider_from_name("dry_run").name == "dry-run"
    assert provider_from_name("").name == "dry-run"


def test_provider_from_name_rejects_unknown_provider():
    with pytest.raises(ProviderError, match="unsupported provider"):
        provider_from_name("unknown")
