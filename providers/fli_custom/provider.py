"""FliCustomProvider — AI Flight Radar adapter over the vendored Fli engine.

Upstream Fli lives verbatim in ``third_party/fli/`` (see ``docs/UPSTREAM_FLI.md``);
all customization stays in this package so upstream diffs remain trivial. Locally
authored. The outer collector task budget stays authoritative; Fli's own bounded
retry (3 attempts) and global 10 req/s limiter apply underneath it.
"""
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from config.settings import settings
from providers.base import BaseFlightProvider, StandardFlightOffer
from providers.rate_limiter import rate_limiter
from providers.fli_custom.errors import FliProviderError
from providers.fli_custom import mapper

logger = logging.getLogger(__name__)

# Round-trip expansion issues one follow-up request per candidate; keep the
# per-task request count small so a 90s collector timeout still covers it.
TOP_N = 3

_MAX_STOPS = None  # resolved lazily after the vendored package is importable


def _ensure_fli_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "third_party" / "fli"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _load_engine():
    """Import the vendored Fli package lazily so --help/tests stay light."""
    _ensure_fli_path()
    os.environ.setdefault("FLI_TIMEOUT", "20")
    from fli.models import (Airport, FlightSearchFilters, FlightSegment,
                            MaxStops, PassengerInfo, SeatType, TripType)
    from fli.search.flights import SearchFlights
    return (Airport, FlightSearchFilters, FlightSegment, MaxStops,
            PassengerInfo, SeatType, TripType, SearchFlights)


class FliCustomProvider(BaseFlightProvider):
    name = "fli_custom"

    def __init__(self):
        self.currency = settings.CURRENCY
        self.language = settings.LANGUAGE
        self.country = "TW"

    def _fetch(self, filters):
        """Isolated engine call — tests monkeypatch this, never the network."""
        *_models, SearchFlights = _load_engine()
        return SearchFlights().search(
            filters, top_n=TOP_N,
            currency=self.currency, language=self.language, country=self.country)

    def search(self, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, max_stops: int = 0
               ) -> List[StandardFlightOffer]:
        try:
            (Airport, FlightSearchFilters, FlightSegment, MaxStops,
             PassengerInfo, SeatType, TripType, _search) = _load_engine()
            stops = {0: MaxStops.NON_STOP, 1: MaxStops.ONE_STOP_OR_FEWER}.get(
                max_stops, MaxStops.TWO_OR_FEWER_STOPS)
            segments = [FlightSegment(departure_airport=[[Airport[origin], 0]],
                                      arrival_airport=[[Airport[destination], 0]],
                                      travel_date=depart_date)]
            if return_date:
                segments.append(FlightSegment(departure_airport=[[Airport[destination], 0]],
                                              arrival_airport=[[Airport[origin], 0]],
                                              travel_date=return_date))
            filters = FlightSearchFilters(
                trip_type=TripType.ROUND_TRIP if return_date else TripType.ONE_WAY,
                passenger_info=PassengerInfo(adults=1),
                flight_segments=segments, stops=stops, seat_type=SeatType.ECONOMY)
        except (KeyError, ValueError, TypeError) as exc:
            raise FliProviderError(f"Cannot build search filters: {type(exc).__name__}") from exc

        rate_limiter.wait()
        try:
            raw = self._fetch(filters)
        except Exception as exc:
            rate_limiter.record_error()
            raise FliProviderError(
                f"Upstream search failed ({type(exc).__name__}); no price observation recorded"
            ) from exc

        if not raw:
            rate_limiter.record_success()
            return []

        ctx = {"origin": origin, "destination": destination,
               "depart_date": depart_date, "return_date": return_date,
               "trip_type": "round-trip" if return_date else "one-way",
               "max_stops": max_stops}
        offers = []
        for row in raw:
            try:
                offers.append(mapper.map_result(row, ctx))
            except (AttributeError, TypeError, ValueError) as exc:
                logger.warning("Rejected malformed Fli result: %s", type(exc).__name__)
        if not offers:
            rate_limiter.record_error()
            raise FliProviderError("Upstream returned results, but none could be validated")
        rate_limiter.record_success()
        return sorted(offers, key=lambda offer: offer.price_twd)
