import logging
import httpx
from typing import Optional
from config.settings import settings

logger = logging.getLogger(__name__)

class NtfyClient:
    def __init__(self):
        self.server = settings.NTFY_SERVER.rstrip("/")
        self.topic = settings.NTFY_TOPIC
        self.enabled = settings.NTFY_ENABLED

    def send_alert(
        self,
        title: str,
        message: str,
        priority: int = 3, # 1: min, 3: default, 4: high, 5: urgent
        tags: Optional[str] = "airplane,rotating_light",
        click_url: Optional[str] = None
    ) -> bool:
        if not self.enabled:
            return False

        url = f"{self.server}/{self.topic}"
        headers = {
            "Title": title.encode("utf-8"),
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = tags
        if click_url:
            headers["Click"] = click_url

        try:
            resp = httpx.post(url, data=message.encode("utf-8"), headers=headers, timeout=10.0)
            if resp.status_code == 200:
                logger.info(f"Ntfy alert sent successfully to {self.topic}")
                return True
            else:
                logger.warning(f"Ntfy alert failed with status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending ntfy notification: {e}")
            return False

ntfy_client = NtfyClient()
