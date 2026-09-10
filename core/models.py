from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, UniqueConstraint

class Route(SQLModel, table=True):
    __tablename__ = "routes"
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    country: str = Field(default="日本")
    priority: int = Field(default=5)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("origin", "destination", name="uq_origin_destination"),
    )

class FlightSearchRecord(SQLModel, table=True):
    __tablename__ = "flight_records"
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    trip_type: str = Field(default="round-trip")
    depart_date: str = Field(index=True)
    return_date: Optional[str] = Field(default=None, index=True)
    duration_days: Optional[int] = Field(default=None, index=True)
    
    airline: str
    plane_type: Optional[str] = None
    price_twd: int = Field(index=True)
    is_direct: bool = Field(default=True)
    stops: int = Field(default=0)
    
    depart_time: Optional[str] = None
    arrival_time: Optional[str] = None
    duration_mins: Optional[int] = None
    source: str = Field(default="google_flights")
    searched_at: datetime = Field(default_factory=datetime.utcnow, index=True)

class RouteStats(SQLModel, table=True):
    __tablename__ = "route_stats"
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    duration_days: int = Field(index=True)
    sample_count: int = Field(default=0)
    avg_7d: Optional[float] = None
    avg_30d: Optional[float] = None
    avg_90d: Optional[float] = None
    min_historical: Optional[int] = None
    max_historical: Optional[int] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("origin", "destination", "duration_days", name="uq_route_duration_stats"),
    )

class Deal(SQLModel, table=True):
    __tablename__ = "deals"
    id: Optional[int] = Field(default=None, primary_key=True)
    record_id: Optional[int] = None
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    depart_date: str = Field(index=True)
    return_date: str = Field(index=True)
    duration_days: int = Field(index=True)
    airline: str
    price_twd: int = Field(index=True)
    ref_price_twd: int
    drop_pct: float
    deal_score: int = Field(index=True)
    deal_level: str = Field(default="GREAT_DEAL") # GREAT_DEAL, 90D_LOW, EXCEPTIONAL_DEAL
    reasons: str = Field(default="[]") # JSON string array
    is_direct: bool = Field(default=True)
    status: str = Field(default="active", index=True) # active, expired
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    notified: bool = Field(default=False)
    notified_at: Optional[datetime] = None

class SearchTask(SQLModel, table=True):
    __tablename__ = "search_tasks"
    id: Optional[int] = Field(default=None, primary_key=True)
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    depart_date: str = Field(index=True)
    return_date: str = Field(index=True)
    duration_days: int = Field(index=True)
    tier: int = Field(default=1) # 1: normal, 2: drop, 3: target, 4: extreme
    last_price: Optional[int] = None
    last_deal_score: Optional[int] = None
    last_searched_at: Optional[datetime] = None
    next_run_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    priority: int = Field(default=5)

    __table_args__ = (
        UniqueConstraint("origin", "destination", "depart_date", "return_date", name="uq_task_dates"),
    )
