"""Конфигурация пайплайна. Все секреты — через переменные окружения (GitHub Secrets)."""
import os

# --- API ключи (задаются в GitHub Secrets) ---
HEYGEN_API_KEY = os.environ["HEYGEN_API_KEY"]
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")  # опционально
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# --- Твои ID из HeyGen (после создания Digital Twin) ---
# Найти: HeyGen → Avatars → твой аватар → avatar_id в URL или через GET /v2/avatars
HEYGEN_AVATAR_ID = os.environ["HEYGEN_AVATAR_ID"]
# Голос: либо voice_id из HeyGen (вкладка Voices), либо не нужен, если озвучиваем через ElevenLabs
HEYGEN_VOICE_ID = os.environ.get("HEYGEN_VOICE_ID", "")
# Голос-клон в ElevenLabs (если используем режим elevenlabs)
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")

# --- Режим озвучки: "heygen_text" (проще) или "elevenlabs" (дешевле, больше контроля) ---
TTS_MODE = os.environ.get("TTS_MODE", "heygen_text")

# --- Параметры видео ---
VIDEO_WIDTH = int(os.environ.get("VIDEO_WIDTH", "720"))    # 720x1280 = вертикалка для Reels/Shorts
VIDEO_HEIGHT = int(os.environ.get("VIDEO_HEIGHT", "1280"))

# --- Пути ---
QUEUE_FILE = "queue.yaml"
OUTPUT_DIR = "output"

# --- Промпт для генерации скрипта ---
SCRIPT_SYSTEM_PROMPT = """Ты пишешь сценарии коротких видео (30-60 секунд) для говорящей головы.
Правила:
- Только произносимый текст, никаких ремарок, заголовков, эмодзи и markdown
- Разговорный живой язык, короткие фразы, как будто человек говорит на камеру
- Начни с хука в первой фразе, закончи явным выводом или призывом
- Объём: 80-140 слов
- Язык: тот же, что у темы"""
