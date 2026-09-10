from datetime import datetime, timedelta
from sqlmodel import Session, select
from core.database import engine
from core.models import Deal
from config.settings import settings

class AlertThrottler:
    @staticmethod
    def should_alert(origin: str, destination: str, depart_date: str, return_date: str, current_price: int, deal_score: int) -> bool:
        """
        Determines if an alert should be sent based on cooldown rules and score thresholds.
        """
        if deal_score < settings.DEAL_SCORE_ALERT_THRESHOLD:
            return False

        cooldown_cutoff = datetime.utcnow() - timedelta(hours=settings.COOLDOWN_HOURS_PER_DEAL)
        with Session(engine) as session:
            stmt = select(Deal).where(
                Deal.origin == origin,
                Deal.destination == destination,
                Deal.depart_date == depart_date,
                Deal.return_date == return_date,
                Deal.notified == True,
                Deal.notified_at >= cooldown_cutoff
            ).order_by(Deal.price_twd.asc())
            past_deals = session.exec(stmt).all()

            if not past_deals:
                return True

            lowest_notified_price = min(d.price_twd for d in past_deals)
            # Only alert again if the price dropped by at least 5% further
            if current_price < lowest_notified_price * 0.95:
                return True

            return False
