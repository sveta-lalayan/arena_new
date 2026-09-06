import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")

DB_PATH = os.getenv("DB_PATH", "arena2.db")
CHECKPOINT_TURNS = int(os.getenv("CHECKPOINT_TURNS", "6"))
FIRST_ENCOUNTER_MOVES = int(os.getenv("FIRST_ENCOUNTER_MOVES", "8"))
BATTLE_DURATION_MINUTES = int(os.getenv("BATTLE_DURATION_MINUTES", "2"))