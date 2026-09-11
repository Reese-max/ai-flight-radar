"""No live provider requests or notifications. Synthetic data exists only in tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from core.models import FlightSearchRecord
from core.snapshots import SearchSnapshot
from engine.price_history import query_key
from config.settings import settings
from api.site import app, worker_health, _manual_calls


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def snapshot(db, price=6000, age=0, depart=None, raw=False):
    dep = depart or (now()+timedelta(days=50)).date().isoformat()
    ret = (datetime.fromisoformat(dep)+timedelta(days=4)).date().isoformat()
    at = now()-timedelta(days=age, minutes=1)
    row = SearchSnapshot(query_key=query_key('TPE', 'FUK', dep, ret), origin='TPE', destination='FUK',
                         depart_date=dep, return_date=ret, duration_days=4, price_twd=price,
                         offer_count=3, searched_at=at)
    with Session(db) as session:
        session.add(row)
        if raw:
            session.add(FlightSearchRecord(origin='TPE', destination='FUK', depart_date=dep,
                return_date=ret, duration_days=4, price_twd=price, searched_at=at,
                airline='<script>external text</script>', source='google_flights'))
        session.commit()
        session.refresh(row)
        return row


def test_site_assets_and_security_headers(db):
    with TestClient(app) as client:
        root = client.get('/')
        assert root.status_code == 200
        assert 'Flight Radar' in root.text
        assert "script-src 'self'" in root.headers['content-security-policy']
        for path in ('/assets/app.js', '/assets/app.css', '/assets/logic.mjs', '/assets/icons/radar.svg'):
            assert client.get(path).status_code == 200
        assert client.get('/assets/../../.env').status_code != 200


def test_empty_is_not_demo(db):
    with TestClient(app) as client:
        data = client.get('/api/ui/quotes').json()
        assert data['quotes'] == [] and data['demo'] is False
        assert data['next_offset'] is None


def test_quotes_exclude_current_batch_from_baseline(db):
    for day in range(1, 6):
        snapshot(db, price=8000, age=day)
    latest = snapshot(db, price=6000, raw=True)
    with TestClient(app) as client:
        rows = client.get('/api/ui/quotes').json()['quotes']
        assert len(rows) == 1
        q = rows[0]
        assert q['id'] == latest.id and q['baseline_twd'] == 8000
        assert q['drop_pct'] == 25 and q['prior_observed_days'] == 5
        assert q['baseline_confident'] is True and q['trip_days'] == 5
        assert q['airline'] == '<script>external text</script>'
        assert q['baggage_verified'] is False
        assert q['searched_at'].endswith('+00:00')


def test_new_price_over_budget_does_not_resurface_old_cheap_quote(db):
    snapshot(db, price=5000, age=0.02)
    snapshot(db, price=9000)
    with TestClient(app) as client:
        assert client.get('/api/ui/quotes?max_price=6000').json()['quotes'] == []


def test_date_comparison_retains_but_labels_old_quotes(db):
    old = snapshot(db, age=1)
    with TestClient(app) as client:
        assert client.get('/api/ui/quotes').json()['quotes'] == []
        rows = client.get('/api/ui/dates/TPE/FUK').json()['quotes']
        assert len(rows) == 1 and rows[0]['expired'] is True
        assert client.get('/api/ui/quote/'+old.id).json()['expired'] is True


def test_cold_start_does_not_invent_discount_or_airline(db):
    snapshot(db)
    with TestClient(app) as client:
        q = client.get('/api/ui/quotes').json()['quotes'][0]
        assert q['baseline_twd'] is None and q['drop_pct'] is None
        assert q['airline'] is None and q['baseline_confident'] is False


@pytest.mark.parametrize('query', [
    'origin=ABC', 'destination=TPE', 'min_days=0', 'min_days=10&max_days=4',
    'start_date=2026-12-05&end_date=2026-12-01', 'limit=10000', 'sort=unknown',
])
def test_invalid_filter_is_422(db, query):
    with TestClient(app) as client:
        assert client.get('/api/ui/quotes?'+query).status_code == 422


def test_missing_detail_not_synthetic(db):
    with TestClient(app) as client:
        assert client.get('/api/ui/quote/'+str(uuid4())).status_code == 404


def test_config_never_returns_secrets(db, monkeypatch):
    monkeypatch.setattr(settings, 'API_KEY', 'do-not-expose-this-administrator-secret')
    monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', 'do-not-expose-this-bot-secret')
    monkeypatch.setattr(settings, 'NTFY_TOPIC', 'do-not-expose-this-topic')
    with TestClient(app) as client:
        res = client.get('/api/ui/config')
        assert 'do-not-expose' not in res.text
        assert res.json()['watchlist_scope'] == 'browser_only'
        assert res.headers['cache-control'] == 'no-store'


def test_access_check_and_public_scan_fail_closed(db, monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_MODE', 'public')
    monkeypatch.setattr(settings, 'API_KEY', '')
    with TestClient(app) as client:
        assert client.post('/api/scan/trigger', json={}).status_code == 503
        monkeypatch.setattr(settings, 'API_KEY', 'x'*40)
        assert client.get('/api/ui/access').status_code == 401
        assert client.get('/api/ui/access', headers={'X-API-Key':'x'*40}).status_code == 200
        assert client.post('/api/scan/trigger', json={}).status_code == 401


def test_public_manual_scan_is_globally_throttled_without_network(db, monkeypatch):
    import api.app as original
    monkeypatch.setenv('DEPLOYMENT_MODE', 'public')
    monkeypatch.setattr(settings, 'API_KEY', 'x'*40)
    monkeypatch.setattr(original.scheduler_instance, 'process_task', lambda task_id: True)
    _manual_calls.clear()
    try:
        with TestClient(app) as client:
            headers={'X-API-Key':'x'*40}
            assert client.post('/api/scan/trigger', headers=headers,
                json={'origin':'TPE','destination':'FUK'}).status_code == 200
            res=client.post('/api/scan/trigger', headers=headers, json={})
            assert res.status_code == 429 and res.headers['retry-after'] == '60'
    finally:
        _manual_calls.clear()


def test_bounded_post_and_rule_parser(db):
    with TestClient(app) as client:
        assert client.post('/api/ui/parse', content=b'x'*17000).status_code == 413
        result=client.post('/api/ui/parse', json={'query':'福岡 4～5 天 8000 元以下'})
        assert result.status_code == 200 and result.json()['requires_confirmation'] is True
        assert result.json()['method'] == 'rule_based'


def test_worker_heartbeat_does_not_invent_running_status(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'DB_PATH', str(tmp_path/'test.db'))
    assert worker_health()['status'] == 'not_started'
    file=tmp_path/'worker-health.json'
    file.write_text(json.dumps({'status':'idle','heartbeat_at':datetime.now(timezone.utc).isoformat()}))
    assert worker_health()['status'] == 'idle'
    file.write_text(json.dumps({'status':'scanning','heartbeat_at':(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()}))
    assert worker_health()['status'] == 'stale'
