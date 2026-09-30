"""Provider selection. ``RADAR_PRIMARY_PROVIDER`` picks the engine; the safe
default stays ``fast_flights`` until runtime calibration (Issue #8) passes.
``RADAR_FALLBACK_PROVIDER`` names the explicit fallback used by tooling that
compares providers — collection never silently falls over mid-task."""
import os

from providers.base import BaseFlightProvider


def get_provider(name: str = None) -> BaseFlightProvider:
    name = (name or os.environ.get("RADAR_PRIMARY_PROVIDER") or "fast_flights").strip()
    if name in ("fli", "fli_custom"):
        from providers.fli_custom import FliCustomProvider
        return FliCustomProvider()
    if name == "fast_flights":
        from providers.fast_flights_impl import FastFlightsProvider
        return FastFlightsProvider()
    raise ValueError(f"Unknown provider: {name!r} (expected 'fast_flights' or 'fli')")


def get_fallback_provider(name: str = None) -> BaseFlightProvider:
    """The provider consulted when the primary is unavailable or being calibrated."""
    name = (name or os.environ.get("RADAR_FALLBACK_PROVIDER") or "fast_flights").strip()
    return get_provider(name)
