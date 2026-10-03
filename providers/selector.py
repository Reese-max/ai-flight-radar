"""Provider selection. ``RADAR_PRIMARY_PROVIDER`` picks the engine; the safe
default stays ``fast_flights`` until runtime calibration (Issue #8) passes."""
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


def get_provider_chain() -> list:
    """Primary then optional explicit fallback, per migration env config."""
    primary = os.environ.get("RADAR_PRIMARY_PROVIDER")
    fallback = os.environ.get("RADAR_FALLBACK_PROVIDER")
    names = []
    if primary and primary.strip():
        names.append(primary.strip())
    if fallback and fallback.strip() and fallback.strip() != (primary or "").strip():
        names.append(fallback.strip())
    if not names:
        names = ["fast_flights"]
    return [get_provider(name) for name in names]
