"""Environment configuration. Notifications and public listening are opt-in."""
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
DATA_DIR = BASE_DIR / "data"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value.strip().lower() not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true/false, 1/0, or yes/no")
    return value.strip().lower() in {"true", "1", "yes"}


class Settings(BaseModel):
    DB_PATH: str = os.getenv("DB_PATH", str(DATA_DIR / "flights.db"))
    CURRENCY: str = "TWD"
    LANGUAGE: str = "zh-TW"
    MIN_REQUEST_DELAY_SEC: float = 3.0
    MAX_REQUEST_DELAY_SEC: float = 6.0
    MAX_RETRIES: int = 3
    DEFAULT_MAX_STOPS: int = 0
    TIER_1_INTERVAL_SEC: int = 6 * 3600
    TIER_2_INTERVAL_SEC: int = 2 * 3600
    TIER_3_INTERVAL_SEC: int = 3600
    TIER_4_INTERVAL_SEC: int = 1800
    TASK_LEASE_SECONDS: int = 900
    ERROR_RETRY_SECONDS: int = 600
    DEAL_MAX_AGE_HOURS: int = 6
    DEAL_SCORE_ALERT_THRESHOLD: int = 80
    PRICE_DROP_ALERT_THRESHOLD_PCT: float = 25.0
    COOLDOWN_HOURS_PER_DEAL: int = 12
    NTFY_ENABLED: bool = env_bool("NTFY_ENABLED")
    NTFY_TOPIC: str = os.getenv("NTFY_TOPIC", "")
    NTFY_SERVER: str = os.getenv("NTFY_SERVER", "https://ntfy.sh")
    TELEGRAM_ENABLED: bool = env_bool("TELEGRAM_ENABLED", bool(
        os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")))
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = Field(default=int(os.getenv("API_PORT", "8787")), ge=1, le=65535)
    API_KEY: str = os.getenv("API_KEY", "")

    @model_validator(mode="after")
    def validate_delivery(self):
        if self.NTFY_ENABLED and (not self.NTFY_TOPIC.strip() or self.NTFY_TOPIC == "flight-radar-taiwan"):
            raise ValueError("Set your own private/reserved NTFY_TOPIC before enabling notifications")
        if self.TELEGRAM_ENABLED and not (self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID):
            raise ValueError("Telegram requires both a bot token and chat ID")
        return self


settings = Settings()
