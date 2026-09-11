"""Local-first dashboard API. Write access can be protected with API_KEY."""
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
import secrets
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select, func
from core.database import engine, init_db
from core.models import Route, Deal, FlightSearchRecord, SearchTask, RouteStats
from core.snapshots import SearchSnapshot
from engine.scheduler import RadarScheduler, taipei_today
from engine.planner import ProgressivePlanner
from engine.price_history import summarize_history
from ai.nlp_parser import NLPIntentParser
from ai.insight_generator import DealInsightGenerator
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS
from config.settings import settings


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="AI Flight Radar API", version="1.2.0", lifespan=lifespan)
# The bundled UI is same-origin; unrestricted credentialed CORS is unnecessary.
scheduler_instance = RadarScheduler()


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    if settings.API_KEY and not secrets.compare_digest(
        (x_api_key or "").encode(), settings.API_KEY.encode()
    ):
        raise HTTPException(status_code=401, detail="Valid X-API-Key required")


def live_deals():
    return select(Deal).where(
        Deal.status == "active", Deal.depart_date >= taipei_today(),
        Deal.created_at >= datetime.utcnow() - timedelta(hours=settings.DEAL_MAX_AGE_HOURS),
    )


@app.get("/")
def serve_dashboard():
    page = Path(__file__).resolve().parent.parent / "web" / "index.html"
    return FileResponse(page) if page.exists() else {"message": "AI Flight Radar API running"}


@app.get("/api/health")
def health():
    with Session(engine) as session:
        session.exec(select(func.count(SearchSnapshot.id))).one()
    return {"status": "ok", "version": "1.2.0", "price_method": "search_snapshots_v1"}


@app.get("/api/stats/overview")
def get_stats_overview():
    with Session(engine) as session:
        return {
            "total_routes": session.exec(select(func.count(Route.id))).one(),
            "active_deals": len(session.exec(live_deals()).all()),
            "flight_records": session.exec(select(func.count(FlightSearchRecord.id))).one(),
            "search_snapshots": session.exec(select(func.count(SearchSnapshot.id))).one(),
            "queued_tasks": session.exec(select(func.count(SearchTask.id)).where(
                SearchTask.depart_date >= taipei_today())).one(),
        }


@app.get("/api/deals")
def get_deals(min_score: int = Query(default=60, ge=0, le=100),
              origin: Optional[str] = None, destination: Optional[str] = None,
              mode: Optional[str] = None):
    with Session(engine) as session:
        stmt = live_deals().where(Deal.deal_score >= min_score)
        if origin:
            stmt = stmt.where(Deal.origin == origin.upper())
        if destination:
            stmt = stmt.where(Deal.destination == destination.upper())
        deals = session.exec(stmt.order_by(Deal.deal_score.desc(), Deal.price_twd.asc())).all()
    if mode == "country_radar":
        cities = {}
        for deal in deals:
            airport = JAPAN_AIRPORTS.get(deal.destination)
            cities.setdefault(airport.city if airport else deal.destination, deal)
        return list(cities.values())[:50]
    if mode == "any_dest":
        return sorted(deals, key=lambda d: d.price_twd)[:50]
    if mode in {"weekend", "minimal_leave"}:
        selected = []
        for deal in deals:
            try:
                dep, ret = datetime.fromisoformat(deal.depart_date), datetime.fromisoformat(deal.return_date)
                if mode == "weekend":
                    matches = dep.weekday() in {4, 5} and ret.weekday() in {6, 0} and (ret-dep).days <= 4
                else:
                    # Conservative full-day weekday count; no invented holiday calendar.
                    weekdays = sum((dep+timedelta(days=i)).weekday() < 5
                                   for i in range((ret-dep).days + 1))
                    matches = 0 <= (ret-dep).days <= 4 and weekdays <= 1
                if matches:
                    selected.append(deal)
            except ValueError:
                continue
        return selected[:50]
    return deals[:50]


@app.get("/api/briefing")
def get_briefing():
    return {"briefing": DealInsightGenerator.generate_daily_briefing()}


@app.get("/api/routes")
def get_routes():
    with Session(engine) as session:
        routes = session.exec(select(Route).where(Route.active == True).order_by(Route.priority.desc())).all()
        return [{"id": route.id, "origin": route.origin, "destination": route.destination,
                 "country": route.country, "priority": route.priority,
                 "stats": session.exec(select(RouteStats).where(
                     RouteStats.origin == route.origin,
                     RouteStats.destination == route.destination,
                 )).first()} for route in routes]


