"""Шаг 1: генерация сценария видео из темы через Claude API."""
import requests
from . import config


def generate_script(topic: str, extra_instructions: str = "") -> str:
    """Тема из очереди -> готовый текст для озвучки."""
    user_prompt = f"Тема видео: {topic}"
    if extra_instructions:
        user_prompt += f"\nДополнительно: {extra_instructions}"

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 1024,
            "system": config.SCRIPT_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    script = "".join(b["text"] for b in data["content"] if b["type"] == "text").strip()
    print(f"[script] {len(script.split())} слов:\n{script}\n")
    return script
