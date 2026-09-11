"""Figma UI 2.0 and bounded, read-only quote endpoints for a public deployment.

The original API remains compatible. No settings, secrets or personal watchlists
are exposed. A quote is an observation, not a promise that a fare is bookable.
"""
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Literal, Optional
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from api.app import app
from ai.nlp_parser import NLPIntentParser
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS
from config.settings import settings
from core.database import engine
from core.models import FlightSearchRecord, Route, SearchTask
from core.snapshots import SearchSnapshot
from engine.price_history import summarize_history
from engine.scheduler import taipei_today

WEB = Path(__file__).resolve().parent.parent / "web"
app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="ui-assets")
_manual_calls = deque()
_manual_lock = threading.Lock()


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def is_public():
    return os.getenv("DEPLOYMENT_MODE", "local").lower() == "public"


def admin_key(x_api_key: Optional[str] = Header(default=None)):
    if not settings.API_KEY or not secrets.compare_digest(
            (x_api_key or "").encode(), settings.API_KEY.encode()):
        raise HTTPException(status_code=401, detail="Valid administrator key required")


@app.middleware("http")
async def public_guard(request: Request, call_next):
    """Fail closed for public writes; this never changes read-only search into a scan."""
    if request.method == "POST":
        # Buffer only a small JSON request, including requests without Content-Length.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        request._body = bytes(body)
    if request.url.path == "/api/scan/trigger" and request.method == "POST" and is_public():
        if not settings.API_KEY:
            return JSONResponse({"detail": "Public scan access is not configured"}, status_code=503)
        supplied = request.headers.get("x-api-key", "")
        if not secrets.compare_digest(supplied.encode(), settings.API_KEY.encode()):
            return JSONResponse({"detail": "Valid administrator key required"}, status_code=401)
        with _manual_lock:
            cutoff = time.monotonic() - 60
            while _manual_calls and _manual_calls[0] < cutoff:
                _manual_calls.popleft()
            if _manual_calls:
                return JSONResponse({"detail": "Please wait before another manual scan"},
                                    status_code=429, headers={"Retry-After": "60"})
            _manual_calls.append(time.monotonic())
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'self'; object-src 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def airport_codes(value, allowed):
    if not value:
        return []
    codes = sorted(set(value.upper().split(",")))
    if len(codes) > len(allowed) or any(code not in allowed for code in codes):
        raise HTTPException(status_code=422, detail="Unsupported airport code")
    return codes


def latest_query(start, end, origins=None, destinations=None):
    s = SearchSnapshot
    conditions = [s.depart_date >= start, s.return_date <= end, s.price_twd > 0,
                  s.currency == "TWD", s.adults == 1, s.cabin == "economy",
                  s.direct_only == True, s.source == "google_flights"]
    if origins:
        conditions.append(s.origin.in_(origins))
    if destinations:
        conditions.append(s.destination.in_(destinations))
    ranked = select(s.id, func.row_number().over(
        partition_by=s.query_key, order_by=(s.searched_at.desc(), s.id.desc())
    ).label("rank")).where(*conditions).subquery()
    # Pick the latest BEFORE applying a price or freshness filter. An old cheaper
    # observation must not replace a newer price that exceeds the user's budget.
    return select(s).where(s.id.in_(select(ranked.c.id).where(ranked.c.rank == 1)))


