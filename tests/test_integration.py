"""Real SQLite/SQLModel/API tests with fake quotes and fake delivery channels."""
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from sqlmodel import Session, select
from sqlalchemy import delete
from core.models import SearchTask, Deal, FlightSearchRecord
from core.snapshots import SearchSnapshot, TaskLease, RadarMigration
from core.database import init_db
from engine.analyzer import PriceAnalyzer
from engine.scheduler import RadarScheduler
from engine.price_history import query_key
from providers.base import StandardFlightOffer
from notifier.dispatcher import AlertDispatcher


def dates():
    departure = datetime.utcnow().date() + timedelta(days=50)
    return departure.isoformat(), (departure + timedelta(days=4)).isoformat()


def offer(price=5500):
    dep, ret = dates()
    return StandardFlightOffer(provider="fast_flights", origin="TPE", destination="NRT",
                              trip_type="round-trip", depart_date=dep, return_date=ret,
                              duration_days=4, price_twd=price, is_direct=True, stops=0,
                              primary_airline="Test Airline", depart_time_str="10:00",
                              arrival_time_str="14:00", searched_at=datetime.utcnow())


def task(db, **changes):
    dep, ret = dates()
    values = dict(origin="TPE", destination="NRT", depart_date=dep, return_date=ret, duration_days=4)
    values.update(changes)
    with Session(db) as session:
        obj = SearchTask(**values)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj.id


def old_snapshots(db, count=5):
    with Session(db) as session:
        for days in range(1, count+1):
            session.add(PriceAnalyzer.make_snapshot(offer(8000), 5,
                        searched_at=datetime.utcnow()-timedelta(days=days)))
        session.commit()


def stored_deal(db, **changes):
    dep, ret = dates()
    values = dict(origin="TPE", destination="NRT", depart_date=dep, return_date=ret,
                  duration_days=4, airline="Test Airline", price_twd=5500,
                  ref_price_twd=8000, drop_pct=31.2, deal_score=85,
                  reasons='["相同查詢的實際歷史基準"]')
    values.update(changes)
    with Session(db) as session:
        result = Deal(**values)
        session.add(result)
        session.commit()
        session.refresh(result)
        return result


def test_batch_stores_one_snapshot_and_uses_previous_reference(db, monkeypatch):
    old_snapshots(db)
    task_id = task(db)
    monkeypatch.setattr(AlertDispatcher, "dispatch_deal", lambda deal: False)
    provider = SimpleNamespace(search=lambda *a, **k: [offer(p) for p in [5500, 7500, 9000, 12000, 15000]])
    assert RadarScheduler(provider).process_task(task_id)
    with Session(db) as session:
        assert len(session.exec(select(FlightSearchRecord)).all()) == 5
        snapshots = session.exec(select(SearchSnapshot)).all()
        assert len(snapshots) == 6
        newest = max(snapshots, key=lambda row: row.searched_at)
        assert newest.price_twd == 5500 and newest.offer_count == 5
        deal = session.exec(select(Deal).where(Deal.status == "active")).one()
        assert deal.ref_price_twd == 8000 and deal.drop_pct == 31.2


def test_different_dates_cannot_share_a_baseline(db):
    old_snapshots(db)
    dep, ret = dates()
    different = (datetime.fromisoformat(ret)+timedelta(days=1)).date().isoformat()
    assert PriceAnalyzer.get_reference_stats("TPE", "NRT", 5, depart_date=dep,
                                              return_date=different)["is_cold_start"]


def test_no_baseline_without_exact_dates(db):
    old_snapshots(db)
    assert PriceAnalyzer.get_reference_stats("TPE", "NRT", 4)["avg_30d"] is None


def test_failed_provider_does_not_create_a_zero_price_or_hot_retry(db):
    task_id = task(db)
    def fail(*args, **kwargs):
        raise RuntimeError("Simulated provider failure")
    assert not RadarScheduler(SimpleNamespace(search=fail)).process_task(task_id)
    with Session(db) as session:
        assert session.exec(select(SearchSnapshot)).all() == []
        assert session.get(SearchTask, task_id).next_run_at > datetime.utcnow()+timedelta(minutes=9)


def test_two_workers_cannot_own_one_live_task(db):
    task_id = task(db)
    assert RadarScheduler._claim(task_id, "worker-a")
    assert not RadarScheduler._claim(task_id, "worker-b")
    RadarScheduler._release(task_id, "worker-b")
    assert not RadarScheduler._claim(task_id, "worker-b")
    RadarScheduler._release(task_id, "worker-a")
    assert RadarScheduler._claim(task_id, "worker-b")


