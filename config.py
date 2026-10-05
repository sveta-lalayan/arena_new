"""
config.py — настройки ARENA.

Ключевое архитектурное правило: interface_language и learning_language
разделены. Telegram language_code используется ТОЛЬКО для первичного
определения interface_language, никогда — как язык обучения.
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

# --- OpenAI (текст, распознавание и синтез речи) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Если запросы к OpenAI блокируются напрямую (см. HANDOFF про блокировку из РФ),
# можно завернуть их через прокси — заполнив ОДНУ из двух переменных ниже,
# без изменения кода:
#
# 1) OPENAI_BASE_URL — если это "прокси-зеркало" самого OpenAI API
#    (отдельный домен, который сам проксирует запросы на api.openai.com).
#    Пример: OPENAI_BASE_URL=https://my-proxy.example.com/v1
#
# 2) OPENAI_PROXY — если это обычный HTTP/SOCKS5-прокси, через который нужно
#    заворачивать любой трафик (в т.ч. к настоящему api.openai.com).
#    Пример: OPENAI_PROXY=http://user:password@1.2.3.4:8080
#    Пример (SOCKS5): OPENAI_PROXY=socks5://user:password@1.2.3.4:1080
#    (для socks5 нужен пакет httpx[socks], см. requirements.txt)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
OPENAI_PROXY = os.getenv("OPENAI_PROXY", "").strip() or None
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")

DB_PATH = os.getenv("DB_PATH", "arena2.db")

# Сколько реплик пользователя длится Храм (первое знакомство)
FIRST_ENCOUNTER_MOVES = int(os.getenv("FIRST_ENCOUNTER_MOVES", "8"))

# Длительность боя: 10 минут в проде, 2 для теста (ставится в .env)
BATTLE_DURATION_MINUTES = int(os.getenv("BATTLE_DURATION_MINUTES", "10"))
BATTLE_MAX_ROUNDS = int(os.getenv("BATTLE_MAX_ROUNDS", "20"))
BATTLE_COOLDOWN_HOURS = int(os.getenv("BATTLE_COOLDOWN_HOURS", "24"))

# Час (UTC, 0-23) ежедневного пуша
DAILY_PUSH_HOUR = int(os.getenv("DAILY_PUSH_HOUR", "12"))

# Стартовая убеждённость и досрочная победа
CONVICTION_START = int(os.getenv("CONVICTION_START", "100"))
CONVICTION_WIN_THRESHOLD = int(os.getenv("CONVICTION_WIN_THRESHOLD", "15"))

# Победа: win_score = 50% «убеждённость» + 50% средний балл по 10 критериям
WIN_SCORE_THRESHOLD = int(os.getenv("WIN_SCORE_THRESHOLD", "60"))
MIN_ROUNDS_TO_WIN = int(os.getenv("MIN_ROUNDS_TO_WIN", "2"))

# Telegram-канал: разборы приёмов «в исполнении» персонажей (ссылка показывается в My Arsenal)
CHANNEL_URL = os.getenv("ARENA_CHANNEL_URL", "https://t.me/arena_league")

# --- Админы (обходят кулдаун и правило «Храм один раз») ---
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "654485503").split(",")
    if x.strip().isdigit()
}


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


# ============================================================
# ЯЗЫКИ
# ============================================================
# Два независимых набора языков:
#   - interface_language: язык UI (меню, кнопки, системные сообщения)
#   - learning_language: язык, на котором идёт практика (Temple, Battle, Free Talk)
#
# Значения ВСЕГДА хранятся в БД как короткие ISO-коды: en, ru, de, es, it, ko, zh.
# Внутренние ключи LANGUAGES (english / russian / ...) используются только
# в промптах к GPT и в подборе голоса для TTS.

SUPPORTED_LANGUAGES = ["en", "ru", "de", "es", "it", "ko", "zh"]
DEFAULT_INTERFACE_LANGUAGE = "en"
DEFAULT_LEARNING_LANGUAGE = "en"

# ISO-код → внутренний ключ (english, russian, ...)
# Нужен для промптов GPT, выбора голоса TTS и кода Whisper.
ISO_TO_LANG_KEY = {
    "en": "english",
    "ru": "russian",
    "de": "german",
    "es": "spanish",
    "it": "italian",
    "ko": "korean",
    "zh": "chinese",
}
LANG_KEY_TO_ISO = {v: k for k, v in ISO_TO_LANG_KEY.items()}

# Человекочитаемые названия языков для UI (в настройках, в выборе языка обучения).
# Названия НЕ локализуются — язык всегда называется на самом себе.
LANGUAGE_DISPLAY = {
    "en": "English",
    "ru": "Русский",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "ko": "한국어",
    "zh": "中文",
}

# Флаги для кнопок выбора языка (без названия).
LANGUAGE_FLAGS = {
    "en": "🇬🇧",
    "ru": "🇷🇺",
    "de": "🇩🇪",
    "es": "🇪🇸",
    "it": "🇮🇹",
    "ko": "🇰🇷",
    "zh": "🇨🇳",
}

# Маппинг Telegram language_code → наш ISO-код (для первичного определения
# interface_language при первом /start).
TELEGRAM_LANG_MAP = {
    "en": "en", "en-us": "en", "en-gb": "en",
    "ru": "ru", "ru-ru": "ru",
    "de": "de", "de-de": "de", "de-at": "de", "de-ch": "de",
    "es": "es", "es-es": "es", "es-mx": "es", "es-ar": "es",
    "it": "it", "it-it": "it",
    "ko": "ko", "ko-kr": "ko",
    "zh": "zh", "zh-cn": "zh", "zh-hans": "zh", "zh-tw": "zh", "zh-hant": "zh",
}


def telegram_lang_to_iso(language_code: str | None) -> str:
    """Telegram language_code → наш ISO. Никогда не даёт 'ru' по умолчанию."""
    if not language_code:
        return DEFAULT_INTERFACE_LANGUAGE
    code = language_code.lower().strip()
    if code in TELEGRAM_LANG_MAP:
        return TELEGRAM_LANG_MAP[code]
    short = code.split("-")[0]
    return TELEGRAM_LANG_MAP.get(short, DEFAULT_INTERFACE_LANGUAGE)


# ============================================================
# ЛОКАЛИЗАЦИЯ
# ============================================================
LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")