"""Persisted radar timestamps retain the existing timezone-free UTC contract."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from core.models import Deal, FlightSearchRecord, Route, RouteStats, SearchTask
from core.snapshots import RadarMigration, SearchSnapshot, TaskLease

STAMP = datetime(2026, 10, 1, 12, 30, 15, 123456)


@pytest.mark.parametrize("model,values,fields", [
    (Route, {"origin": "TPE", "destination": "NRT"}, ["created_at"]),
    (FlightSearchRecord, {"origin": "TPE", "destination": "NRT", "depart_date": "2026-12-01", "airline": "Test", "price_twd": 1000}, ["searched_at"]),
    (RouteStats, {"origin": "TPE", "destination": "NRT", "duration_days": 5}, ["last_updated"]),
    (Deal, {"origin": "TPE", "destination": "NRT", "depart_date": "2026-12-01", "return_date": "2026-12-06", "duration_days": 5, "airline": "Test", "price_twd": 1000, "ref_price_twd": 2000, "drop_pct": 50.0, "deal_score": 80, "notified_at": STAMP}, ["created_at", "notified_at"]),
    (SearchTask, {"origin": "TPE", "destination": "NRT", "depart_date": "2026-12-01", "return_date": "2026-12-06", "duration_days": 5, "last_searched_at": STAMP}, ["next_run_at", "last_searched_at"]),
    (SearchSnapshot, {"query_key": "test-query", "origin": "TPE", "destination": "NRT", "depart_date": "2026-12-01", "return_date": "2026-12-06", "duration_days": 5, "price_twd": 1000, "offer_count": 1}, ["searched_at"]),
    (TaskLease, {"task_id": 1, "owner": "test-owner", "expires_at": STAMP}, ["expires_at"]),
    (RadarMigration, {"name": "test-migration"}, ["applied_at"]),
])
def test_all_persisted_timestamp_fields_roundtrip_and_support_utc_filters(tmp_path, model, values, fields):
    engine = create_engine(f"sqlite:///{tmp_path / 'roundtrip.db'}")
    try:
        SQLModel.metadata.create_all(engine)
        record = model(**values)
        expected = {field: getattr(record, field) for field in fields}
        with Session(engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            for field, instant in expected.items():
                assert isinstance(instant, datetime) and instant.tzinfo is None
                assert getattr(record, field) == instant
                assert getattr(record, field).tzinfo is None
                match = session.exec(select(model).where(getattr(model, field) < instant + timedelta(seconds=1))).one()
                assert getattr(match, field) == instant
    finally:
        engine.dispose()


def test_existing_sqlite_timestamp_rows_are_read_without_timezone_reinterpretation(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        SQLModel.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO radar_migrations (name, applied_at) VALUES (:name, :stamp)"), {"name": "legacy", "stamp": "2026-10-01 12:30:15.123456"})
        with Session(engine) as session:
            record = session.get(RadarMigration, "legacy")
            assert record.applied_at == STAMP
            assert record.applied_at.tzinfo is None
    finally:
        engine.dispose()
