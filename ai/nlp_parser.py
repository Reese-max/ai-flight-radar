import re
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from config.routes import TAIWAN_AIRPORTS, JAPAN_AIRPORTS

class ParsedSearchIntent(BaseModel):
    origins: List[str] = ["TPE", "KHH"]
    destinations: List[str] = []
    min_duration: int = 4
    max_duration: int = 5
    max_budget_twd: Optional[int] = None
    direct_only: bool = True
    start_date: str
    end_date: str
    summary_text: str

class NLPIntentParser:
    CITY_TO_AIRPORTS = {
        "台北": ["TPE", "TSA"],
        "桃園": ["TPE"],
        "松山": ["TSA"],
        "高雄": ["KHH"],
        "台中": ["RMQ"],
        "台灣": ["TPE", "TSA", "KHH"],
        # Japan
        "東京": ["NRT", "HND"],
        "成田": ["NRT"],
        "羽田": ["HND"],
        "大阪": ["KIX"],
        "關西": ["KIX"],
        "京都": ["KIX"],
        "福岡": ["FUK"],
        "九州": ["FUK", "KMJ", "KOJ"],
        "沖繩": ["OKA"],
        "那霸": ["OKA"],
        "札幌": ["CTS"],
        "北海道": ["CTS"],
        "名古屋": ["NGO"],
        "仙台": ["SDJ"],
        "熊本": ["KMJ"],
        "鹿兒島": ["KOJ"],
        "岡山": ["OKJ"],
        "高松": ["TAK"],
        "日本": ["NRT", "HND", "KIX", "FUK", "OKA", "CTS", "NGO", "KMJ", "KOJ", "SDJ", "OKJ", "TAK"]
    }

    @classmethod
    def parse(cls, query: str) -> ParsedSearchIntent:
        today = datetime.utcnow().date()
        start_date = today + timedelta(days=7)
        end_date = today + timedelta(days=90) # Default future 90 days

        # 1. Date Range
        if "半年" in query or "6個月" in query:
            end_date = today + timedelta(days=180)
        elif "三個月" in query or "3個月" in query:
            end_date = today + timedelta(days=90)
        elif "一個月" in query or "下個月" in query:
            start_date = today + timedelta(days=15)
            end_date = today + timedelta(days=45)

        # 2. Origins
        matched_origins = set()
        for city, codes in cls.CITY_TO_AIRPORTS.items():
            if city in ["台北", "桃園", "松山", "高雄", "台中"]:
                if city in query:
                    matched_origins.update(codes)
        if not matched_origins:
            matched_origins = {"TPE", "KHH"}

        # 3. Destinations
        matched_destinations = set()
        for city, codes in cls.CITY_TO_AIRPORTS.items():
            if city not in ["台北", "桃園", "松山", "高雄", "台中", "台灣"]:
                if city in query:
                    matched_destinations.update(codes)
        
        # If no specific city matched but "日本" mentioned or empty
        if not matched_destinations or "日本" in query:
            matched_destinations = {"NRT", "KIX", "FUK", "OKA", "CTS", "NGO", "KMJ"}

        # 4. Durations (e.g. 4~5天, 4～5天, 4-5天, 5天)
        min_dur, max_dur = 4, 5
        dur_match = re.search(r'(\d+)\s*[~～至到\-－—]\s*(\d+)\s*天', query)
        if dur_match:
            min_dur = int(dur_match.group(1))
            max_dur = int(dur_match.group(2))
        else:
            single_dur = re.search(r'(\d+)\s*天', query)
            if single_dur:
                d = int(single_dur.group(1))
                min_dur, max_dur = d, d

        # 5. Budget (e.g. 8000以下, 8,000元, 一萬以下)
        budget = None
        if "一萬" in query or "1萬" in query or "10000" in query:
            budget = 10000
        budget_match = re.search(r'(\d{4,6})\s*(元|塊|以內|以下)?', query.replace(",", ""))
        if budget_match:
            val = int(budget_match.group(1))
            if val >= 3000:
                budget = val

        # 6. Direct flights
        direct_only = True
        if "轉機" in query and "不要" not in query:
            direct_only = False

        summary = (
            f"搜尋出發：{', '.join(sorted(matched_origins))} ➔ 目的地：{', '.join(sorted(matched_destinations))}\n"
            f"日期範圍：{start_date} ~ {end_date} | 旅行天數：{min_dur}~{max_dur}天 | "
            f"預算上限：{'NT$' + str(budget) if budget else '不限'} | 直飛限定：{'是' if direct_only else '否'}"
        )

        return ParsedSearchIntent(
            origins=sorted(list(matched_origins)),
            destinations=sorted(list(matched_destinations)),
            min_duration=min_dur,
            max_duration=max_dur,
            max_budget_twd=budget,
            direct_only=direct_only,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            summary_text=summary
        )
