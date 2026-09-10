import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select, func

from core.database import engine, init_db
from core.models import Route, Deal, FlightSearchRecord, SearchTask, RouteStats
from engine.scheduler import RadarScheduler
from engine.planner import ProgressivePlanner
from ai.nlp_parser import NLPIntentParser
from ai.insight_generator import DealInsightGenerator
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS

app = FastAPI(title="AI Flight Radar API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler_instance = RadarScheduler()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def serve_dashboard():
    web_file = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    if os.path.exists(web_file):
        return FileResponse(web_file)
    return {"message": "AI Flight Radar API running. Web dashboard not found."}

@app.get("/api/stats/overview")
def get_stats_overview():
    with Session(engine) as session:
        routes_count = session.exec(select(func.count(Route.id))).one()
        deals_count = session.exec(select(func.count(Deal.id)).where(Deal.status == "active")).one()
        records_count = session.exec(select(func.count(FlightSearchRecord.id))).one()
        tasks_count = session.exec(select(func.count(SearchTask.id))).one()

    return {
        "total_routes": routes_count,
        "active_deals": deals_count,
        "flight_records": records_count,
        "queued_tasks": tasks_count
    }

@app.get("/api/deals")
def get_deals(
    min_score: int = 60, 
    origin: Optional[str] = None, 
    destination: Optional[str] = None,
    mode: Optional[str] = None  # "weekend", "minimal_leave", "country_radar", "any_dest"
):
    with Session(engine) as session:
        stmt = select(Deal).where(Deal.status == "active", Deal.deal_score >= min_score)
        
        if origin:
            stmt = stmt.where(Deal.origin == origin.upper())
        if destination:
            stmt = stmt.where(Deal.destination == destination.upper())

        raw_deals = session.exec(stmt.order_by(Deal.deal_score.desc(), Deal.price_twd.asc())).all()

        # Mode 2: 國家雷達 (Country Radar) - 每個日本城市只取第一名最超值 Deal
        if mode == "country_radar":
            seen_cities = {}
            for d in raw_deals:
                dest_info = JAPAN_AIRPORTS.get(d.destination)
                city = dest_info.city if dest_info else d.destination
                if city not in seen_cities:
                    seen_cities[city] = d
            return list(seen_cities.values())

        # Mode 3: 目的地不限 (Any Destination) - 價格最低優先
        elif mode == "any_dest":
            return sorted(raw_deals, key=lambda x: x.price_twd)

        # Mode 4: 週末快閃模式 (Weekend Trips: 週五/週六出發，週日/週一返台)
        elif mode == "weekend":
            filtered = []
            for d in raw_deals:
                try:
                    dep_weekday = datetime.strptime(d.depart_date, "%Y-%m-%d").weekday() # 4=Fri, 5=Sat
                    ret_weekday = datetime.strptime(d.return_date, "%Y-%m-%d").weekday() # 6=Sun, 0=Mon
                    if dep_weekday in [4, 5] and ret_weekday in [6, 0]:
                        filtered.append(d)
                except Exception:
                    pass
            return filtered

        # Mode 5: 最少請假模式 (Minimal Leave: 停留 3~4 天且橫跨週六日，最多請假 1 天)
        elif mode == "minimal_leave":
            filtered = []
            for d in raw_deals:
                if d.duration_days in [3, 4]:
                    try:
                        dep_weekday = datetime.strptime(d.depart_date, "%Y-%m-%d").weekday()
                        # Fri-Sun (3d, 0 off), Fri-Mon (4d, 1 off), Sat-Tue (4d, 1 off)
                        if dep_weekday in [4, 5]:
                            filtered.append(d)
                    except Exception:
                        pass
            return filtered

        return raw_deals[:50]

@app.get("/api/briefing")
def get_briefing():
    return {
        "briefing": DealInsightGenerator.generate_daily_briefing()
    }

@app.get("/api/routes")
def get_routes():
    with Session(engine) as session:
        routes = session.exec(select(Route).where(Route.active == True).order_by(Route.priority.desc())).all()
        result = []
        for r in routes:
            stats = session.exec(
                select(RouteStats).where(
                    RouteStats.origin == r.origin,
                    RouteStats.destination == r.destination
                )
            ).first()
            result.append({
                "id": r.id,
                "origin": r.origin,
                "destination": r.destination,
                "country": r.country,
                "priority": r.priority,
                "stats": stats
            })
        return result

@app.get("/api/history/{origin}/{destination}")
def get_price_history(origin: str, destination: str):
    """Returns price trend data for charting and calendar heatmap."""
    with Session(engine) as session:
        stmt = select(
            FlightSearchRecord.depart_date,
            FlightSearchRecord.return_date,
            func.min(FlightSearchRecord.price_twd).label("min_price"),
            func.avg(FlightSearchRecord.price_twd).label("avg_price"),
            func.count(FlightSearchRecord.id).label("count")
        ).where(
            FlightSearchRecord.origin == origin.upper(),
            FlightSearchRecord.destination == destination.upper()
        ).group_by(
            FlightSearchRecord.depart_date,
            FlightSearchRecord.return_date
        ).order_by(FlightSearchRecord.depart_date.asc())

        rows = session.exec(stmt).all()
        
        # Also get benchmark stats
        stats = session.exec(
            select(RouteStats).where(
                RouteStats.origin == origin.upper(),
                RouteStats.destination == destination.upper()
            )
        ).first()

        history = [
            {
                "depart_date": r[0],
                "return_date": r[1],
                "min_price": r[2],
                "avg_price": round(float(r[3]), 0),
                "count": r[4]
            }
            for r in rows
        ]

        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "benchmark_30d": stats.avg_30d if stats else None,
            "min_historical": stats.min_historical if stats else None,
            "data": history
        }

