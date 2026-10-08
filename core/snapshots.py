"""Additive tables: existing flight records and schema are not rewritten."""
from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlmodel import Field, SQLModel
from sqlalchemy import DateTime

# SQLite stores existing radar timestamps as timezone-free UTC.


class SearchSnapshot(SQLModel, table=True):
    __tablename__ = "search_snapshots"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    query_key: str = Field(index=True)
    origin: str = Field(index=True)
    destination: str = Field(index=True)
    depart_date: str = Field(index=True)
    return_date: str = Field(index=True)
    duration_days: int
    price_twd: int
    offer_count: int
    currency: str = "TWD"
    source: str = "google_flights"
    direct_only: bool = True
    adults: int = 1
    cabin: str = "economy"
    searched_at: datetime = Field(default_factory=datetime.utcnow, index=True, sa_type=DateTime(timezone=False))


class TaskLease(SQLModel, table=True):
    __tablename__ = "task_leases"
    task_id: int = Field(primary_key=True)
    owner: str
    expires_at: datetime = Field(index=True, sa_type=DateTime(timezone=False))


class RadarMigration(SQLModel, table=True):
    __tablename__ = "radar_migrations"
    name: str = Field(primary_key=True)
    applied_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime(timezone=False))
