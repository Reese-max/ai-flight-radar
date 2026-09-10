import logging
import httpx
from typing import Optional
from config.settings import settings

logger = logging.getLogger(__name__)

class TelegramClient:
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.enabled = settings.TELEGRAM_ENABLED

    def send_message(self, text: str) -> bool:
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            resp = httpx.post(url, json=payload, timeout=10.0)
            if resp.status_code == 200:
                logger.info("Telegram alert sent successfully.")
                return True
            else:
                logger.warning(f"Telegram alert failed: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

telegram_client = TelegramClient()