class NLPSearchRequest(BaseModel):
    query: str

@app.post("/api/search/nlp")
def search_nlp(req: NLPSearchRequest):
    intent = NLPIntentParser.parse(req.query)
    
    with Session(engine) as session:
        stmt = select(Deal).where(Deal.status == "active")
        if intent.origins:
            stmt = stmt.where(Deal.origin.in_(intent.origins))
        if intent.destinations:
            stmt = stmt.where(Deal.destination.in_(intent.destinations))
        if intent.max_budget_twd:
            stmt = stmt.where(Deal.price_twd <= intent.max_budget_twd)
        if intent.direct_only:
            stmt = stmt.where(Deal.is_direct == True)

        deals = session.exec(stmt.order_by(Deal.deal_score.desc())).all()

    return {
        "intent": intent,
        "matching_deals": deals
    }

class TriggerScanRequest(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None

@app.post("/api/scan/trigger")
def trigger_scan(req: TriggerScanRequest, background_tasks: BackgroundTasks):
    with Session(engine) as session:
        if req.origin and req.destination:
            stmt = select(SearchTask).where(
                SearchTask.origin == req.origin.upper(),
                SearchTask.destination == req.destination.upper()
            ).order_by(SearchTask.next_run_at.asc())
            task = session.exec(stmt).first()
            if not task:
                dep = (datetime.utcnow() + timedelta(days=25)).strftime("%Y-%m-%d")
                ret = (datetime.utcnow() + timedelta(days=29)).strftime("%Y-%m-%d")
                task = SearchTask(
                    origin=req.origin.upper(),
                    destination=req.destination.upper(),
                    depart_date=dep,
                    return_date=ret,
                    duration_days=4,
                    tier=1,
                    priority=10,
                    next_run_at=datetime.utcnow()
                )
                session.add(task)
                session.commit()
                session.refresh(task)
        else:
            stmt = select(SearchTask).order_by(SearchTask.priority.desc(), SearchTask.next_run_at.asc())
            task = session.exec(stmt).first()

    if not task:
        ProgressivePlanner.generate_search_tasks()
        with Session(engine) as session:
            task = session.exec(select(SearchTask).order_by(SearchTask.priority.desc())).first()

    if task:
        background_tasks.add_task(scheduler_instance.process_task, task.id)
        return {
            "status": "triggered",
            "message": f"已在背景開始掃描 {task.origin} ➔ {task.destination} ({task.depart_date} ~ {task.return_date})"
        }

    return {"status": "error", "message": "未能找到可執行的任務"}
