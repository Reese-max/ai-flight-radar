"""Typed failures for the Fli-derived provider. Locally authored."""


class FliProviderError(RuntimeError):
    """Upstream/engine failure — never reported as an empty result."""