def test_expired_worker_lease_can_be_reclaimed(db):
    task_id = task(db)
    assert RadarScheduler._claim(task_id, "old-worker")
    with Session(db) as session:
        lease = session.get(TaskLease, task_id)
        lease.expires_at = datetime.utcnow()-timedelta(seconds=1)
        session.add(lease)
        session.commit()
    assert RadarScheduler._claim(task_id, "new-worker")


def test_finite_scan_exits_when_no_tasks_are_due(db, monkeypatch):
    from engine.planner import ProgressivePlanner
    monkeypatch.setattr(ProgressivePlanner, "generate_search_tasks", lambda: 0)
    task(db, next_run_at=datetime.utcnow()+timedelta(days=1))
    radar = RadarScheduler(SimpleNamespace(search=lambda *a, **k: pytest.fail("Unexpected scan")))
    radar.run_loop(max_iterations=3)
    assert not radar.running


def test_all_delivery_failures_keep_notification_eligible(db, monkeypatch):
    import notifier.dispatcher as module
    deal = stored_deal(db)
    monkeypatch.setattr(module.ntfy_client, "send_alert", lambda **kwargs: False)
    monkeypatch.setattr(module.telegram_client, "send_message", lambda text: False)
    assert not AlertDispatcher.dispatch_deal(deal)
    with Session(db) as session:
        assert not session.get(Deal, deal.id).notified


def test_successful_delivery_marks_notified_and_escapes_html(db, monkeypatch):
    import notifier.dispatcher as module
    deal = stored_deal(db, airline='<b>untrusted & airline</b>')
    messages = []
    monkeypatch.setattr(module.ntfy_client, "send_alert", lambda **kwargs: False)
    monkeypatch.setattr(module.telegram_client, "send_message", lambda text: messages.append(text) or True)
    assert AlertDispatcher.dispatch_deal(deal)
    assert '&lt;b&gt;untrusted &amp; airline&lt;/b&gt;' in messages[0]
    with Session(db) as session:
        assert session.get(Deal, deal.id).notified


def test_migration_expires_old_scoring_only_once_and_keeps_records(db):
    previous = stored_deal(db)
    with Session(db) as session:
        session.add(FlightSearchRecord(origin="TPE", destination="NRT", depart_date=dates()[0],
                                       airline="Legacy", price_twd=99999))
        session.execute(delete(RadarMigration))
        session.commit()
    init_db()
    with Session(db) as session:
        assert session.get(Deal, previous.id).status == "expired"
        assert len(session.exec(select(FlightSearchRecord)).all()) == 1
    fresh = stored_deal(db)
    init_db()
    with Session(db) as session:
        assert session.get(Deal, fresh.id).status == "active"


def test_api_history_uses_snapshots_not_old_expensive_offers(db):
    from fastapi.testclient import TestClient
    from api.app import app
    old_snapshots(db)
    with Session(db) as session:
        session.add(FlightSearchRecord(origin="TPE", destination="NRT", depart_date=dates()[0],
                                       airline="Legacy", price_twd=99999))
        session.commit()
    with TestClient(app) as client:
        result = client.get("/api/history/TPE/NRT").json()
        assert result["data"][0]["avg_price"] == 8000
        assert result["data"][0]["observed_days"] == 5
        assert client.get("/api/health").status_code == 200


def test_write_key_and_route_validation(db, monkeypatch):
    from fastapi.testclient import TestClient
    from api.app import app, settings
    monkeypatch.setattr(settings, "API_KEY", "test-only-key")
    with TestClient(app) as client:
        assert client.post("/api/scan/trigger", json={}).status_code == 401
        assert client.post("/api/scan/trigger", json={"origin": "TPE"},
                           headers={"X-API-Key": "test-only-key"}).status_code == 422
        assert client.post("/api/scan/trigger", json={"origin": "TPE", "destination": "XXX"},
                           headers={"X-API-Key": "test-only-key"}).status_code == 422


def test_expired_quotes_are_not_returned_by_api(db):
    from fastapi.testclient import TestClient
    from api.app import app
    stored_deal(db, created_at=datetime.utcnow()-timedelta(hours=7))
    with TestClient(app) as client:
        assert client.get("/api/deals").json() == []


def test_snapshot_cold_start_does_not_publish_high_discount(db, monkeypatch):
    monkeypatch.setattr(AlertDispatcher, "dispatch_deal", lambda deal: pytest.fail("Unexpected alert"))
    assert RadarScheduler(SimpleNamespace(search=lambda *a, **k: [offer(3000), offer(15000)])).process_task(task(db))
    with Session(db) as session:
        assert len(session.exec(select(SearchSnapshot)).all()) == 1
        assert session.exec(select(Deal)).all() == []
