import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select
from core.database import engine
from core.models import SearchTask, FlightSearchRecord, Deal
from providers.fast_flights_impl import FastFlightsProvider
from engine.analyzer import PriceAnalyzer
from engine.deal_scorer import DealScorer
from engine.planner import ProgressivePlanner
from notifier.dispatcher import AlertDispatcher
from config.settings import settings

logger = logging.getLogger(__name__)

class RadarScheduler:
    def __init__(self):
        self.provider = FastFlightsProvider()
        self.running = False

    def process_task(self, task_id: int) -> bool:
        """Executes a single search task, updates stats, scores deals, and reschedules."""
        with Session(engine) as session:
            task = session.get(SearchTask, task_id)
            if not task:
                return False

            origin = task.origin
            destination = task.destination
            depart_date = task.depart_date
            return_date = task.return_date
            duration_days = task.duration_days

        logger.info(f"Scanning route: {origin} -> {destination} ({depart_date} ~ {return_date})")
        offers = self.provider.search(origin, destination, depart_date, return_date, max_stops=0)

        now = datetime.utcnow()
        if not offers:
            logger.warning(f"No direct offers found for {origin}->{destination} on {depart_date}")
            # Re-schedule with Tier 1 delay
            with Session(engine) as session:
                task = session.get(SearchTask, task_id)
                if task:
                    task.last_searched_at = now
                    task.next_run_at = now + timedelta(seconds=settings.TIER_1_INTERVAL_SEC)
                    session.add(task)
                    session.commit()
            return False

        # Best offer is first since provider sorts ascending
        best_offer = offers[0]
        logger.info(f"Best offer found: {best_offer.primary_airline} NT${best_offer.price_twd:,}")

        # 1. Save flight records
        with Session(engine) as session:
            for off in offers:
                record = FlightSearchRecord(
                    origin=off.origin,
                    destination=off.destination,
                    trip_type=off.trip_type,
                    depart_date=off.depart_date,
                    return_date=off.return_date,
                    duration_days=off.duration_days,
                    airline=off.primary_airline,
                    price_twd=off.price_twd,
                    is_direct=off.is_direct,
                    stops=off.stops,
                    depart_time=off.depart_time_str,
                    arrival_time=off.arrival_time_str,
                    duration_mins=off.total_duration_mins,
                    source="google_flights",
                    searched_at=now
                )
                session.add(record)
            session.commit()

        # 2. Update Route Stats
        PriceAnalyzer.update_route_stats(origin, destination, duration_days)
        ref_stats = PriceAnalyzer.get_reference_stats(origin, destination, duration_days)

        # 3. Score the best deal
        score, deal_level, reasons, drop_pct = DealScorer.evaluate(best_offer, ref_stats)

        # 4. Handle Deal creation and notification
        if score >= 70 or drop_pct >= 15.0:
            deal = Deal(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                duration_days=duration_days,
                airline=best_offer.primary_airline,
                price_twd=best_offer.price_twd,
                ref_price_twd=int(ref_stats["avg_30d"]),
                drop_pct=drop_pct,
                deal_score=score,
                deal_level=deal_level,
                reasons=json.dumps(reasons, ensure_ascii=False),
                is_direct=best_offer.is_direct,
                status="active",
                created_at=now,
                notified=False
            )
            with Session(engine) as session:
                session.add(deal)
                session.commit()
                session.refresh(deal)

            # Dispatch notification if it qualifies
            AlertDispatcher.dispatch_deal(deal)

        # 5. Dynamically adjust Tier and Next Run Time
        if score >= 85 or drop_pct >= 35.0:
            new_tier = 4
            delay_sec = settings.TIER_4_INTERVAL_SEC # 30 min
        elif score >= 75 or drop_pct >= 20.0:
            new_tier = 3
            delay_sec = settings.TIER_3_INTERVAL_SEC # 1 hour
        elif drop_pct >= 10.0:
            new_tier = 2
            delay_sec = settings.TIER_2_INTERVAL_SEC # 2 hours
        else:
            new_tier = 1
            delay_sec = settings.TIER_1_INTERVAL_SEC # 6 hours

        with Session(engine) as session:
            task = session.get(SearchTask, task_id)
            if task:
                task.tier = new_tier
                task.last_price = best_offer.price_twd
                task.last_deal_score = score
                task.last_searched_at = now
                task.next_run_at = now + timedelta(seconds=delay_sec)
                session.add(task)
                session.commit()

        return True

    def run_loop(self, max_iterations: Optional[int] = None):
        """Main autonomous scanning loop."""
        self.running = True
        logger.info("Starting AI Flight Radar Autonomous Loop...")
        
        # Ensure task queue is seeded
        with Session(engine) as session:
            task_count = session.exec(select(SearchTask)).all()
            if len(task_count) < 5:
                ProgressivePlanner.generate_search_tasks()

        iterations = 0
        while self.running:
            now = datetime.utcnow()
            with Session(engine) as session:
                # Pick next ready task by priority and due time
                stmt = select(SearchTask).where(
                    SearchTask.next_run_at <= now
                ).order_by(
                    SearchTask.priority.desc(),
                    SearchTask.tier.desc(),
                    SearchTask.next_run_at.asc()
                )
                task = session.exec(stmt).first()

            if not task:
                logger.info("No due tasks right now. Sleeping 15s...")
                time.sleep(15)
                continue

            try:
                self.process_task(task.id)
            except Exception as e:
                logger.error(f"Error processing task #{task.id}: {e}", exc_info=True)

            iterations += 1
            if max_iterations and iterations >= max_iterations:
                logger.info(f"Reached max iterations ({max_iterations}). Exiting loop.")
                break

    def stop(self):
        self.running = False
