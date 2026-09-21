import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

# --- OpenAI (текст, распознавание и синтез речи) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")

DB_PATH = os.getenv("DB_PATH", "arena2.db")
CHECKPOINT_TURNS = int(os.getenv("CHECKPOINT_TURNS", "6"))

# Сколько реплик пользователя длится Храм (первое знакомство)
FIRST_ENCOUNTER_MOVES = int(os.getenv("FIRST_ENCOUNTER_MOVES", "8"))

# Длительность боя. Для теста — 2 минуты, в бою — поставь 10 в .env
BATTLE_DURATION_MINUTES = int(os.getenv("BATTLE_DURATION_MINUTES", "2"))
# Страховка: максимум реплик игрока за один бой (обычно бой заканчивается по таймеру раньше)
BATTLE_MAX_ROUNDS = int(os.getenv("BATTLE_MAX_ROUNDS", "12"))
# Бой доступен раз в N часов. Free talk — без ограничений.
BATTLE_COOLDOWN_HOURS = int(os.getenv("BATTLE_COOLDOWN_HOURS", "24"))

# В какой час (UTC, 0-23) отправлять ежедневный пуш от персонажа
DAILY_PUSH_HOUR = int(os.getenv("DAILY_PUSH_HOUR", "12"))

CONVICTION_START = int(os.getenv("CONVICTION_START", "100"))
# Ниже какого значения "убеждённости" персонажа игрок побеждает досрочно
CONVICTION_WIN_THRESHOLD = int(os.getenv("CONVICTION_WIN_THRESHOLD", "15"))

# Победа: win_score = 50% "насколько убеждён персонаж" + 50% средний балл по 10 критериям.
WIN_SCORE_THRESHOLD = int(os.getenv("WIN_SCORE_THRESHOLD", "60"))
# Минимум реплик игрока, чтобы можно было выиграть (кроме досрочной победы)
MIN_ROUNDS_TO_WIN = int(os.getenv("MIN_ROUNDS_TO_WIN", "2"))

# --- Админы: для них правило "один бой в 24 часа" не действует (тестирование) ---
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "654485503").split(",")
    if x.strip().isdigit()
}


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS
