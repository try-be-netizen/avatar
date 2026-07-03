"""Telegram-бот для пополнения очереди тем с телефона.

Текст  -> тема добавляется в queue.yaml (коммит через GitHub Contents API)
Голос  -> расшифровка через ElevenLabs STT -> кнопка-подтверждение -> тема в очередь
/queue -> показать pending-темы
/go    -> немедленно запустить воркфлоу генерации (workflow_dispatch)
/redo [правки] -> вернуть последнее готовое видео в очередь с правками и перегенерировать

Формат текста: "тема | заметки для сценариста" (часть после | опциональна).

Запуск: long-polling, рассчитан на systemd (см. avatar-queue-bot.service).
"""
import base64
import io
import os
import time

import requests
import yaml

# --- Конфиг из окружения ---
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ["ALLOWED_USER_ID"])          # твой telegram user id
GITHUB_TOKEN = os.environ["GH_TOKEN"]                          # fine-grained PAT, contents:write + actions:write
GITHUB_REPO = os.environ["GH_REPO"]                            # напр. "xen/avatar-pipeline"
QUEUE_PATH = os.environ.get("QUEUE_PATH", "queue.yaml")
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "generate.yml")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")  # для голосовых

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"
GH_API = "https://api.github.com"
GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}


# Расшифровки голосовых, ожидающие подтверждения кнопкой: {chat_id: topic}
pending_confirm: dict[int, str] = {}


# ---------- Telegram helpers ----------

def tg(method: str, **kwargs) -> dict:
    resp = requests.post(f"{TG_API}/{method}", json=kwargs, timeout=60)
    resp.raise_for_status()
    return resp.json()["result"]


def reply(chat_id: int, text: str) -> None:
    tg("sendMessage", chat_id=chat_id, text=text)


def reply_with_confirm(chat_id: int, text: str) -> None:
    tg("sendMessage", chat_id=chat_id, text=text, reply_markup={
        "inline_keyboard": [[
            {"text": "✅ В очередь", "callback_data": "confirm"},
            {"text": "❌ Отмена", "callback_data": "cancel"},
        ]]
    })


def download_voice(file_id: str) -> bytes:
    info = tg("getFile", file_id=file_id)
    url = f"https://api.telegram.org/file/bot{TG_TOKEN}/{info['file_path']}"
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


# ---------- ElevenLabs STT ----------

