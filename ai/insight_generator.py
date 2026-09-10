import json
from typing import List, Dict
from sqlmodel import Session, select
from core.database import engine
from core.models import Deal
from config.routes import TAIWAN_AIRPORTS, JAPAN_AIRPORTS

class DealInsightGenerator:
    @staticmethod
    def generate_daily_briefing() -> str:
        """
        Generates the "Today's Top Flight Deals Intelligence" summary.
        Answers: 今天有什麼最值得買？
        """
        with Session(engine) as session:
            stmt = select(Deal).where(Deal.status == "active").order_by(Deal.deal_score.desc()).limit(5)
            top_deals = session.exec(stmt).all()

            if not top_deals:
                return "📡 今日雷達掃描中：目前暫無達到高評分 (Score >= 75) 的異常低價航班，雷達正持續全天候監控中。"

            briefing_lines = ["✈️ 【AI Flight Radar 今日超值神價情報】\n"]
            for i, deal in enumerate(top_deals, 1):
                orig = TAIWAN_AIRPORTS.get(deal.origin)
                orig_str = orig.city if orig else deal.origin
                dest = JAPAN_AIRPORTS.get(deal.destination)
                dest_str = dest.city if dest else deal.destination
                
                try:
                    reasons = json.loads(deal.reasons)
                    reasons_str = "、".join(reasons[:3])
                except Exception:
                    reasons_str = "大降幅特惠"

                icon = "🔥" if deal.deal_score >= 85 else "✨"
                briefing_lines.append(
                    f"{icon} {i}. {orig_str} ➔ {dest_str} ({dest.name if dest else deal.destination})\n"
                    f"   💰 票價：NT${deal.price_twd:,} (比基準均價 ↓{deal.drop_pct}%)\n"
                    f"   🎯 Deal Score：{deal.deal_score} / 100\n"
                    f"   📅 日期：{deal.depart_date} ~ {deal.return_date} ({deal.duration_days} 天)\n"
                    f"   ✈️ 航空：{deal.airline} (直飛)\n"
                    f"   💡 特點：{reasons_str}\n"
                )

            return "\n".join(briefing_lines)
