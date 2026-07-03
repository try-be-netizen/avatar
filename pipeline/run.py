"""Оркестратор: берёт первую необработанную тему из queue.yaml и прогоняет весь пайплайн.

Запуск локально:
    export HEYGEN_API_KEY=... ANTHROPIC_API_KEY=... (и остальные)
    python -m pipeline.run

В GitHub Actions запускается по cron (см. .github/workflows/generate.yml).
После успеха помечает тему как done и коммитит queue.yaml обратно в репо.
"""
import os
import re
import sys
import datetime

import yaml

from . import config, scriptgen, heygen, deliver

if config.TTS_MODE == "elevenlabs":
    from . import tts_elevenlabs


def load_queue() -> list[dict]:
    with open(config.QUEUE_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def save_queue(items: list[dict]) -> None:
    with open(config.QUEUE_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(items, f, allow_unicode=True, sort_keys=False)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", "-", text.lower()).strip("-")[:40]


def main() -> int:
    items = load_queue()
    task = next((i for i in items if i.get("status", "pending") == "pending"), None)
    if task is None:
        print("Очередь пуста — нечего генерировать.")
        return 0

    topic = task["topic"]
    print(f"=== Тема: {topic} ===")

    # 1. Скрипт
    script = scriptgen.generate_script(topic, task.get("notes", ""))

    # 2-3. Озвучка + рендер
    if config.TTS_MODE == "elevenlabs":
        audio_path = tts_elevenlabs.synthesize(script)
        audio_url = heygen.upload_audio(audio_path)
        video_id = heygen.generate_from_audio(audio_url)
    else:
        video_id = heygen.generate_from_text(script)

    video_url = heygen.wait_for_video(video_id)

    # 4. Скачать и доставить
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    out_path = os.path.join(config.OUTPUT_DIR, f"{stamp}-{slugify(topic)}.mp4")
    heygen.download(video_url, out_path)
    deliver.send_video(out_path, caption=f"🎬 {topic}\n\n{script[:300]}")

    # 5. Пометить как выполненное
    task["status"] = "done"
    task["done_at"] = stamp
    task["video_id"] = video_id
    save_queue(items)
    print("=== Готово ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
