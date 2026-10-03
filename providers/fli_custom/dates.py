"""Bounded flexible-date search over the vendored Fli engine (Issue #8).

A flexible-date query never silently explodes into unbounded per-day requests:
the span is capped by ``max_span_days`` (default one calendar-month window,
under Fli's own 61-day per-query split limit), trip duration must be positive,
and the collector task budget stays authoritative. Locally authored.
"""
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

from providers.fli_custom.errors import FliProviderError
from providers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

MAX_SPAN_DAYS = 61
MAX_RESULTS = 50


class FlexibleDatePrice(BaseModel):
    origin: str
    destination: str
    depart_date: str
    return_date: Optional[str] = None
    price_twd: int
    currency: Optional[str] = None


def _ensure_fli_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "third_party" / "fli"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _load_dates_engine():
    _ensure_fli_path()
    os.environ.setdefault("FLI_TIMEOUT", "20")
    from fli.models import (Airport, DateSearchFilters, FlightSegment,
                            MaxStops, PassengerInfo, SeatType, TripType)
    from fli.search.dates import SearchDates
    return (Airport, DateSearchFilters, FlightSegment, MaxStops,
            PassengerInfo, SeatType, TripType, SearchDates)


def _fetch_dates(filters):
    """Isolated engine call — tests monkeypatch this, never the network."""
    *_models, SearchDates = _load_dates_engine()
    return SearchDates().search(
        filters, currency="TWD", language="zh-TW", country="TW")


def _normalize_row(row, origin: str, destination: str) -> FlexibleDatePrice:
    raw_price = getattr(row, "price", None)
    if raw_price is None:
        raise ValueError("price missing")
    numeric = Decimal(str(raw_price))
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError("Invalid price")
    price = int(numeric.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if price < 1:
        raise ValueError("Price rounds below one TWD")
    date = getattr(row, "date", None)
    if not date:
        raise ValueError("date missing")
    depart = date[0].strftime("%Y-%m-%d") if hasattr(date[0], "strftime") else str(date[0])[:10]
    ret = None
    if len(date) > 1:
        ret = date[1].strftime("%Y-%m-%d") if hasattr(date[1], "strftime") else str(date[1])[:10]
    return FlexibleDatePrice(origin=origin, destination=destination,
                             depart_date=depart, return_date=ret,
                             price_twd=price,
                             currency=getattr(row, "currency", None))


def search_flexible_dates(origin: str, destination: str, from_date: str,
                          to_date: str, trip_duration_days: Optional[int] = None,
                          max_stops: int = 0, cabin: str = "ECONOMY",
                          adults: int = 1, max_span_days: int = MAX_SPAN_DAYS,
                          max_results: int = MAX_RESULTS
                          ) -> List[FlexibleDatePrice]:
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        raise FliProviderError("Bad date range") from exc
    if end < start:
        raise FliProviderError("Empty date range")
    span = (end - start).days + 1
    if span > max_span_days:
        raise FliProviderError(
            f"Flexible-date span {span}d exceeds budget of {max_span_days}d")
    if trip_duration_days is not None and trip_duration_days < 1:
        raise FliProviderError("trip_duration_days must be positive")
    if not isinstance(adults, int) or adults < 1:
        raise FliProviderError("adults must be a positive integer")

    (Airport, DateSearchFilters, _segment, MaxStops,
     PassengerInfo, SeatType, _triptype, _search) = _load_dates_engine()
    try:
        seat = SeatType[cabin.strip().upper()]
        stops = {0: MaxStops.NON_STOP, 1: MaxStops.ONE_STOP_OR_FEWER}.get(
            max_stops, MaxStops.TWO_OR_FEWER_STOPS)
        round_trip = trip_duration_days is not None
        from fli.core.builders import build_date_search_segments
        segments, trip_type = build_date_search_segments(
            origin=Airport[origin], destination=Airport[destination],
            start_date=from_date,
            trip_duration=trip_duration_days if round_trip else None,
            is_round_trip=round_trip)
        filters = DateSearchFilters(
            trip_type=trip_type,
            passenger_info=PassengerInfo(adults=adults),
            flight_segments=segments, stops=stops, seat_type=seat,
            from_date=from_date, to_date=to_date,
            duration=trip_duration_days if round_trip else None)
    except (KeyError, ValueError, TypeError) as exc:
        raise FliProviderError(f"Cannot build date filters: {type(exc).__name__}") from exc

    rate_limiter.wait()
    try:
        raw = _fetch_dates(filters)
    except Exception as exc:
        rate_limiter.record_error()
        raise FliProviderError(
            f"Upstream date search failed ({type(exc).__name__})") from exc

    if not raw:
        rate_limiter.record_success()
        return []
    rows = []
    for row in raw:
        try:
            rows.append(_normalize_row(row, origin, destination))
        except (AttributeError, TypeError, ValueError, InvalidOperation) as exc:
            logger.warning("Rejected malformed date row: %s", type(exc).__name__)
    if not rows:
        rate_limiter.record_error()
        raise FliProviderError("Upstream returned dates, but none validated")
    rate_limiter.record_success()
    return sorted(rows, key=lambda r: r.price_twd)[:max_results]
