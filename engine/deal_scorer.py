import json
from typing import Dict, Tuple, List
from providers.base import StandardFlightOffer
from engine.analyzer import PriceAnalyzer
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS

class DealScorer:
    @staticmethod
    def evaluate(offer: StandardFlightOffer, ref_stats: Dict[str, float]) -> Tuple[int, str, List[str], float]:
        """
        Evaluates an offer against historical statistics and route characteristics.
        Returns:
            - deal_score (0~100)
            - deal_level ("EXCEPTIONAL_DEAL" | "90D_LOW" | "GREAT_DEAL" | "NORMAL")
            - reasons (List[str] of explainable highlights)
            - drop_pct (Percentage drop compared to 30d baseline)
        """
        price = offer.price_twd
        avg_30d = ref_stats["avg_30d"]
        avg_90d = ref_stats["avg_90d"]
        min_hist = ref_stats["min_historical"]
        
        # Calculate drop percentage relative to 30-day average
        drop_pct = round(((avg_30d - price) / avg_30d) * 100.0, 1) if avg_30d > 0 else 0.0
        reasons: List[str] = []
        score = 0

        # 1. 價格絕對值競爭力 (0 ~ 25 分)
        if price <= 5500:
            score += 25
            reasons.append(f"極致低價 (NT${price:,})")
        elif price <= 7500:
            score += 21
            reasons.append(f"超值甜甜價 (NT${price:,})")
        elif price <= 9500:
            score += 17
        elif price <= 12000:
            score += 12
        elif price <= 15000:
            score += 7
        else:
            score += 2

        # 2. 相較 30 日平均降幅 (0 ~ 25 分)
        if drop_pct >= 35.0:
            score += 25
            reasons.append(f"比近 30 日均價大降 {drop_pct}%")
        elif drop_pct >= 25.0:
            score += 20
            reasons.append(f"比近 30 日均價降幅 {drop_pct}%")
        elif drop_pct >= 15.0:
            score += 14
            reasons.append(f"比近 30 日均價降 {drop_pct}%")
        elif drop_pct > 0:
            score += 7
        else:
            score += 0

        # 3. 相較 90 日平均降幅 (0 ~ 15 分)
        drop_90d = round(((avg_90d - price) / avg_90d) * 100.0, 1) if avg_90d > 0 else 0.0
        if drop_90d >= 30.0:
            score += 15
        elif drop_90d >= 15.0:
            score += 10
        elif drop_90d > 0:
            score += 5

        # 4. 是否為歷史新低或逼近新低 (0 ~ 10 分)
        if price <= min_hist and not ref_stats.get("is_cold_start", False):
            score += 10
            reasons.append("創歷史最低價記錄")
        elif price <= min_hist * 1.05:
            score += 6
            reasons.append("逼近歷史低點")

        # 5. 直飛 vs 轉機 (0 ~ 10 分)
        if offer.is_direct:
            score += 10
            reasons.append("直飛不轉機")
        elif offer.stops == 1:
            score += 3
        else:
            score += 0

        # 6. 航班時間友善度 (0 ~ 5 分)
        # 扣分：紅眼航班 (出發 00:00~06:30 或 抵達 > 23:00)
        is_red_eye = False
        if offer.depart_time_str:
            try:
                hour = int(offer.depart_time_str.split(":")[0])
                if 0 <= hour < 6:
                    is_red_eye = True
            except Exception:
                pass
        
        if is_red_eye:
            score += 0
            reasons.append("注意：此航班為清晨/紅眼班機")
        else:
            score += 5
            reasons.append("日間優質時段航班")

        # 7. 機場便利性 (0 ~ 5 分)
        # 例如羽田 (HND)、松山 (TSA)、福岡 (FUK 距市區僅 15 分鐘)
        dest_airport = JAPAN_AIRPORTS.get(offer.destination)
        orig_airport = TAIWAN_AIRPORTS.get(offer.origin)
        if (dest_airport and dest_airport.is_downtown) or (orig_airport and orig_airport.is_downtown):
            score += 5
            reasons.append(f"市區型便利機場 ({offer.origin}/{offer.destination})")
        else:
            score += 3

        # 8. 航空公司加分 (0 ~ 5 分)
        fsc_airlines = ["中華航空", "長榮航空", "星宇航空", "日本航空", "全日空航空"]
        if any(fsc in offer.primary_airline for fsc in fsc_airlines):
            score += 5
            reasons.append(f"傳統全服務航空含托運 ({offer.primary_airline})")
        else:
            score += 2

        score = min(100, max(0, score))

        # Determine Deal Level
        if drop_pct >= 40.0 or (score >= 90 and price <= 8000):
            deal_level = "EXCEPTIONAL_DEAL"
        elif price <= min_hist and drop_pct >= 25.0:
            deal_level = "90D_LOW"
        elif drop_pct >= 20.0 or score >= 75:
            deal_level = "GREAT_DEAL"
        else:
            deal_level = "NORMAL"

        return score, deal_level, reasons, drop_pct
