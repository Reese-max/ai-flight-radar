import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseModel):
    # Database
    DB_PATH: str = os.getenv("DB_PATH", str(DATA_DIR / "flights.db"))
    
    # Currency & Language
    CURRENCY: str = "TWD"
    LANGUAGE: str = "zh-TW"
    
    # Provider & Scraping Controls
    MIN_REQUEST_DELAY_SEC: float = 3.0
    MAX_REQUEST_DELAY_SEC: float = 6.0
    MAX_RETRIES: int = 3
    DEFAULT_MAX_STOPS: int = 0  # 0 for direct only
    
    # Tier scan intervals (in seconds)
    TIER_1_INTERVAL_SEC: int = 6 * 3600    # Normal routes: 6 hours
    TIER_2_INTERVAL_SEC: int = 2 * 3600    # Price drop detected: 2 hours
    TIER_3_INTERVAL_SEC: int = 1 * 3600    # Near target price: 1 hour
    TIER_4_INTERVAL_SEC: int = 30 * 60     # Extreme deal / rapid tracking: 30 minutes
    
    # Deal Score & Alert Thresholds
    DEAL_SCORE_ALERT_THRESHOLD: int = 80   # Score >= 80 qualifies for alert
    PRICE_DROP_ALERT_THRESHOLD_PCT: float = 25.0  # 25% drop relative to 30d avg
    COOLDOWN_HOURS_PER_DEAL: int = 12      # Prevent duplicate alert spam
    
    # Push Notifications
    NTFY_ENABLED: bool = True
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC", "flight-radar-taiwan")
    NTFY_SERVER: str = os.getenv("NTFY_SERVER", "https://ntfy.sh")
    
    TELEGRAM_ENABLED: bool = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Web & API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8787

settings = Settings()
