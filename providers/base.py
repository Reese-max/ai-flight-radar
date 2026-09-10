from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class FlightLeg(BaseModel):
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration_mins: int
    airline: str
    flight_no: Optional[str] = None
    plane_type: Optional[str] = None

class StandardFlightOffer(BaseModel):
    provider: str
    origin: str
    destination: str
    trip_type: str  # "round-trip" | "one-way"
    depart_date: str
    return_date: Optional[str] = None
    duration_days: Optional[int] = None
    price_twd: int
    is_direct: bool
    stops: int
    legs: List[FlightLeg] = []
    primary_airline: str
    depart_time_str: Optional[str] = None
    arrival_time_str: Optional[str] = None
    total_duration_mins: Optional[int] = None
    searched_at: datetime

class BaseFlightProvider(ABC):
    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        depart_date: str,
        return_date: Optional[str] = None,
        max_stops: int = 0
    ) -> List[StandardFlightOffer]:
        """Search flights between origin and destination."""
        pass
