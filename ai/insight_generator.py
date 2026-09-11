"""Deterministic summary of fresh observations, not a live-agent status claim."""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlmodel import Session, select
from core.database import engine
from core.models import Deal
from config.settings import settings


class DealInsightGenerator:
    @staticmethod
    def generate_daily_briefing() -> str:
        cutoff = datetime.utcnow() - timedelta(hours=settings.DEAL_MAX_AGE_HOURS)
        today = datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
        with Session(engine) as session:
            deals = session.exec(select(Deal).where(
                Deal.status == "active", Deal.deal_score >= 75,
                Deal.created_at >= cutoff, Deal.depart_date >= today,
            ).order_by(Deal.deal_score.desc()).limit(5)).all()
        if not deals:
            return "目前沒有足夠歷史證據且仍在有效期內的高評分報價。請確認排程是否正在執行；新安裝需先累積觀測資料。"
        lines = ["AI Flight Radar 近期報價摘要（規則式整理，非訂票保證）"]
        for index, deal in enumerate(deals, 1):
            try:
                reasons = json.loads(deal.reasons)
                reasons = reasons if isinstance(reasons, list) else []
            except (TypeError, ValueError):
                reasons = []
            lines.append(
                f"{index}. {deal.origin} → {deal.destination}：NT${deal.price_twd:,}\n"
                f"日期：{deal.depart_date} 至 {deal.return_date}；航空：{deal.airline}\n"
                f"評分：{deal.deal_score}/100；觀測時間（UTC）：{deal.created_at.isoformat()}\n"
                + "；".join(str(reason) for reason in reasons[:3])
            )
        lines.append("購買前仍須確認最新價格、去回航段、行李及附加費。")
        return "\n\n".join(lines)
