"""Typed failures for the Fli-derived provider. Locally authored."""

from providers.base import ProviderSearchError


class FliProviderError(RuntimeError):
    """A typed Fli adapter error, including local request/configuration errors."""


class FliSearchError(FliProviderError, ProviderSearchError):
    """A provider execution failure eligible for configured fallback."""
