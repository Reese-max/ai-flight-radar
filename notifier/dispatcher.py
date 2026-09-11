"""Only successful deliveries advance the cooldown state."""
import html
import json
import logging
from datetime import datetime
from urllib.parse import urlencode
from sqlmodel import Session
from core.database import engine
from core.models import Deal
from notifier.ntfy_client import ntfy_client
from notifier.telegram_client import telegram_client
from notifier.throttler import AlertThrottler

logger = logging.getLogger(__name__)


class AlertDispatcher:
    @staticmethod
    def get_google_flights_url(origin: str, destination: str, depart_date: str, return_date: str) -> str:
        query = f"flights from {origin} to {destination} on {depart_date} through {return_date}"
        return "https://www.google.com/travel/flights?" + urlencode({"q": query, "curr": "TWD"})

    @classmethod
    def dispatch_deal(cls, deal: Deal) -> bool:
        if not AlertThrottler.should_alert(
            origin=deal.origin, destination=deal.destination,
            depart_date=deal.depart_date, return_date=deal.return_date,
            current_price=deal.price_twd, deal_score=deal.deal_score,
        ):
            return False
        url = cls.get_google_flights_url(deal.origin, deal.destination, deal.depart_date, deal.return_date)
        try:
            reasons = json.loads(deal.reasons)
            if not isinstance(reasons, list):
                reasons = []
        except (TypeError, ValueError):
            reasons = []
        title = f"機票報價提醒 {deal.origin} → {deal.destination} NT${deal.price_twd:,}"
        message = (
            f"{deal.depart_date} 至 {deal.return_date}\n航空：{deal.airline}\n"
            f"報價：NT${deal.price_twd:,}；評分 {deal.deal_score}/100\n"
            + "\n".join(str(reason) for reason in reasons)
            + "\n此為搜尋時報價，非保證庫存；購買前確認往返航段、行李與總價。"
        )
        results = []
        for name, send in (
            ("ntfy", lambda: ntfy_client.send_alert(title=title, message=message, priority=4, click_url=url)),
            ("telegram", lambda: telegram_client.send_message(
                f"<b>{html.escape(title)}</b>\n{html.escape(message)}\n"
                f'<a href="{html.escape(url, quote=True)}">查看 Google Flights</a>')),
        ):
            try:
                results.append(bool(send()))
            except Exception:
                logger.exception("Notification channel %s failed", name)
                results.append(False)
        if not any(results):
            logger.warning("No channel delivered deal %s; leaving it eligible for retry", deal.id)
            return False
        with Session(engine) as session:
            stored = session.get(Deal, deal.id)
            if stored is not None:
                stored.notified = True
                stored.notified_at = datetime.utcnow()
                session.add(stored)
                session.commit()
        return True
