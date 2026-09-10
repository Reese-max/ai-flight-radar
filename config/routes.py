from typing import Dict, List
from pydantic import BaseModel

class Airport(BaseModel):
    code: str
    name: str
    city: str
    country: str
    is_downtown: bool = False  # e.g. HND, TSA, FUK close to city center

# Monitored Origin Airports
TAIWAN_AIRPORTS: Dict[str, Airport] = {
    "TPE": Airport(code="TPE", name="桃園國際機場", city="台北", country="台灣"),
    "TSA": Airport(code="TSA", name="台北松山機場", city="台北", country="台灣", is_downtown=True),
    "KHH": Airport(code="KHH", name="高雄小港機場", city="高雄", country="台灣"),
    "RMQ": Airport(code="RMQ", name="台中國際機場", city="台中", country="台灣"),
}

# Japan Target Airports
JAPAN_AIRPORTS: Dict[str, Airport] = {
    # Tokyo
    "NRT": Airport(code="NRT", name="成田國際機場", city="東京", country="日本"),
    "HND": Airport(code="HND", name="羽田機場", city="東京", country="日本", is_downtown=True),
    # Kansai
    "KIX": Airport(code="KIX", name="關西國際機場", city="大阪", country="日本"),
    # Kyushu
    "FUK": Airport(code="FUK", name="福岡機場", city="福岡", country="日本", is_downtown=True),
    "KMJ": Airport(code="KMJ", name="阿蘇熊本機場", city="熊本", country="日本"),
    "KOJ": Airport(code="KOJ", name="鹿兒島機場", city="鹿兒島", country="日本"),
    # Okinawa
    "OKA": Airport(code="OKA", name="那霸機場", city="沖繩", country="日本"),
    # Chubu
    "NGO": Airport(code="NGO", name="中部國際機場", city="名古屋", country="日本"),
    # Hokkaido
    "CTS": Airport(code="CTS", name="新千歲機場", city="札幌", country="日本"),
    # Tohoku / Chugoku / Shikoku
    "SDJ": Airport(code="SDJ", name="仙台機場", city="仙台", country="日本"),
    "OKJ": Airport(code="OKJ", name="岡山機場", city="岡山", country="日本"),
    "TAK": Airport(code="TAK", name="高松機場", city="高松", country="日本"),
}

# Default Monitored Route Pairs (Origin -> Destination)
DEFAULT_MONITORED_ROUTES = [
    # Top Tier: High demand
    {"origin": "TPE", "destination": "NRT", "priority": 10},
    {"origin": "TPE", "destination": "KIX", "priority": 10},
    {"origin": "TPE", "destination": "FUK", "priority": 9},
    {"origin": "TPE", "destination": "OKA", "priority": 9},
    {"origin": "TPE", "destination": "CTS", "priority": 8},
    {"origin": "TPE", "destination": "NGO", "priority": 8},
    {"origin": "TSA", "destination": "HND", "priority": 9},
    # Kaohsiung departures
    {"origin": "KHH", "destination": "NRT", "priority": 8},
    {"origin": "KHH", "destination": "KIX", "priority": 8},
    {"origin": "KHH", "destination": "FUK", "priority": 7},
    {"origin": "KHH", "destination": "OKA", "priority": 7},
    # Secondary destinations with great potential deals
    {"origin": "TPE", "destination": "KMJ", "priority": 7},
    {"origin": "TPE", "destination": "KOJ", "priority": 6},
    {"origin": "TPE", "destination": "SDJ", "priority": 6},
    {"origin": "TPE", "destination": "OKJ", "priority": 6},
    {"origin": "TPE", "destination": "TAK", "priority": 6},
]
