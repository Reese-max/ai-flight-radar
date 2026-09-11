"""Google Flights adapter. Upstream failures are different from an empty result."""
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Optional
from config.settings import settings
from providers.base import BaseFlightProvider, StandardFlightOffer, FlightLeg
from providers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    pass


class FastFlightsProvider(BaseFlightProvider):
    def __init__(self):
        self.currency = settings.CURRENCY
        self.language = settings.LANGUAGE

    def search(self, origin: str, destination: str, depart_date: str,
               return_date: Optional[str] = None, max_stops: int = 0) -> List[StandardFlightOffer]:
        # Import lazily so --help, status and offline tests need not load a scraper.
        import fast_flights
        rate_limiter.wait()
        queries = [fast_flights.FlightQuery(date=depart_date, from_airport=origin,
                                           to_airport=destination, max_stops=max_stops)]
        if return_date:
            queries.append(fast_flights.FlightQuery(date=return_date, from_airport=destination,
                                                    to_airport=origin, max_stops=max_stops))
        try:
            query = fast_flights.create_query(
                flights=queries, trip="round-trip" if return_date else "one-way",
                seat="economy", passengers=fast_flights.Passengers(adults=1),
                currency=self.currency, language=self.language, max_stops=max_stops,
            )
            raw = list(fast_flights.get_flights(query))
        except fast_flights.FlightsNotFound:
            rate_limiter.record_success()
            return []
        except Exception as exc:
            rate_limiter.record_error()
            raise ProviderError("Upstream search failed; no price observation recorded") from exc
        offers = []
        for item in raw:
            try:
                numeric = Decimal(str(item.price))
                if not numeric.is_finite() or numeric <= 0:
                    raise ValueError("Invalid price")
                price = int(numeric.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                if price < 1:
                    raise ValueError("Price rounds below one TWD")
                airline = (item.airlines or ["未知航空"])[0]
                legs = []
                for segment in item.flights:
                    dh, dm = segment.departure.time
                    ah, am = segment.arrival.time
                    legs.append(FlightLeg(
                        origin=segment.from_airport.code, destination=segment.to_airport.code,
                        departure_time=f"{dh:02d}:{dm:02d}", arrival_time=f"{ah:02d}:{am:02d}",
                        duration_mins=segment.duration or 0, airline=airline,
                        plane_type=segment.plane_type or "",
                    ))
                if not legs:
                    raise ValueError("No verifiable flight segments")
                # A direct outbound + direct inbound are two directions, not one stop.
                direct = all((leg.origin, leg.destination) in
                             {(origin, destination), (destination, origin)} for leg in legs)
                stops = 0 if direct else max(1, len(legs) - 1)
                if max_stops == 0 and not direct:
                    continue
                duration = ((datetime.fromisoformat(return_date) - datetime.fromisoformat(depart_date)).days
                            if return_date else None)
                offers.append(StandardFlightOffer(
                    provider="fast_flights", origin=origin, destination=destination,
                    trip_type="round-trip" if return_date else "one-way",
                    depart_date=depart_date, return_date=return_date, duration_days=duration,
                    price_twd=price, is_direct=direct, stops=stops, legs=legs,
                    primary_airline=airline, depart_time_str=legs[0].departure_time,
                    arrival_time_str=legs[0].arrival_time if direct else legs[-1].arrival_time,
                    total_duration_mins=sum(leg.duration_mins for leg in legs),
                    searched_at=datetime.utcnow(),
                ))
            except (AttributeError, TypeError, ValueError, InvalidOperation) as exc:
                logger.warning("Rejected malformed flight result: %s", type(exc).__name__)
        if raw and not offers:
            rate_limiter.record_error()
            raise ProviderError("Upstream returned results, but none could be validated")
        rate_limiter.record_success()
        return sorted(offers, key=lambda offer: offer.price_twd)
