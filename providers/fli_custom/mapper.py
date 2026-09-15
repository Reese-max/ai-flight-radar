"""Map vendored Fli ``FlightResult`` objects onto AI Flight Radar's domain model.

Pure duck-typed mapping: this module never imports ``fli.*`` so offline tests can
feed it fixtures without the upstream package or its heavy dependencies.
Unknown upstream fields stay ``None`` — nothing is inferred from airline names
or heuristics. Locally authored (not upstream-derived).
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Optional, Tuple

from providers.base import FlightLeg, StandardFlightOffer


def _airline_name(airline) -> Optional[str]:
    """``Airline`` is ``Enum(name, AIRLINE_NAMES)``: .name=IATA, .value=full name."""
    if airline is None:
        return None
    value = getattr(airline, "value", None)
    return value if isinstance(value, str) and value else getattr(airline, "name", None)


def _price_twd(result) -> int:
    """Round-trip prices attach to whichever element Google priced; try both."""
    price = getattr(result, "price", None)
    if price is None:
        raise ValueError("price not surfaced by upstream")
    numeric = Decimal(str(price))
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError("Invalid price")
    value = int(numeric.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if value < 1:
        raise ValueError("Price rounds below one TWD")
    return value


def _map_legs(result) -> List[FlightLeg]:
    legs = []
    for leg in getattr(result, "legs", None) or []:
        airline = _airline_name(getattr(leg, "airline", None)) or "未知航空"
        dep = getattr(leg, "departure_datetime", None)
        arr = getattr(leg, "arrival_datetime", None)
        duration = getattr(leg, "duration", None) or 0
        legs.append(FlightLeg(
            origin=getattr(getattr(leg, "departure_airport", None), "name",
                           getattr(leg, "departure_airport", "")),
            destination=getattr(getattr(leg, "arrival_airport", None), "name",
                                getattr(leg, "arrival_airport", "")),
            departure_time=dep.strftime("%H:%M") if dep else "00:00",
            arrival_time=arr.strftime("%H:%M") if arr else "00:00",
            duration_mins=int(duration),
            airline=airline,
            flight_no=getattr(leg, "flight_number", None),
            plane_type=getattr(leg, "aircraft", None) or "",
        ))
    if not legs:
        raise ValueError("No verifiable flight segments")
    return legs


def map_result(raw, ctx) -> StandardFlightOffer:
    """Map one upstream row — a ``FlightResult`` (one-way) or a
    ``(outbound, inbound, ...)`` tuple (round-trip) — to a standard offer."""
    parts: Tuple = raw if isinstance(raw, tuple) else (raw,)
    outbound = parts[0]
    inbound = parts[1] if len(parts) > 1 else None
    price = None
    for part in (inbound, outbound):
        if part is None:
            continue
        try:
            price = _price_twd(part)
            break
        except (InvalidOperation, TypeError, ValueError):
            continue
    if price is None:
        raise ValueError("price not surfaced by upstream")

    legs = _map_legs(outbound)
    out_leg_count = len(legs)
    if inbound is not None:
        legs = legs + _map_legs(inbound)

    out_stops = int(getattr(outbound, "stops", 0) or 0)
    in_stops = int(getattr(inbound, "stops", 0) or 0) if inbound is not None else 0
    direct = out_stops == 0 and in_stops == 0
    stops = out_stops + in_stops

    if ctx["max_stops"] == 0 and not direct:
        raise ValueError("not a direct offer")

    duration_days = None
    if ctx["return_date"]:
        duration_days = (datetime.fromisoformat(ctx["return_date"])
                         - datetime.fromisoformat(ctx["depart_date"])).days

    airline = (getattr(outbound, "primary_airline_name", None)
               or _airline_name(getattr(outbound, "primary_airline", None))
               or legs[0].airline)
    return StandardFlightOffer(
        provider="fli_custom", origin=ctx["origin"], destination=ctx["destination"],
        trip_type=ctx["trip_type"], depart_date=ctx["depart_date"],
        return_date=ctx["return_date"], duration_days=duration_days,
        price_twd=price, is_direct=direct, stops=stops, legs=legs,
        primary_airline=airline,
        depart_time_str=legs[0].departure_time,
        arrival_time_str=legs[out_leg_count - 1].arrival_time,
        total_duration_mins=sum(leg.duration_mins for leg in legs),
        searched_at=datetime.utcnow(),
    )
