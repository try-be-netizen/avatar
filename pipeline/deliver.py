"""Шаг 4: доставка готового видео в Telegram (тебе в личку или в канал)."""
import requests
from . import config


def send_video(path: str, caption: str = "") -> None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendVideo"
    with open(path, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": caption[:1024]},
            files={"video": f},
            timeout=300,
        )
    resp.raise_for_status()
    print("[telegram] видео отправлено")