@app.get("/api/history/{origin}/{destination}")
def get_price_history(origin: str, destination: str):
    now = datetime.utcnow()
    with Session(engine) as session:
        snapshots = session.exec(select(SearchSnapshot).where(
            SearchSnapshot.origin == origin.upper(), SearchSnapshot.destination == destination.upper(),
            SearchSnapshot.searched_at >= now - timedelta(days=90),
        )).all()
    grouped = defaultdict(list)
    for snapshot in snapshots:
        grouped[(snapshot.depart_date, snapshot.return_date)].append(snapshot)
    history = []
    for (dep, ret), rows in sorted(grouped.items()):
        ref = summarize_history([(r.searched_at, r.price_twd) for r in rows], before=now)
        history.append({"depart_date": dep, "return_date": ret,
                        "min_price": ref["min_historical"], "avg_price": ref["avg_30d"] if ref["avg_30d"] is not None else ref["avg_90d"],
                        "count": len(rows), "observed_days": ref["observed_days"],
                        "baseline_confident": ref["sufficient_history"]})
    return {"origin": origin.upper(), "destination": destination.upper(),
            "benchmark_30d": None, "min_historical": min((r.price_twd for r in snapshots), default=None),
            "data": history, "window_days": 90,
            "baseline_note": "各日期組合分開比較；只含本系統實際觀測，不提供虛構市場均價。"}


class NLPSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


@app.post("/api/search/nlp")
def search_nlp(req: NLPSearchRequest):
    intent = NLPIntentParser.parse(req.query)
    with Session(engine) as session:
        stmt = live_deals().where(
            Deal.depart_date >= intent.start_date, Deal.return_date <= intent.end_date,
            Deal.duration_days >= max(1, intent.min_duration - 1),
            Deal.duration_days <= max(1, intent.max_duration - 1),
        )
        if intent.origins:
            stmt = stmt.where(Deal.origin.in_(intent.origins))
        if intent.destinations:
            stmt = stmt.where(Deal.destination.in_(intent.destinations))
        if intent.max_budget_twd:
            stmt = stmt.where(Deal.price_twd <= intent.max_budget_twd)
        if intent.direct_only:
            stmt = stmt.where(Deal.is_direct == True)
        deals = session.exec(stmt.order_by(Deal.deal_score.desc()).limit(50)).all()
    return {"intent": intent, "matching_deals": deals}


class TriggerScanRequest(BaseModel):
    origin: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    destination: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{3}$")

    @model_validator(mode="after")
    def validate_route(self):
        if bool(self.origin) != bool(self.destination):
            raise ValueError("Provide both origin and destination, or neither")
        if self.origin:
            self.origin, self.destination = self.origin.upper(), self.destination.upper()
            if self.origin not in TAIWAN_AIRPORTS or self.destination not in JAPAN_AIRPORTS:
                raise ValueError("This version supports configured Taiwan/Japan airports only")
        return self


@app.post("/api/scan/trigger", dependencies=[Depends(require_api_key)])
def trigger_scan(req: TriggerScanRequest, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        stmt = select(SearchTask).where(SearchTask.depart_date >= taipei_today())
        if req.origin:
            stmt = stmt.where(SearchTask.origin == req.origin, SearchTask.destination == req.destination)
        task = session.exec(stmt.order_by(SearchTask.next_run_at.asc()).limit(1)).first()
        if task is None and req.origin:
            departure = datetime.fromisoformat(taipei_today()) + timedelta(days=25)
            task = SearchTask(origin=req.origin, destination=req.destination,
                              depart_date=departure.date().isoformat(),
                              return_date=(departure+timedelta(days=4)).date().isoformat(),
                              duration_days=4, priority=10)
            session.add(task)
            session.commit()
            session.refresh(task)
    if task is None:
        ProgressivePlanner.generate_search_tasks()
        with Session(engine) as session:
            task = session.exec(select(SearchTask).where(
                SearchTask.depart_date >= taipei_today()).limit(1)).first()
    if task is None:
        raise HTTPException(status_code=503, detail="No search tasks available")
    background_tasks.add_task(scheduler_instance.process_task, task.id)
    return {"status": "triggered", "message": f"已排入掃描：{task.origin} → {task.destination}"}