def annotate(session, snapshots):
    if not snapshots:
        return []
    keys = [s.query_key for s in snapshots]
    history = session.exec(select(SearchSnapshot.query_key, SearchSnapshot.searched_at,
                                  SearchSnapshot.price_twd).where(
        SearchSnapshot.query_key.in_(keys),
        SearchSnapshot.searched_at >= now_utc() - timedelta(days=90),
    ).order_by(SearchSnapshot.searched_at.desc()).limit(10001)).all()
    truncated = len(history) > 10000
    grouped = defaultdict(list)
    for key, at, price in history[:10000]:
        grouped[key].append((at, price))
    # Exact timestamp+price join: never borrow airline details from another quote.
    raw = session.exec(select(SearchSnapshot.id, FlightSearchRecord).join(
        FlightSearchRecord,
        (FlightSearchRecord.origin == SearchSnapshot.origin) &
        (FlightSearchRecord.destination == SearchSnapshot.destination) &
        (FlightSearchRecord.depart_date == SearchSnapshot.depart_date) &
        (FlightSearchRecord.return_date == SearchSnapshot.return_date) &
        (FlightSearchRecord.price_twd == SearchSnapshot.price_twd) &
        (FlightSearchRecord.source == SearchSnapshot.source) &
        (FlightSearchRecord.searched_at == SearchSnapshot.searched_at),
    ).where(SearchSnapshot.id.in_([s.id for s in snapshots]))
      .order_by(FlightSearchRecord.id.asc()).limit(10000)).all()
    details = {}
    for sid, record in raw:
        details.setdefault(sid, record)
    result = []
    current_time = now_utc()
    for snap in snapshots:
        ref = summarize_history(grouped[snap.query_key], before=snap.searched_at)
        confident = ref["sufficient_history"] and not truncated
        baseline = ref["avg_30d"] if confident else None
        expired = (snap.searched_at < current_time - timedelta(hours=settings.DEAL_MAX_AGE_HOURS)
                   or snap.depart_date < taipei_today())
        record = details.get(snap.id)
        google_query = (f"Flights from {snap.origin} to {snap.destination} on "
                        f"{snap.depart_date} returning {snap.return_date} nonstop")
        result.append({
            "id": snap.id, "origin": snap.origin, "destination": snap.destination,
            "depart_date": snap.depart_date, "return_date": snap.return_date,
            "trip_days": (date.fromisoformat(snap.return_date)-date.fromisoformat(snap.depart_date)).days+1,
            "price_twd": snap.price_twd, "currency": snap.currency, "adults": snap.adults,
            "cabin": snap.cabin, "direct_only": snap.direct_only,
            "airline": record.airline if record else None,
            "searched_at": iso_utc(snap.searched_at), "expired": expired,
            "baseline_confident": confident, "baseline_twd": baseline,
            "drop_pct": round((baseline-snap.price_twd)/baseline*100, 1) if baseline else None,
            "prior_observed_days": ref["observed_days"], "history_truncated": truncated,
            "source": "Google Flights", "baggage_verified": False,
            "source_url": "https://www.google.com/travel/flights?"+urlencode({"q": google_query, "curr": "TWD"}),
        })
    return result


@app.get("/api/ui/quotes")
def quotes(origin: Optional[str] = None, destination: Optional[str] = None,
           start_date: Optional[date] = None, end_date: Optional[date] = None,
           min_days: int = Query(default=2, ge=2, le=31),
           max_days: int = Query(default=31, ge=2, le=31),
           max_price: Optional[int] = Query(default=None, ge=1, le=1000000),
           limit: int = Query(default=48, ge=1, le=100),
           offset: int = Query(default=0, ge=0, le=5000),
           sort: Literal["price", "recent"] = "price"):
    start = start_date or date.fromisoformat(taipei_today())
    end = end_date or start+timedelta(days=180)
    if end <= start or (end-start).days > 366 or min_days > max_days:
        raise HTTPException(status_code=422, detail="Invalid date or trip duration range")
    stmt = latest_query(start.isoformat(), end.isoformat(),
                        airport_codes(origin, TAIWAN_AIRPORTS), airport_codes(destination, JAPAN_AIRPORTS))
    stmt = stmt.where(SearchSnapshot.duration_days >= min_days-1,
                      SearchSnapshot.duration_days <= max_days-1,
                      SearchSnapshot.searched_at >= now_utc()-timedelta(hours=settings.DEAL_MAX_AGE_HOURS))
    if max_price is not None:
        stmt = stmt.where(SearchSnapshot.price_twd <= max_price)
    order = (SearchSnapshot.searched_at.desc(), SearchSnapshot.id) if sort == "recent" else (
        SearchSnapshot.price_twd.asc(), SearchSnapshot.id)
    with Session(engine) as session:
        rows = session.exec(stmt.order_by(*order).offset(offset).limit(limit+1)).all()
        data = annotate(session, rows[:limit])
    return {"quotes": data, "next_offset": offset+limit if len(rows) > limit else None,
            "generated_at": iso_utc(now_utc()), "demo": False,
            "note": "Only observed quotes; baggage and final availability require source confirmation."}


