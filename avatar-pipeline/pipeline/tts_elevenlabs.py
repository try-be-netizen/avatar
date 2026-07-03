"""Шаг 2 (опционально): озвучка текста твоим голосом-клоном через ElevenLabs."""
import requests
from . import config


def synthesize(text: str, out_path: str = "voiceover.mp3") -> str:
    """Текст -> mp3 твоим голосом. Возвращает путь к файлу."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    resp = requests.post(
        url,
        headers={
            "xi-api-key": config.ELEVENLABS_API_KEY,
            "content-type": "application/json",
        },
        json={
            "text": text,
            # multilingual-модель отлично держит русский
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,          # ниже = живее интонации, выше = ровнее
                "similarity_boost": 0.8,   # насколько похоже на оригинал
                "style": 0.3,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"[tts] аудио сохранено: {out_path} ({len(resp.content) // 1024} KB)")
    return out_path
