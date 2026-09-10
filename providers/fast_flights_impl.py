import logging
from datetime import datetime
from typing import List, Optional
import fast_flights

from config.settings import settings
from providers.base import BaseFlightProvider, StandardFlightOffer, FlightLeg
from providers.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class FastFlightsProvider(BaseFlightProvider):
    def __init__(self):
        self.currency = settings.CURRENCY
        self.language = settings.LANGUAGE

    def search(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: Optional[str] = None,
        max_stops: int = 0
    ) -> List[StandardFlightOffer]:
        """
        Executes search on Google Flights via fast_flights.
        Returns normalized StandardFlightOffer list.
        """
        rate_limiter.wait()
        
        trip_type = "round-trip" if return_date else "one-way"
        flight_queries = [
            fast_flights.FlightQuery(
                date=depart_date,
                from_airport=origin,
                to_airport=destination,
                max_stops=max_stops
            )
        ]
        
        duration_days = None
        if return_date:
            flight_queries.append(
                fast_flights.FlightQuery(
                    date=return_date,
                    from_airport=destination,
                    to_airport=origin,
                    max_stops=max_stops
                )
            )
            try:
                d1 = datetime.strptime(depart_date, "%Y-%m-%d")
                d2 = datetime.strptime(return_date, "%Y-%m-%d")
                duration_days = (d2 - d1).days
            except Exception:
                pass

        try:
            query = fast_flights.create_query(
                flights=flight_queries,
                trip=trip_type,
                currency=self.currency,
                language=self.language,
                max_stops=max_stops
            )
            raw_results = fast_flights.get_flights(query)
            rate_limiter.record_success()
        except Exception as e:
            rate_limiter.record_error()
            logger.error(f"Error fetching flights for {origin}->{destination} ({depart_date} to {return_date}): {e}")
            return []

        offers: List[StandardFlightOffer] = []
        now = datetime.utcnow()

        for item in raw_results:
            try:
                price = int(item.price)
                if price <= 0:
                    continue
                
                airlines = item.airlines if item.airlines else ["未知航空"]
                primary_airline = airlines[0]

                legs: List[FlightLeg] = []
                total_duration = 0
                dep_time_str = None
                arr_time_str = None

                for f in item.flights:
                    dep_h, dep_m = f.departure.time
                    arr_h, arr_m = f.arrival.time
                    cur_dep_str = f"{dep_h:02d}:{dep_m:02d}"
                    cur_arr_str = f"{arr_h:02d}:{arr_m:02d}"

                    if dep_time_str is None:
                        dep_time_str = cur_dep_str
                    arr_time_str = cur_arr_str
                    total_duration += f.duration or 0

                    legs.append(
                        FlightLeg(
                            origin=f.from_airport.code,
                            destination=f.to_airport.code,
                            departure_time=cur_dep_str,
                            arrival_time=cur_arr_str,
                            duration_mins=f.duration or 0,
                            airline=primary_airline,
                            plane_type=f.plane_type or ""
                        )
                    )

                is_direct = (len(legs) <= 1) and (max_stops == 0)
                stops_count = max(0, len(legs) - 1)

                offer = StandardFlightOffer(
                    provider="fast_flights",
                    origin=origin,
                    destination=destination,
                    trip_type=trip_type,
                    depart_date=depart_date,
                    return_date=return_date,
                    duration_days=duration_days,
                    price_twd=price,
                    is_direct=is_direct,
                    stops=stops_count,
                    legs=legs,
                    primary_airline=primary_airline,
                    depart_time_str=dep_time_str,
                    arrival_time_str=arr_time_str,
                    total_duration_mins=total_duration,
                    searched_at=now
                )
                offers.append(offer)
            except Exception as e:
                logger.debug(f"Failed parsing single flight item: {e}")
                continue

        # Sort by price ascending
        offers.sort(key=lambda x: x.price_twd)
        return offers
