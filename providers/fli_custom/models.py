"""Normalized domain objects for the Fli-derived provider. Locally authored —
upstream ``fli.*`` types must never escape into the rest of the product."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FlexibleDateQuery(BaseModel):
    """One planned upstream calendar call inside a bounded flexible-date plan."""
    trip_type: str          # "one-way" | "round-trip"
    from_date: str          # ISO date — first departure day in the window
    to_date: str            # ISO date — last departure day in the window
    duration_days: Optional[int] = None  # trip length; required for round-trip


class FlexibleDateOffer(BaseModel):
    """A normalized date+price observation (the calendar grid answer, not an
    itinerary). Fields the upstream did not surface stay ``None``."""
    provider: str
    origin: str
    destination: str
    trip_type: str
    depart_date: str
    return_date: Optional[str] = None
    duration_days: Optional[int] = None
    price_twd: int
    currency: Optional[str] = None
    searched_at: datetime
