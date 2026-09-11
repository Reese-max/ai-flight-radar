"""Bounded scans, per-task leases, truthful snapshots and expiring quotes."""
import json
import logging
import time
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from sqlmodel import Session, select
from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert
from core.database import engine
from core.models import SearchTask, FlightSearchRecord, Deal
from core.snapshots import TaskLease
from providers.fast_flights_impl import FastFlightsProvider
from engine.analyzer import PriceAnalyzer
from engine.deal_scorer import DealScorer
from engine.planner import ProgressivePlanner
from notifier.dispatcher import AlertDispatcher
from config.settings import settings

logger = logging.getLogger(__name__)


def taipei_today():
    return datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()


class RadarScheduler:
    def __init__(self, provider=None):
        self.provider = provider if provider is not None else FastFlightsProvider()
        self.running = False

    @staticmethod
    def _claim(task_id: int, owner: str) -> bool:
        now = datetime.utcnow()
        values = dict(task_id=task_id, owner=owner,
                      expires_at=now + timedelta(seconds=settings.TASK_LEASE_SECONDS))
        with Session(engine) as session:
            result = session.execute(insert(TaskLease).values(**values).on_conflict_do_update(
                index_elements=["task_id"], set_=values, where=TaskLease.expires_at <= now))
            session.commit()
            return result.rowcount == 1

    @staticmethod
    def _release(task_id: int, owner: str):
        with Session(engine) as session:
            session.execute(delete(TaskLease).where(TaskLease.task_id == task_id, TaskLease.owner == owner))
            session.commit()

    @staticmethod
    def expire_deals():
        cutoff = datetime.utcnow() - timedelta(hours=settings.DEAL_MAX_AGE_HOURS)
        with Session(engine) as session:
            session.execute(update(Deal).where(
                Deal.status == "active",
                (Deal.created_at < cutoff) | (Deal.depart_date < taipei_today()),
            ).values(status="expired"))
            session.commit()

    @staticmethod
    def _reschedule(task_id: int, delay: int, *, tier=None, price=None, score=None):
        now = datetime.utcnow()
        with Session(engine) as session:
            task = session.get(SearchTask, task_id)
            if task:
                task.last_searched_at = now
                task.next_run_at = now + timedelta(seconds=delay)
                if tier is not None:
                    task.tier = tier
                if price is not None:
                    task.last_price = price
                if score is not None:
                    task.last_deal_score = score
                session.add(task)
                session.commit()

    def process_task(self, task_id: int) -> bool:
        owner = str(uuid4())
        if not self._claim(task_id, owner):
            return False
        try:
            self.expire_deals()
            with Session(engine) as session:
                task = session.get(SearchTask, task_id)
                if not task or task.depart_date < taipei_today():
                    return False
                origin, destination = task.origin, task.destination
                depart, ret, duration = task.depart_date, task.return_date, task.duration_days
            # Snapshot comparison must precede this batch's insertion.
            before = datetime.utcnow()
            offers = self.provider.search(origin, destination, depart, ret, max_stops=0)
            offers = [off for off in offers if (
                off.price_twd > 0 and off.is_direct and off.stops == 0
                and off.origin == origin and off.destination == destination
                and off.depart_date == depart and off.return_date == ret
            )]
            offers.sort(key=lambda off: off.price_twd)
            if not offers:
                self._reschedule(task_id, settings.TIER_1_INTERVAL_SEC, tier=1)
                return False
            best = offers[0]
            reference = PriceAnalyzer.get_reference_stats(
                origin, destination, duration, depart_date=depart, return_date=ret, before=before)
            score, level, reasons, drop = DealScorer.evaluate(best, reference)
            observed_at = datetime.utcnow()
            with Session(engine) as session:
                for off in offers:
                    session.add(FlightSearchRecord(
                        origin=origin, destination=destination, trip_type=off.trip_type,
                        depart_date=depart, return_date=ret, duration_days=duration,
                        airline=off.primary_airline, price_twd=off.price_twd,
                        is_direct=off.is_direct, stops=off.stops,
                        depart_time=off.depart_time_str, arrival_time=off.arrival_time_str,
                        duration_mins=off.total_duration_mins, source="google_flights",
                        searched_at=observed_at,
                    ))
                session.add(PriceAnalyzer.make_snapshot(best, len(offers), searched_at=observed_at))
                # A new quote supersedes older active quotes, not alert history.
                session.execute(update(Deal).where(
                    Deal.origin == origin, Deal.destination == destination,
                    Deal.depart_date == depart, Deal.return_date == ret,
                    Deal.status == "active",
                ).values(status="expired"))
                deal = None
                if reference["sufficient_history"] and (score >= 70 or drop >= 15):
                    deal = Deal(
                        origin=origin, destination=destination, depart_date=depart,
                        return_date=ret, duration_days=duration, airline=best.primary_airline,
                        price_twd=best.price_twd, ref_price_twd=round(reference["avg_30d"]),
                        drop_pct=drop, deal_score=score, deal_level=level,
                        reasons=json.dumps(reasons, ensure_ascii=False), is_direct=best.is_direct,
                        status="active", created_at=observed_at, notified=False,
                    )
                    session.add(deal)
                session.commit()
                if deal is not None:
                    session.refresh(deal)
            PriceAnalyzer.update_route_stats(origin, destination, duration)
            if score >= 85 or drop >= 35:
                tier, delay = 4, settings.TIER_4_INTERVAL_SEC
            elif score >= 75 or drop >= 20:
                tier, delay = 3, settings.TIER_3_INTERVAL_SEC
            elif drop >= 10:
                tier, delay = 2, settings.TIER_2_INTERVAL_SEC
            else:
                tier, delay = 1, settings.TIER_1_INTERVAL_SEC
            self._reschedule(task_id, delay, tier=tier, price=best.price_twd, score=score)
            if deal is not None:
                AlertDispatcher.dispatch_deal(deal)
            return True
        except Exception:
            # Provider or parse failures must not poison the price history with zero.
            logger.exception("Search task %s failed; retry delayed", task_id)
            self._reschedule(task_id, settings.ERROR_RETRY_SECONDS)
            return False
        finally:
            self._release(task_id, owner)

    def run_loop(self, max_iterations=None):
        if max_iterations is not None and max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self.running = True
        seeded_day = None
        iterations = 0
        while self.running:
            today = taipei_today()
            if seeded_day != today:
                ProgressivePlanner.generate_search_tasks()
                self.expire_deals()
                seeded_day = today
            with Session(engine) as session:
                task = session.exec(select(SearchTask).where(
                    SearchTask.next_run_at <= datetime.utcnow(),
                    SearchTask.depart_date >= today,
                    SearchTask.id.not_in(select(TaskLease.task_id).where(
                        TaskLease.expires_at > datetime.utcnow())),
                ).order_by(SearchTask.next_run_at.asc(), SearchTask.tier.desc(),
                           SearchTask.priority.desc()).limit(1)).first()
            if not task:
                if max_iterations is not None:
                    break
                time.sleep(15)
                continue
            self.process_task(task.id)
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
        self.running = False

    def stop(self):
        self.running = False
