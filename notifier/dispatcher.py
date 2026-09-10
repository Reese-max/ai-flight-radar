import json
import logging
from datetime import datetime
from sqlmodel import Session
from core.database import engine
from core.models import Deal
from notifier.ntfy_client import ntfy_client
from notifier.telegram_client import telegram_client
from notifier.throttler import AlertThrottler
from config.routes import TAIWAN_AIRPORTS, JAPAN_AIRPORTS

logger = logging.getLogger(__name__)

class AlertDispatcher:
    @staticmethod
    def get_google_flights_url(origin: str, destination: str, depart_date: str, return_date: str) -> str:
        return f"https://www.google.com/travel/flights?q=flights%20from%20{origin}%20to%20{destination}%20on%20{depart_date}%20through%20{return_date}"

    @classmethod
    def dispatch_deal(cls, deal: Deal) -> bool:
        should_send = AlertThrottler.should_alert(
            origin=deal.origin,
            destination=deal.destination,
            depart_date=deal.depart_date,
            return_date=deal.return_date,
            current_price=deal.price_twd,
            deal_score=deal.deal_score
        )

        if not should_send:
            logger.info(f"Alert throttled or below threshold for {deal.origin}->{deal.destination} (Score: {deal.deal_score})")
            return False

        orig_name = TAIWAN_AIRPORTS.get(deal.origin, None)
        orig_label = f"{orig_name.city}({deal.origin})" if orig_name else deal.origin
        dest_name = JAPAN_AIRPORTS.get(deal.destination, None)
        dest_label = f"{dest_name.city}({deal.destination})" if dest_name else deal.destination

        gf_url = cls.get_google_flights_url(deal.origin, deal.destination, deal.depart_date, deal.return_date)
        
        try:
            reasons_list = json.loads(deal.reasons)
        except Exception:
            reasons_list = []
        reasons_text = "\n".join([f"  • {r}" for r in reasons_list])

        level_badge = "🔥【神價機票情報】" if deal.deal_level == "EXCEPTIONAL_DEAL" else "🎯【超值機票發現】"

        # 1. Dispatch via ntfy
        ntfy_title = f"{level_badge} {orig_label} ✈️ {dest_label} NT${deal.price_twd:,} (Score: {deal.deal_score})"
        ntfy_msg = (
            f"航線：{orig_label} 往返 {dest_label}\n"
            f"日期：{deal.depart_date} ~ {deal.return_date} ({deal.duration_days} 天)\n"
            f"航空：{deal.airline} (直飛)\n"
            f"票價：NT${deal.price_twd:,} (比基準降幅 {deal.drop_pct}%)\n"
            f"評分：{deal.deal_score} / 100\n\n"
            f"推薦原因：\n{reasons_text}\n\n"
            f"點擊立即前往 Google Flights 查看！"
        )
        ntfy_priority = 5 if deal.deal_level == "EXCEPTIONAL_DEAL" else 4
        sent_ntfy = ntfy_client.send_alert(
            title=ntfy_title,
            message=ntfy_msg,
            priority=ntfy_priority,
            click_url=gf_url
        )

        # 2. Dispatch via Telegram
        tg_html = (
            f"<b>{level_badge}</b>\n"
            f"✈️ <b>{orig_label} ➔ {dest_label}</b>\n"
            f"💰 <b>價格：NT${deal.price_twd:,}</b> (降幅 <b>{deal.drop_pct}%</b>)\n"
            f"🎯 <b>Deal Score：{deal.deal_score} / 100</b>\n"
            f"📅 日期：<code>{deal.depart_date}</code> 至 <code>{deal.return_date}</code> ({deal.duration_days} 天)\n"
            f"🏢 航空公司：{deal.airline}\n"
            f"\n<b>推薦理由：</b>\n{reasons_text}\n\n"
            f"👉 <a href='{gf_url}'>點此開啟 Google Flights 預訂/比價</a>"
        )
        sent_tg = telegram_client.send_message(tg_html)

        # Update deal notified status in DB
        with Session(engine) as session:
            db_deal = session.get(Deal, deal.id)
            if db_deal:
                db_deal.notified = True
                db_deal.notified_at = datetime.utcnow()
                session.add(db_deal)
                session.commit()

        logger.info(f"Alert successfully dispatched for Deal #{deal.id}: {deal.origin}->{deal.destination}")
        return True
