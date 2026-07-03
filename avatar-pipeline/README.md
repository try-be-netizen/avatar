# Avatar Pipeline: очередь тем → видео с тобой → Telegram

Автогенерация видео с твоим ИИ-аватаром по расписанию через GitHub Actions.

## Как это работает

```
queue.yaml (темы) → Claude (скрипт) → [ElevenLabs (голос)] → HeyGen (рендер аватара) → Telegram
```

Твоё лицо и голос создаются **один раз** в HeyGen (Digital Twin). Дальше пайплайн
генерирует любое количество видео из текста — камера больше не нужна.

## Разовая настройка (~1 час)

### 1. Создай аватара в HeyGen
1. Запиши 1–2 минуты видео себя: фронтально, хороший свет, чистый фон, естественная речь с паузами.
2. HeyGen → Avatars → Create Avatar → Digital Twin → загрузи видео.
3. Запиши consent-заявление (подтверждение, что это ты).
4. После обработки скопируй `avatar_id` (виден в URL аватара или через `GET /v2/avatars`).
5. Там же появится клон голоса — скопируй `voice_id` (вкладка Voices).

### 2. (Опционально) Голос в ElevenLabs
Если хочешь режим `TTS_MODE=elevenlabs`: ElevenLabs → Voices → Instant Voice Clone →
загрузи 1–2 минуты чистой записи речи → скопируй `voice_id`.

### 3. API-ключи
- HeyGen: Settings → API → создать ключ (нужен платный план для API)
- Anthropic: console.anthropic.com
- ElevenLabs: Profile → API key
- Telegram: создай бота через @BotFather, узнай свой chat_id через @userinfobot

### 4. GitHub
1. Создай приватный репозиторий, залей эти файлы.
2. Settings → Secrets and variables → Actions → добавь секреты:
   `HEYGEN_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
   `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID`, (опц.) `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.
3. Actions → Generate avatar video → Run workflow (ручной тест).

## Ежедневное использование

Добавь тему в `queue.yaml`, закоммить — по расписанию (пн/ср/пт) пайплайн возьмёт
первую `pending`-тему, сгенерирует видео и пришлёт в Telegram. Расписание меняется
в `.github/workflows/generate.yml` (cron).

## Локальный запуск

```bash
pip install -r requirements.txt
export HEYGEN_API_KEY=... ANTHROPIC_API_KEY=... TELEGRAM_BOT_TOKEN=... \
       TELEGRAM_CHAT_ID=... HEYGEN_AVATAR_ID=... HEYGEN_VOICE_ID=...
python -m pipeline.run
```

## Режимы озвучки

| Режим | Как | Когда выбирать |
|---|---|---|
| `heygen_text` (дефолт) | HeyGen сам озвучивает текст твоим voice_id | Проще, меньше движущихся частей |
| `elevenlabs` | ElevenLabs делает mp3 → HeyGen анимирует под него | Дешевле по кредитам HeyGen, тоньше контроль интонаций, аудио переиспользуемо |

## Telegram-бот для очереди (bot/)

Пополнение очереди с телефона без ноутбука: текст или голосовое → бот коммитит тему
в `queue.yaml` через GitHub Contents API. Голосовые расшифровываются через ElevenLabs STT.

Команды: тема текстом («тема | заметки»), голосовое (после расшифровки бот показывает
текст и кнопки «В очередь / Отмена» — страховка, если STT ослышался), `/queue` — показать
очередь, `/go` — запустить генерацию немедленно, `/redo <правки>` — вернуть последнее
готовое видео в начало очереди с твоими правками к сценарию и сразу перегенерировать
(например: `/redo короче и без хука про бенчмарки`).

Установка (VM + systemd):
1. Создай fine-grained PAT на github.com/settings/personal-access-tokens: доступ только
   к этому репо, права **Contents: Read and write** и **Actions: Read and write**.
2. Узнай свой Telegram user id (@userinfobot) — бот отвечает только тебе.
3. На VM: скопируй `bot/` в `/opt/avatar-pipeline/bot`, заполни `.env` по `.env.example`
   (`chmod 600 .env`), поставь юнит из шапки `avatar-queue-bot.service`.

Полный цикл: голосовое боту в метро → тема в очереди → `/go` или cron → через 15 минут
готовое видео с тобой приходит в тот же Telegram.

## Важные детали

- **Сверь актуальные эндпоинты** в docs.heygen.com — API эволюционирует; скелет писался под v2 `/video/generate` + v1 `/video_status.get`.
- Рендер 1 минуты видео занимает обычно 5–15 минут — воркфлоу ждёт до 30.
- HeyGen списывает кредиты за минуты рендера — следи за балансом на тарифе.
- `[skip ci]` в коммите бота предотвращает рекурсивный запуск воркфлоу.
