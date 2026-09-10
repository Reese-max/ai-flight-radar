import logging
from datetime import datetime, timedelta
from typing import List
from sqlmodel import Session, select
from core.database import engine
from core.models import Route, SearchTask

logger = logging.getLogger(__name__)

class ProgressivePlanner:
    @staticmethod
    def generate_search_tasks(
        days_ahead_start: int = 14,
        days_ahead_end: int = 90,
        durations: List[int] = [4, 5],
        step_days: int = 5
    ) -> int:
        """
        Generates progressive sampling tasks for active routes.
        Avoids brute force by picking smart date intervals (e.g. every 5 days, sampling weekends and weekdays).
        """
        now = datetime.utcnow()
        created_count = 0

        with Session(engine) as session:
            active_routes = session.exec(select(Route).where(Route.active == True)).all()
            if not active_routes:
                logger.warning("No active routes found in database.")
                return 0

            for route in active_routes:
                for dur in durations:
                    cur_offset = days_ahead_start
                    while cur_offset <= days_ahead_end:
                        dep_dt = (now + timedelta(days=cur_offset)).date()
                        ret_dt = dep_dt + timedelta(days=dur)
                        
                        dep_str = dep_dt.strftime("%Y-%m-%d")
                        ret_str = ret_dt.strftime("%Y-%m-%d")

                        # Check if task already exists
                        stmt = select(SearchTask).where(
                            SearchTask.origin == route.origin,
                            SearchTask.destination == route.destination,
                            SearchTask.depart_date == dep_str,
                            SearchTask.return_date == ret_str
                        )
                        existing = session.exec(stmt).first()
                        if not existing:
                            task = SearchTask(
                                origin=route.origin,
                                destination=route.destination,
                                depart_date=dep_str,
                                return_date=ret_str,
                                duration_days=dur,
                                tier=1,
                                priority=route.priority,
                                next_run_at=now
                            )
                            session.add(task)
                            created_count += 1

                        cur_offset += step_days

            session.commit()

        logger.info(f"ProgressivePlanner generated {created_count} new search tasks.")
        return created_count
