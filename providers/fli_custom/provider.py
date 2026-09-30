"""FliCustomProvider — AI Flight Radar adapter over the vendored Fli engine.

Upstream Fli lives verbatim in ``third_party/fli/`` (see ``docs/UPSTREAM_FLI.md``);
all customization stays in this package so upstream diffs remain trivial. Locally
authored. The outer collector task budget stays authoritative; Fli's own bounded
retry (3 attempts) and global 10 req/s limiter apply underneath it.

Bounds (all enforced before any upstream request):

- ``TOP_N``: round-trip expansion issues one follow-up request per candidate.
- ``MAX_AIRPORTS_PER_SIDE``: multi-airport queries ride inside a single upstream
  request — they never fan out per city pair.
- ``FLEX_MAX_SPAN_DAYS`` / ``FLEX_MAX_QUERIES``: a flexible-date plan is a fixed
  list of calendar calls, never an unbounded per-date loop.
"""
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from config.settings import settings
from providers.base import BaseFlightProvider, StandardFlightOffer
from providers.rate_limiter import rate_limiter
from providers.fli_custom.errors import FliProviderError
from providers.fli_custom.models import FlexibleDateOffer, FlexibleDateQuery
from providers.fli_custom import mapper

logger = logging.getLogger(__name__)

# Round-trip expansion issues one follow-up request per candidate; keep the
# per-task request count small so a 90s collector timeout still covers it.
TOP_N = 3

MAX_AIRPORTS_PER_SIDE = 3
MAX_ADULTS = 9
FLEX_MAX_SPAN_DAYS = 61   # one upstream calendar chunk — never parallel fan-out
FLEX_MAX_QUERIES = 4      # deterministic upstream-request budget per plan
FLEX_MAX_TRIP_DAYS = 30   # matches the collector's task bound
FLEX_MAX_RESULTS = 100    # absolute ceiling; callers may tighten via max_results


def _ensure_fli_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "third_party" / "fli"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _load_engine():
    """Import the vendored Fli package lazily so --help/tests stay light."""
    _ensure_fli_path()
    os.environ.setdefault("FLI_TIMEOUT", "20")
    from fli.models import (Airline, Airport, Currency, DateSearchFilters,
                            FlightSearchFilters, FlightSegment, MaxStops,
                            PassengerInfo, PriceLimit, SeatType, TripType)
    from fli.search.dates import SearchDates
    from fli.search.flights import SearchFlights
    return (Airline, Airport, Currency, DateSearchFilters, FlightSearchFilters,
            FlightSegment, MaxStops, PassengerInfo, PriceLimit, SeatType,
            TripType, SearchDates, SearchFlights)


