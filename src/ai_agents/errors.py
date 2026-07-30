"""Shared package exceptions."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Raised when provider configuration or execution fails."""
