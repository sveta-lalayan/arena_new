"""
Конфигурация Arena 2.0.

ВСЕ секреты берутся только из переменных окружения (.env).
Ничего чувствительного здесь не хардкодится — .env НЕ должен попадать в git
(проверь, что .env есть в .gitignore).
"""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Создай файл .env на основе .env.example "
        "и укажи там свой токен (получить/перевыпустить можно у @BotFather)."
    )

# Yandex GPT
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")

# Путь к файлу базы данных SQLite
DB_PATH = os.getenv("DB_PATH", "arena2.db")

# Список telegram_id админов (через запятую в .env: ADMIN_IDS=123,456)
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# Через сколько раундов диалога спрашивать пользователя "продолжаем?"
CHECKPOINT_TURNS = int(os.getenv("CHECKPOINT_TURNS", "8"))
# Сколько реплик пользователя собирает вступительный диалог с гидом,
# прежде чем показать "первое впечатление" и рекомендовать персонажа
INTRO_ROUNDS = int(os.getenv("INTRO_ROUNDS", "6"))