"""Provider selection. ``RADAR_PRIMARY_PROVIDER`` picks the engine; the safe
default stays ``fast_flights`` until runtime calibration (Issue #8) passes."""
import os
from typing import Iterable, Tuple

from providers.base import BaseFlightProvider, ProviderSearchError, StandardFlightOffer

_SAFE_DEFAULT_PROVIDER = "fast_flights"
_PROVIDER_NAMES = {"fast_flights", "fli", "fli_custom"}
_CANONICAL_NAMES = {"fli": "fli_custom", "fli_custom": "fli_custom",
                    "fast_flights": "fast_flights"}


def _provider_name(value: str, setting: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Invalid {setting}; expected a configured provider name")
    name = value.strip().lower()
    if name not in _PROVIDER_NAMES:
        raise ValueError(f"Invalid {setting}; expected a configured provider name")
    return _CANONICAL_NAMES[name]


def get_provider(name: str = None) -> BaseFlightProvider:
    configured = name if name is not None else os.environ.get("RADAR_PRIMARY_PROVIDER")
    selected = _provider_name(configured or _SAFE_DEFAULT_PROVIDER, "provider")
    if selected == "fli_custom":
        from providers.fli_custom import FliCustomProvider
        return FliCustomProvider()
    if selected == "fast_flights":
        from providers.fast_flights_impl import FastFlightsProvider
        return FastFlightsProvider()
    raise AssertionError("Provider configuration validation missed a supported name")


def get_provider_chain() -> list:
    """Build the configured primary/fallback chain without changing safe defaults."""
    primary = _provider_name(
        os.environ.get("RADAR_PRIMARY_PROVIDER") or _SAFE_DEFAULT_PROVIDER,
        "RADAR_PRIMARY_PROVIDER",
    )
    fallback_value = os.environ.get("RADAR_FALLBACK_PROVIDER")
    names = [primary]
    if fallback_value and fallback_value.strip():
        fallback = _provider_name(fallback_value, "RADAR_FALLBACK_PROVIDER")
        if fallback != primary:
            names.append(fallback)
    return [get_provider(name) for name in names]


class ProviderChainError(ProviderSearchError):
    """All configured providers failed; keep each typed cause available."""

    def __init__(self, failures: Iterable[Tuple[str, ProviderSearchError]]):
        self.failures = tuple(failures)
        summary = ", ".join(
            f"{name}={type(error).__name__}" for name, error in self.failures
        )
        super().__init__(f"All configured flight providers failed ({summary})")


def search_with_provider_chain(origin: str, destination: str, depart_date: str,
                               return_date: str = None, max_stops: int = 0
                               ) -> list[StandardFlightOffer]:
    """Try the explicit fallback only after a typed provider failure.

    An empty list is a successful NO_RESULTS response and stops the chain.
    Unexpected programming/configuration errors propagate without being hidden.
    """
    failures = []
    providers = get_provider_chain()
    for provider in providers:
        name = getattr(provider, "name", type(provider).__name__)
        try:
            return provider.search(origin, destination, depart_date,
                                   return_date, max_stops=max_stops)
        except ProviderSearchError as exc:
            failures.append((name, exc))
    if not failures:
        raise ProviderChainError([])
    if len(failures) == 1:
        raise failures[0][1]
    raise ProviderChainError(failures) from failures[-1][1]
