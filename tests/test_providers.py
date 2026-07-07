import pytest

from ai_agents.providers import (
    DryRunProvider,
    OpenAIProvider,
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


class _FakeResponses:
    def __init__(self, output_text: str):
        self._output_text = output_text
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return type("FakeOpenAIResponse", (), {"output_text": self._output_text})()


class _FakeClient:
    def __init__(self, output_text: str):
        self.responses = _FakeResponses(output_text)


def test_openai_provider_uses_responses_api_shape():
    fake_client = _FakeClient("Provider response")
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1,
        max_retries=0,
        max_output_tokens=123,
        client=fake_client,
    )

    response = provider.complete(
        ProviderRequest(goal="ship MVP", prompt="Goal: ship MVP")
    )

    assert response.provider == "openai"
    assert response.content == "Provider response"
    assert response.dry_run is False
    assert fake_client.responses.last_request == {
        "model": "gpt-test",
        "input": "Goal: ship MVP",
        "max_output_tokens": 123,
    }


def test_openai_provider_rejects_empty_text_response():
    provider = OpenAIProvider(
        api_key="test-key",
        model="gpt-test",
        timeout_seconds=1,
        max_retries=0,
        max_output_tokens=123,
        client=_FakeClient(""),
    )

    with pytest.raises(ProviderError, match="empty text response"):
        provider.complete(ProviderRequest(goal="ship MVP", prompt="Goal: ship MVP"))
