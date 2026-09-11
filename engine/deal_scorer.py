"""Explainable ranking; unknown history, times and baggage never earn evidence points."""
from typing import Dict, List, Tuple
from config.routes import JAPAN_AIRPORTS, TAIWAN_AIRPORTS
from providers.base import StandardFlightOffer


def _hour(value):
    try:
        hour, minute = map(int, value.split(":"))
        return hour if 0 <= hour <= 23 and 0 <= minute <= 59 else None
    except (ValueError, AttributeError, TypeError):
        return None


class DealScorer:
    @staticmethod
    def evaluate(offer: StandardFlightOffer, ref_stats: Dict) -> Tuple[int, str, List[str], float]:
        price = offer.price_twd
        if price <= 0:
            raise ValueError("Price must be positive")
        reasons: List[str] = []
        score = next(points for limit, points in
                     [(5500, 25), (7500, 21), (9500, 17), (12000, 12),
                      (15000, 7), (float("inf"), 2)] if price <= limit)
        reasons.append(f"本次搜尋最低報價 NT${price:,}；以供應商最終確認為準")
        enough = bool(ref_stats.get("sufficient_history"))
        avg30 = ref_stats.get("avg_30d") or 0
        avg90 = ref_stats.get("avg_90d") or 0
        minimum = ref_stats.get("min_historical")
        drop = round((avg30 - price) / avg30 * 100, 1) if enough and avg30 > 0 else 0.0
        observed = ref_stats.get("observed_days", 0)
        if not enough:
            reasons.append(f"歷史資料不足（近30日內僅{observed}個觀測日），不判定歷史折扣")
        else:
            if drop >= 35:
                score += 40
            elif drop >= 25:
                score += 32
            elif drop >= 15:
                score += 22
            elif drop > 0:
                score += 10
            reasons.append(f"相同日期查詢，低於近30日內{observed}個觀測日基準 {drop}%")
            # Overlapping 30/90-day windows do not earn duplicate discount points.
            if minimum is not None and price < minimum:
                score += 10
                reasons.append("低於本系統此前觀測到的最低價；非全市場歷史最低")
            elif minimum is not None and price <= minimum * 1.05:
                score += 6
                reasons.append("接近本系統觀測低點")
        if offer.is_direct:
            score += 10
            reasons.append("搜尋條件為直飛；往返細節仍須於訂票頁確認")
        elif offer.stops == 1:
            score += 3
        dep, arr = _hour(offer.depart_time_str), _hour(offer.arrival_time_str)
        if dep is not None and arr is not None and 6 <= dep < 23 and 6 <= arr < 23:
            score += 5
            reasons.append("已取得的航段起降時間非深夜")
        elif dep is None or arr is None:
            reasons.append("部分起降時間未知，不加時段分")
        else:
            reasons.append("注意深夜或清晨起降時間")
        airports = [JAPAN_AIRPORTS.get(offer.destination), TAIWAN_AIRPORTS.get(offer.origin)]
        score += 5 if any(a and a.is_downtown for a in airports) else 3
        # Airline brand does not establish a particular fare's baggage allowance.
        reasons.append("行李、票種及附加費未驗證；不依航空公司名稱推定含托運")
        score = min(100, max(0, score))
        level = "NORMAL"
        if enough:
            if drop >= 40 or (score >= 90 and price <= 8000):
                level = "EXCEPTIONAL_DEAL"
            elif (ref_stats.get("has_90d_coverage") and ref_stats.get("min_90d") is not None
                  and price < ref_stats["min_90d"] and drop >= 25):
                level = "90D_LOW"
            elif drop >= 20 or score >= 75:
                level = "GREAT_DEAL"
        return score, level, reasons, drop
