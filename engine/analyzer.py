import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlmodel import Session, select, func
from core.models import FlightSearchRecord, RouteStats
from core.database import engine

logger = logging.getLogger(__name__)

# Realistic Taiwan -> Japan Market Benchmark Baseline (TWD round-trip)
# Used as cold-start baseline before long-term historical records accumulate
DEFAULT_ROUTE_BENCHMARKS: Dict[str, int] = {
    "TPE-NRT": 13000,
    "TPE-HND": 14500,
    "TSA-HND": 15500,
    "TPE-KIX": 12500,
    "TPE-FUK": 11500,
    "TPE-OKA": 9000,
    "TPE-NGO": 11800,
    "TPE-CTS": 16500,
    "TPE-SDJ": 13500,
    "TPE-KMJ": 11000,
    "TPE-KOJ": 12000,
    "TPE-OKJ": 11500,
    "TPE-TAK": 11500,
    "KHH-NRT": 13500,
    "KHH-KIX": 13000,
    "KHH-FUK": 12000,
    "KHH-OKA": 9500,
}

class PriceAnalyzer:
    @staticmethod
    def get_benchmark_price(origin: str, destination: str) -> int:
        key = f"{origin.upper()}-{destination.upper()}"
        return DEFAULT_ROUTE_BENCHMARKS.get(key, 12000)

    @staticmethod
    def update_route_stats(origin: str, destination: str, duration_days: int) -> RouteStats:
        """Calculates and updates 7d, 30d, 90d moving averages and historical extremes."""
        now = datetime.utcnow()
        t7 = now - timedelta(days=7)
        t30 = now - timedelta(days=30)
        t90 = now - timedelta(days=90)

        with Session(engine) as session:
            # Query stats from records
            base_stmt = select(FlightSearchRecord).where(
                FlightSearchRecord.origin == origin,
                FlightSearchRecord.destination == destination,
                FlightSearchRecord.duration_days == duration_days
            )
            records = session.exec(base_stmt).all()

            if not records:
                benchmark = PriceAnalyzer.get_benchmark_price(origin, destination)
                stats = RouteStats(
                    origin=origin,
                    destination=destination,
                    duration_days=duration_days,
                    sample_count=0,
                    avg_7d=float(benchmark),
                    avg_30d=float(benchmark),
                    avg_90d=float(benchmark),
                    min_historical=benchmark,
                    max_historical=benchmark,
                    last_updated=now
                )
                session.add(stats)
                session.commit()
                session.refresh(stats)
                return stats

            # Filter time ranges
            prices_all = [r.price_twd for r in records if r.price_twd > 0]
            prices_7d = [r.price_twd for r in records if r.price_twd > 0 and r.searched_at >= t7]
            prices_30d = [r.price_twd for r in records if r.price_twd > 0 and r.searched_at >= t30]
            prices_90d = [r.price_twd for r in records if r.price_twd > 0 and r.searched_at >= t90]

            benchmark = PriceAnalyzer.get_benchmark_price(origin, destination)

            avg_7 = sum(prices_7d) / len(prices_7d) if prices_7d else float(benchmark)
            avg_30 = sum(prices_30d) / len(prices_30d) if prices_30d else float(benchmark)
            avg_90 = sum(prices_90d) / len(prices_90d) if prices_90d else float(benchmark)
            min_hist = min(prices_all) if prices_all else benchmark
            max_hist = max(prices_all) if prices_all else benchmark

            # Find existing stats or create
            stmt = select(RouteStats).where(
                RouteStats.origin == origin,
                RouteStats.destination == destination,
                RouteStats.duration_days == duration_days
            )
            stats = session.exec(stmt).first()
            if not stats:
                stats = RouteStats(
                    origin=origin,
                    destination=destination,
                    duration_days=duration_days
                )

            stats.sample_count = len(records)
            stats.avg_7d = round(avg_7, 1)
            stats.avg_30d = round(avg_30, 1)
            stats.avg_90d = round(avg_90, 1)
            stats.min_historical = min_hist
            stats.max_historical = max_hist
            stats.last_updated = now

            session.add(stats)
            session.commit()
            session.refresh(stats)
            return stats

    @staticmethod
    def get_reference_stats(origin: str, destination: str, duration_days: int) -> Dict[str, float]:
        """Returns baseline / moving avg price references."""
        with Session(engine) as session:
            stmt = select(RouteStats).where(
                RouteStats.origin == origin,
                RouteStats.destination == destination,
                RouteStats.duration_days == duration_days
            )
            stats = session.exec(stmt).first()
            benchmark = float(PriceAnalyzer.get_benchmark_price(origin, destination))

            if stats and stats.sample_count > 0:
                return {
                    "avg_7d": stats.avg_7d or benchmark,
                    "avg_30d": stats.avg_30d or benchmark,
                    "avg_90d": stats.avg_90d or benchmark,
                    "min_historical": float(stats.min_historical or benchmark),
                    "is_cold_start": stats.sample_count < 3
                }
            else:
                return {
                    "avg_7d": benchmark,
                    "avg_30d": benchmark,
                    "avg_90d": benchmark,
                    "min_historical": benchmark,
                    "is_cold_start": True
                }