def transcribe(audio: bytes) -> str:
    resp = requests.post(
        "https://api.elevenlabs.io/v1/speech-to-text",
        headers={"xi-api-key": ELEVENLABS_API_KEY},
        data={"model_id": "scribe_v1"},
        files={"file": ("voice.ogg", io.BytesIO(audio), "audio/ogg")},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["text"].strip()


# ---------- GitHub: чтение/запись queue.yaml ----------

def gh_get_queue() -> tuple[list[dict], str]:
    """Возвращает (items, sha) — sha нужен для безопасного PUT."""
    resp = requests.get(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{QUEUE_PATH}",
        headers=GH_HEADERS, timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    raw = base64.b64decode(data["content"]).decode("utf-8")
    return yaml.safe_load(raw) or [], data["sha"]


def gh_put_queue(items: list[dict], sha: str, message: str) -> None:
    raw = yaml.safe_dump(items, allow_unicode=True, sort_keys=False)
    resp = requests.put(
        f"{GH_API}/repos/{GITHUB_REPO}/contents/{QUEUE_PATH}",
        headers=GH_HEADERS,
        json={
            "message": f"{message} [skip ci]",
            "content": base64.b64encode(raw.encode("utf-8")).decode("ascii"),
            "sha": sha,
        },
        timeout=30,
    )
    resp.raise_for_status()


def add_topic(topic: str, notes: str = "") -> int:
    """Добавляет тему с ретраем на случай конфликта sha. Возвращает размер очереди."""
    for attempt in range(3):
        items, sha = gh_get_queue()
        entry = {"topic": topic, "status": "pending"}
        if notes:
            entry["notes"] = notes
        items.append(entry)
        try:
            gh_put_queue(items, sha, f"queue: add '{topic[:50]}'")
            return sum(1 for i in items if i.get("status", "pending") == "pending")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 409 and attempt < 2:
                time.sleep(1)  # кто-то закоммитил параллельно — перечитываем
                continue
            raise
    raise RuntimeError("unreachable")


def trigger_workflow() -> None:
    resp = requests.post(
        f"{GH_API}/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches",
        headers=GH_HEADERS,
        json={"ref": "main"},
        timeout=30,
    )
    resp.raise_for_status()


def redo_last(edits: str) -> str:
    """Возвращает последнюю done-тему в начало очереди с правками. Возвращает topic."""
    for attempt in range(3):
        items, sha = gh_get_queue()
        done = [i for i in items if i.get("status") == "done"]
        if not done:
            raise ValueError("Нет готовых видео для переделки.")
        last = done[-1]  # последняя завершённая
        last["status"] = "pending"
        last.pop("done_at", None)
        last.pop("video_id", None)
        base_notes = last.get("notes", "")
        redo_note = f"ПЕРЕДЕЛКА. Правки к прошлой версии: {edits}" if edits else "ПЕРЕДЕЛКА: сделай заметно другой вариант сценария."
        last["notes"] = f"{base_notes}\n{redo_note}".strip()
        # ставим в начало, чтобы взялась первой
        items.remove(last)
        items.insert(0, last)
        try:
            gh_put_queue(items, sha, f"queue: redo '{last['topic'][:50]}'")
            return last["topic"]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 409 and attempt < 2:
                time.sleep(1)
                continue
            raise
    raise RuntimeError("unreachable")


# ---------- Обработка сообщений ----------

def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    user_id = msg.get("from", {}).get("id")
    if user_id != ALLOWED_USER_ID:
        reply(chat_id, "⛔ Этот бот приватный.")
        return

    text = (msg.get("text") or "").strip()

    if text == "/start":
        reply(chat_id,
              "Привет! Пришли тему текстом или голосом — добавлю в очередь на видео.\n"
              "Формат: «тема | заметки» (заметки опциональны)\n"
              "/queue — показать очередь\n/go — запустить генерацию сейчас\n"
              "/redo <правки> — перегенерировать последнее видео с правками")
        return

    if text == "/queue":
        items, _ = gh_get_queue()
        pending = [i["topic"] for i in items if i.get("status", "pending") == "pending"]
        if pending:
            listing = "\n".join(f"{n}. {t}" for n, t in enumerate(pending, 1))
            reply(chat_id, f"📋 В очереди ({len(pending)}):\n{listing}")
        else:
            reply(chat_id, "📋 Очередь пуста.")
        return

    if text == "/go":
        trigger_workflow()
        reply(chat_id, "🚀 Воркфлоу запущен — видео придёт сюда через ~10-20 минут.")
        return

    if text.startswith("/redo"):
        edits = text[len("/redo"):].strip()
        try:
            topic = redo_last(edits)
        except ValueError as e:
            reply(chat_id, str(e))
            return
        trigger_workflow()
        reply(chat_id,
              f"🔁 Перегенерирую «{topic}»"
              + (f"\nПравки: {edits}" if edits else "")
              + "\n🚀 Воркфлоу запущен, видео придёт сюда.")
        return

    if "voice" in msg:
        if not ELEVENLABS_API_KEY:
            reply(chat_id, "Голосовые не настроены (нет ELEVENLABS_API_KEY).")
            return
        reply(chat_id, "🎙 Расшифровываю...")
        topic = transcribe(download_voice(msg["voice"]["file_id"]))
        pending_confirm[chat_id] = topic
        reply_with_confirm(chat_id, f"Расслышала так:\n«{topic}»\n\nДобавить в очередь?")
        return

    if text and not text.startswith("/"):
        topic, _, notes = (p.strip() for p in text.partition("|"))
        n = add_topic(topic, notes)
        reply(chat_id, f"✅ Добавила: «{topic}»" + (f"\nЗаметки: {notes}" if notes else "") + f"\n\nВ очереди: {n}")
        return

    reply(chat_id, "Не поняла. Пришли тему текстом/голосом, или /queue, /go, /redo.")


def handle_callback(cb: dict) -> None:
    """Нажатия кнопок подтверждения расшифровки."""
    chat_id = cb["message"]["chat"]["id"]
    user_id = cb.get("from", {}).get("id")
    msg_id = cb["message"]["message_id"]
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    if user_id != ALLOWED_USER_ID:
        return

    topic = pending_confirm.pop(chat_id, None)
    if topic is None:
        tg("editMessageText", chat_id=chat_id, message_id=msg_id,
           text="⌛ Это подтверждение уже неактуально.")
        return

    if cb["data"] == "confirm":
        n = add_topic(topic)
        tg("editMessageText", chat_id=chat_id, message_id=msg_id,
           text=f"✅ Добавила: «{topic}»\n\nВ очереди: {n}")
    else:
        tg("editMessageText", chat_id=chat_id, message_id=msg_id,
           text=f"❌ Отменила. Если Scribe ослышался — пришли тему текстом:\n«{topic}»")


def main() -> None:
    print("Bot started (long polling)")
    offset = 0
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=50)
            for upd in updates:
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        handle_message(upd["message"])
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                except Exception as e:  # не роняем бота из-за одного апдейта
                    print(f"handler error: {e}")
                    chat = (upd.get("message") or upd.get("callback_query", {}).get("message") or {}).get("chat", {})
                    if chat.get("id"):
                        try:
                            reply(chat["id"], f"⚠️ Ошибка: {e}")
                        except Exception:
                            pass
        except Exception as e:
            print(f"polling error: {e}; retry in 5s")
            time.sleep(5)


if __name__ == "__main__":
    main()