@app.get("/api/ui/quote/{snapshot_id}")
def quote_detail(snapshot_id: UUID):
    with Session(engine) as session:
        snap = session.get(SearchSnapshot, str(snapshot_id))
        if snap is None:
            raise HTTPException(status_code=404, detail="Quote not found")
        return annotate(session, [snap])[0]


@app.get("/api/ui/dates/{origin}/{destination}")
def dates(origin: str, destination: str):
    orig, dest = airport_codes(origin, TAIWAN_AIRPORTS), airport_codes(destination, JAPAN_AIRPORTS)
    if len(orig) != 1 or len(dest) != 1:
        raise HTTPException(status_code=422, detail="One route is required")
    today = date.fromisoformat(taipei_today())
    stmt = latest_query(today.isoformat(), (today+timedelta(days=366)).isoformat(), orig, dest)
    with Session(engine) as session:
        rows = session.exec(stmt.order_by(SearchSnapshot.depart_date, SearchSnapshot.return_date).limit(181)).all()
        data = annotate(session, rows[:180])
    return {"quotes": data, "truncated": len(rows) > 180,
            "note": "Each row is a different travel-date combination, not an observation-time trend."}


def worker_health():
    path = Path(settings.DB_PATH).parent / "worker-health.json"
    try:
        if path.stat().st_size > 8192:
            raise ValueError("Invalid heartbeat size")
        payload = json.loads(path.read_text())
        stamp = datetime.fromisoformat(payload["heartbeat_at"]).astimezone(timezone.utc)
        age = (datetime.now(timezone.utc)-stamp).total_seconds()
        state = payload.get("status")
        if state not in {"idle", "scanning", "error", "stopped"} or not 0 <= age <= 90:
            return {"status": "stale", "heartbeat_at": iso_utc(stamp.replace(tzinfo=None))}
        return {"status": state, "heartbeat_at": payload["heartbeat_at"]}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "not_started", "heartbeat_at": None}


@app.get("/api/ui/config")
def ui_config():
    with Session(engine) as session:
        routes = session.exec(select(Route).where(Route.active == True).order_by(Route.priority.desc())).all()
        total = session.exec(select(func.count(SearchSnapshot.id))).one()
        last = session.exec(select(func.max(SearchSnapshot.searched_at))).one()
    return {"ui_version": "2.0", "public_mode": is_public(), "manual_scan_requires_key": bool(settings.API_KEY) or is_public(),
            "origins": [a.model_dump() for a in TAIWAN_AIRPORTS.values()],
            "destinations": [a.model_dump() for a in JAPAN_AIRPORTS.values()],
            "routes": [{"origin": r.origin, "destination": r.destination} for r in routes],
            "search_snapshots": total, "last_quote_at": iso_utc(last),
            "worker": worker_health(), "notifications": {
                "ntfy": bool(settings.NTFY_ENABLED), "telegram": bool(settings.TELEGRAM_ENABLED)},
            "watchlist_scope": "browser_only", "source_count": 1}


@app.get("/api/ui/access", dependencies=[Depends(admin_key)])
def access():
    return {"authorized": True}


class ParseRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


@app.post("/api/ui/parse")
def parse(req: ParseRequest):
    return {"intent": NLPIntentParser.parse(req.query),
            "requires_confirmation": True, "method": "rule_based"}