def _parse_iso(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise FliProviderError(f"{field} must be an ISO date string") from None


class FliCustomProvider(BaseFlightProvider):
    name = "fli_custom"

    def __init__(self):
        self.currency = settings.CURRENCY
        self.language = settings.LANGUAGE
        self.country = "TW"

    # -- engine seams (tests monkeypatch these, never the network) -----------

    def _fetch(self, filters):
        """Isolated GetShoppingResults call."""
        *_models, SearchFlights = _load_engine()
        return SearchFlights().search(
            filters, top_n=TOP_N,
            currency=self.currency, language=self.language, country=self.country)

    def _fetch_dates(self, filters):
        """Isolated GetCalendarGraph call — one upstream request per call."""
        (_a, _ap, _c, _dsf, _fsf, _fs, _ms, _pi, _pl, _st, _tt,
         SearchDates, _sf) = _load_engine()
        return SearchDates().search(
            filters, currency=self.currency, language=self.language,
            country=self.country)

    # -- validation helpers --------------------------------------------------

    def _seat_type(self, cabin: str):
        SeatType = _load_engine()[9]
        try:
            return SeatType[str(cabin).strip().upper()]
        except KeyError:
            raise FliProviderError(f"Unsupported cabin: {cabin!r}") from None

    def _airport_codes(self, single: Optional[str],
                       multi: Optional[Sequence[str]]) -> Tuple[str, ...]:
        codes = list(multi) if multi is not None else ([single] if single else [])
        codes = [str(c).strip().upper() for c in codes]
        if not codes or not all(codes):
            raise FliProviderError("at least one airport code is required")
        if len(set(codes)) != len(codes):
            raise FliProviderError("duplicate airport codes are not allowed")
        if len(codes) > MAX_AIRPORTS_PER_SIDE:
            raise FliProviderError(
                f"at most {MAX_AIRPORTS_PER_SIDE} airports per side are allowed")
        return tuple(codes)

    def _airline_codes(self, airlines: Optional[Iterable[str]]):
        if airlines is None:
            return None
        codes = list(airlines)
        if not codes:
            raise FliProviderError("airlines must not be empty")
        Airline = _load_engine()[0]
        resolved = []
        for code in codes:
            try:
                resolved.append(Airline[str(code).strip().upper()])
            except KeyError:
                raise FliProviderError(f"Unknown airline code: {code!r}") from None
        return resolved

    @staticmethod
    def _adults(adults) -> int:
        if type(adults) is not int or not 1 <= adults <= MAX_ADULTS:
            raise FliProviderError(f"adults must be an integer in 1..{MAX_ADULTS}")
        return adults

    def _resolve_airports(self, codes, Airport):
        resolved = []
        for code in codes:
            try:
                resolved.append(Airport[code])
            except KeyError:
                raise FliProviderError(f"Unknown airport code: {code!r}") from None
        return [[a, 0] for a in resolved]

    # -- point-in-time search -------------------------------------------------

    def search(self, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, max_stops: int = 0, *,
               cabin: str = "ECONOMY", adults: int = 1,
               airlines: Optional[Iterable[str]] = None,
               origins: Optional[Sequence[str]] = None,
               destinations: Optional[Sequence[str]] = None
               ) -> List[StandardFlightOffer]:
        origin_codes = self._airport_codes(origin, origins)
        dest_codes = self._airport_codes(destination, destinations)
        if set(origin_codes) & set(dest_codes):
            raise FliProviderError("origin and destination airports must differ")
        seat_type = self._seat_type(cabin)
        adults_n = self._adults(adults)
        airline_list = self._airline_codes(airlines)

        try:
            (_a, Airport, _c, _d, FlightSearchFilters, FlightSegment, MaxStops,
             PassengerInfo, _p, _s, TripType, _sd, _sf) = _load_engine()
            stops = {0: MaxStops.NON_STOP, 1: MaxStops.ONE_STOP_OR_FEWER}.get(
                max_stops, MaxStops.TWO_OR_FEWER_STOPS)
            dep_airports = self._resolve_airports(origin_codes, Airport)
            arr_airports = self._resolve_airports(dest_codes, Airport)
            segments = [FlightSegment(departure_airport=dep_airports,
                                      arrival_airport=arr_airports,
                                      travel_date=depart_date)]
            if return_date:
                segments.append(FlightSegment(departure_airport=arr_airports,
                                              arrival_airport=dep_airports,
                                              travel_date=return_date))
            filters = FlightSearchFilters(
                trip_type=TripType.ROUND_TRIP if return_date else TripType.ONE_WAY,
                passenger_info=PassengerInfo(adults=adults_n),
                flight_segments=segments, stops=stops, seat_type=seat_type,
                airlines=airline_list)
        except FliProviderError:
            raise
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

        ctx = {"origin": "+".join(origin_codes),
               "destination": "+".join(dest_codes),
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

    # -- bounded flexible-date search ----------------------------------------

    def flexible_plan(self, origin: str, destination: str,
                      from_date: str, to_date: str, *,
                      trip_durations: Optional[Iterable[int]] = None,
                      origins: Optional[Sequence[str]] = None,
                      destinations: Optional[Sequence[str]] = None,
                      max_queries: int = FLEX_MAX_QUERIES
                      ) -> List[FlexibleDateQuery]:
        """The deterministic, fully-bounded query plan — before any network.

        One upstream ``GetCalendarGraph`` call covers a whole ≤61-day window;
        a round-trip plan needs one call per allowed trip duration. Anything
        wider is rejected instead of silently exploding into per-date queries.
        """
        origin_codes = self._airport_codes(origin, origins)
        dest_codes = self._airport_codes(destination, destinations)
        if set(origin_codes) & set(dest_codes):
            raise FliProviderError("origin and destination airports must differ")
        start = _parse_iso(from_date, "from_date")
        end = _parse_iso(to_date, "to_date")
        if start < date.today():
            raise FliProviderError("from_date cannot be in the past")
        span = (end - start).days + 1
        if span < 1 or span > FLEX_MAX_SPAN_DAYS:
            raise FliProviderError(
                f"date window must span 1..{FLEX_MAX_SPAN_DAYS} days")
        if type(max_queries) is not int or not 1 <= max_queries <= FLEX_MAX_QUERIES:
            raise FliProviderError(f"max_queries must be an integer in 1..{FLEX_MAX_QUERIES}")

        if trip_durations is None:
            durations = [None]
        else:
            raw = list(trip_durations)
            if not raw:
                raise FliProviderError("trip_durations must not be empty")
            if any(type(d) is not int or not 1 <= d <= FLEX_MAX_TRIP_DAYS
                   for d in raw):
                raise FliProviderError(
                    f"trip durations must be integers in 1..{FLEX_MAX_TRIP_DAYS} days")
            durations = sorted(set(raw))
        if len(durations) > max_queries:
            raise FliProviderError(
                f"plan needs {len(durations)} queries, budget is {max_queries}")
        return [FlexibleDateQuery(
            trip_type="round-trip" if d is not None else "one-way",
            from_date=from_date, to_date=to_date, duration_days=d)
            for d in durations]

    def search_dates(self, origin: str, destination: str,
                     from_date: str, to_date: str, *,
                     trip_durations: Optional[Iterable[int]] = None,
                     max_stops: int = 0, cabin: str = "ECONOMY",
                     adults: int = 1, airlines: Optional[Iterable[str]] = None,
                     max_price_twd: Optional[int] = None,
                     max_results: int = 25,
                     origins: Optional[Sequence[str]] = None,
                     destinations: Optional[Sequence[str]] = None,
                     ) -> List[FlexibleDateOffer]:
        """Flexible-date search over an explicit bounded plan.

        ``trip_durations=None`` → one-way calendar; an iterable of trip lengths
        → round-trip calendar, one upstream call per duration. Results are
        sorted deterministically (price, depart, return) and capped."""
        plan = self.flexible_plan(origin, destination, from_date, to_date,
                                  trip_durations=trip_durations, origins=origins,
                                  destinations=destinations)
        origin_codes = self._airport_codes(origin, origins)
        dest_codes = self._airport_codes(destination, destinations)
        if type(max_results) is not int or not 1 <= max_results <= FLEX_MAX_RESULTS:
            raise FliProviderError(f"max_results must be an integer in 1..{FLEX_MAX_RESULTS}")
        if max_price_twd is not None and (type(max_price_twd) is not int or max_price_twd < 1):
            raise FliProviderError("max_price_twd must be a positive integer")
        seat_type = self._seat_type(cabin)
        adults_n = self._adults(adults)
        airline_list = self._airline_codes(airlines)

        (Airline_, Airport, Currency, DateSearchFilters, _fsf, FlightSegment,
         MaxStops, PassengerInfo, PriceLimit, _st, TripType, _sd, _sf) = _load_engine()
        try:
            stops = {0: MaxStops.NON_STOP, 1: MaxStops.ONE_STOP_OR_FEWER}.get(
                max_stops, MaxStops.TWO_OR_FEWER_STOPS)
            dep_airports = self._resolve_airports(origin_codes, Airport)
            arr_airports = self._resolve_airports(dest_codes, Airport)
            price_limit = (PriceLimit(max_price=max_price_twd, currency=Currency.TWD)
                           if max_price_twd else None)
            planned_filters = []
            for query in plan:
                segments = [FlightSegment(departure_airport=dep_airports,
                                          arrival_airport=arr_airports,
                                          travel_date=from_date)]
                if query.duration_days is not None:
                    back = (date.fromisoformat(from_date)
                            + timedelta(days=query.duration_days)).isoformat()
                    segments.append(FlightSegment(departure_airport=arr_airports,
                                                  arrival_airport=dep_airports,
                                                  travel_date=back))
                planned_filters.append(DateSearchFilters(
                    trip_type=(TripType.ROUND_TRIP if query.duration_days is not None
                               else TripType.ONE_WAY),
                    passenger_info=PassengerInfo(adults=adults_n),
                    flight_segments=segments, stops=stops, seat_type=seat_type,
                    airlines=airline_list, price_limit=price_limit,
                    from_date=from_date, to_date=to_date,
                    duration=query.duration_days))
        except FliProviderError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise FliProviderError(f"Cannot build date filters: {type(exc).__name__}") from exc

        ctx = {"origin": "+".join(origin_codes), "destination": "+".join(dest_codes),
               "from_date": from_date, "to_date": to_date}
        offers = []
        saw_rows = False
        for query, filters in zip(plan, planned_filters):
            rate_limiter.wait()
            try:
                rows = self._fetch_dates(filters)
            except Exception as exc:
                rate_limiter.record_error()
                raise FliProviderError(
                    f"Upstream date search failed ({type(exc).__name__}); "
                    "no price observation recorded") from exc
            rate_limiter.record_success()
            if not rows:
                continue
            saw_rows = True
            q_ctx = dict(ctx, trip_type=query.trip_type,
                         duration_days=query.duration_days)
            for row in rows:
                try:
                    offers.append(mapper.map_date_price(row, q_ctx))
                except (AttributeError, TypeError, ValueError) as exc:
                    logger.warning("Rejected malformed Fli date row: %s",
                                   type(exc).__name__)
        if saw_rows and not offers:
            raise FliProviderError(
                "Upstream returned date rows, but none could be validated")
        offers.sort(key=lambda o: (o.price_twd, o.depart_date, o.return_date or ""))
        return offers[:max_results]
