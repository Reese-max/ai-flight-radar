"""Price references come from recorded search minima, never invented benchmarks."""
from datetime import datetime
from sqlmodel import Session, select
from core.database import engine
from core.models import RouteStats
from core.snapshots import SearchSnapshot
from engine.price_history import query_key, summarize_history


class PriceAnalyzer:
    @staticmethod
    def get_reference_stats(origin: str, destination: str, duration_days: int,
                            *, depart_date: str = None, return_date: str = None,
                            before: datetime = None) -> dict:
        before = before or datetime.utcnow()
        # Without exact dates a route-level aggregate must not become a deal baseline.
        if not depart_date or not return_date:
            return summarize_history([], before=before)
        key = query_key(origin, destination, depart_date, return_date)
        with Session(engine) as session:
            rows = session.exec(select(SearchSnapshot).where(
                SearchSnapshot.query_key == key,
                SearchSnapshot.searched_at < before,
            )).all()
            return summarize_history([(r.searched_at, r.price_twd) for r in rows], before=before)

    @staticmethod
    def make_snapshot(offer, offer_count: int, *, searched_at: datetime) -> SearchSnapshot:
        if offer_count < 1 or offer.price_twd <= 0:
            raise ValueError("A snapshot needs at least one valid offer")
        return SearchSnapshot(
            query_key=query_key(offer.origin, offer.destination,
                                offer.depart_date, offer.return_date),
            origin=offer.origin, destination=offer.destination,
            depart_date=offer.depart_date, return_date=offer.return_date,
            duration_days=offer.duration_days, price_twd=offer.price_twd,
            offer_count=offer_count, searched_at=searched_at,
        )

    @staticmethod
    def update_route_stats(origin: str, destination: str, duration_days: int) -> RouteStats:
        """Informational route summary only. Scoring uses the exact-query method."""
        now = datetime.utcnow()
        with Session(engine) as session:
            rows = session.exec(select(SearchSnapshot).where(
                SearchSnapshot.origin == origin,
                SearchSnapshot.destination == destination,
                SearchSnapshot.duration_days == duration_days,
            )).all()
            # Equalize polling frequency per query/day before a route-level summary.
            from collections import defaultdict
            from statistics import median
            grouped = defaultdict(list)
            for r in rows:
                grouped[(r.query_key, r.searched_at.date())].append(r.price_twd)
            observations = [(datetime.combine(day, datetime.min.time()), median(prices))
                            for (_, day), prices in grouped.items()]
            ref = summarize_history(observations, before=now)
            stats = session.exec(select(RouteStats).where(
                RouteStats.origin == origin,
                RouteStats.destination == destination,
                RouteStats.duration_days == duration_days,
            )).first()
            if stats is None:
                stats = RouteStats(origin=origin, destination=destination, duration_days=duration_days)
            stats.sample_count = len(rows)
            stats.avg_7d = ref["avg_7d"]
            stats.avg_30d = ref["avg_30d"]
            stats.avg_90d = ref["avg_90d"]
            stats.min_historical = min((r.price_twd for r in rows), default=None)
            stats.max_historical = max((r.price_twd for r in rows), default=None)
            stats.last_updated = now
            session.add(stats)
            session.commit()
            session.refresh(stats)
            return stats
