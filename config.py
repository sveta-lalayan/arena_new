import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

# --- OpenAI (заменяет Yandex GPT везде: текст, распознавание и синтез речи) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TRANSCRIBE_MODEL = os.getenv("OPENAI_TRANSCRIBE_MODEL", "whisper-1")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")

DB_PATH = os.getenv("DB_PATH", "arena2.db")
CHECKPOINT_TURNS = int(os.getenv("CHECKPOINT_TURNS", "6"))
FIRST_ENCOUNTER_MOVES = int(os.getenv("FIRST_ENCOUNTER_MOVES", "8"))
BATTLE_DURATION_MINUTES = int(os.getenv("BATTLE_DURATION_MINUTES", "2"))

# В какой час (UTC, 0-23) отправлять ежедневный пуш от персонажа
DAILY_PUSH_HOUR = int(os.getenv("DAILY_PUSH_HOUR", "12"))
BATTLE_MAX_ROUNDS = int(os.getenv("BATTLE_MAX_ROUNDS", "8"))
CONVICTION_START = int(os.getenv("CONVICTION_START", "100"))

# Ниже какого значения "убеждённости" персонажа считаем, что игрок победил
# досрочно (не дожидаясь BATTLE_MAX_ROUNDS раундов).
CONVICTION_WIN_THRESHOLD = int(os.getenv("CONVICTION_WIN_THRESHOLD", "15"))