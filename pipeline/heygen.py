"""Шаг 3: рендер видео с твоим аватаром через HeyGen API v2.

Два режима:
- generate_from_text(): HeyGen сам озвучивает текст твоим voice_id
- generate_from_audio(): подаём готовый mp3 (например, из ElevenLabs),
  HeyGen анимирует твоего аватара под это аудио
"""
import time
import requests
from . import config

API = "https://api.heygen.com"
UPLOAD = "https://upload.heygen.com"
HEADERS = {"X-Api-Key": config.HEYGEN_API_KEY}


def upload_audio(path: str) -> str:
    """Загружает mp3 в HeyGen как asset, возвращает audio_url/asset id."""
    with open(path, "rb") as f:
        resp = requests.post(
            f"{UPLOAD}/v1/asset",
            headers={**HEADERS, "Content-Type": "audio/mpeg"},
            data=f.read(),
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()["data"]
    print(f"[heygen] asset загружен: {data['id']}")
    return data["url"]


def _generate(voice_block: dict) -> str:
    """Общий вызов генерации. Возвращает video_id."""
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": config.HEYGEN_AVATAR_ID,
                    "avatar_style": "normal",
                },
                "voice": voice_block,
            }
        ],
        "dimension": {"width": config.VIDEO_WIDTH, "height": config.VIDEO_HEIGHT},
    }
    resp = requests.post(
        f"{API}/v2/video/generate",
        headers={**HEADERS, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    video_id = resp.json()["data"]["video_id"]
    print(f"[heygen] генерация запущена, video_id={video_id}")
    return video_id


def generate_from_text(script: str) -> str:
    return _generate({
        "type": "text",
        "input_text": script,
        "voice_id": config.HEYGEN_VOICE_ID,
    })


def generate_from_audio(audio_url: str) -> str:
    return _generate({
        "type": "audio",
        "audio_url": audio_url,
    })


def wait_for_video(video_id: str, poll_every: int = 20, timeout_min: int = 30) -> str:
    """Ждём завершения рендера. Возвращает URL готового mp4."""
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        resp = requests.get(
            f"{API}/v1/video_status.get",
            headers=HEADERS,
            params={"video_id": video_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        print(f"[heygen] статус: {status}")
        if status == "completed":
            return data["video_url"]
        if status == "failed":
            raise RuntimeError(f"HeyGen render failed: {data.get('error')}")
        time.sleep(poll_every)
    raise TimeoutError("Рендер не завершился за отведённое время")


def download(video_url: str, out_path: str) -> str:
    resp = requests.get(video_url, timeout=300)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"[heygen] видео скачано: {out_path} ({len(resp.content) // 1024 // 1024} MB)")
    return out_path
