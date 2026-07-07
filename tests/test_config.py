import pytest

from ai_agents.config import load_openai_settings
from ai_agents.providers import ProviderError


def test_load_openai_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="OPENAI_API_KEY is required"):
        load_openai_settings()


def test_load_openai_settings_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "1")
    monkeypatch.setenv("OPENAI_MAX_OUTPUT_TOKENS", "400")

    settings = load_openai_settings()

    assert settings.api_key == "test-key"
    assert settings.model == "gpt-test"
    assert settings.timeout_seconds == 12.5
    assert settings.max_retries == 1
    assert settings.max_output_tokens == 400


def test_load_openai_settings_rejects_invalid_timeout(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "0")

    with pytest.raises(ProviderError, match="must be greater than 0"):
        load_openai_settings()
