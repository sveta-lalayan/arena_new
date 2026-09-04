from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("🎮 Играть (выбрать вручную)", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start — точка входа в бота."""
    user = update.effective_user

    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в <b>Arena 2.0</b> — твою языковую тренировочную площадку!\n\n"
        "⚔️ <b>ENTER ARENA</b> — пройди 8 коротких ходов, и ARENA определит твой уровень\n"
        "и подберёт идеального противника.\n\n"
        "🎮 <b>Играть (выбрать вручную)</b> — выбери язык, уровень, тему и персонажа сам."
    )

    keyboard = [
        [InlineKeyboardButton("⚔️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("🎮 Играть (выбрать вручную)", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с ARENA профилем."""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_data = context.user_data

    # Получаем данные ARENA
    level = user_data.get("level", "—")
    arena_profile = user_data.get("arena_profile", {})
    growth_skills = arena_profile.get("growth_skills", [])
    main_growth = growth_skills[0] if growth_skills else "precision"
    growth_name = COMMUNICATION_SKILLS.get(main_growth, {}).get("name", main_growth)

    # Формируем главный экран
    main_text = (
        f"🏛️ <b>ARENA</b>\n\n"
        f"👋 {user.first_name}\n\n"
        f"📊 <b>Текущий уровень</b>\n"
        f"{level} → {_next_level(level)}\n\n"
        f"🎯 <b>Current Focus</b>\n"
        f"{growth_name}\n\n"
        f"⚔️ <b>Your Next Battle</b>\n"
        f"Продолжи свой путь к {_next_level(level)}\n\n"
        f"🔥 <b>XP</b> 2,340 / 5,000"
    )

    keyboard = [
        [InlineKeyboardButton("⚔️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("🎮 Играть (выбрать вручную)", callback_data="menu_play")],
        [InlineKeyboardButton("📊 Мой ARENA профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ]

    await query.edit_message_text(
        main_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


def _next_level(level: str) -> str:
    """Возвращает следующий уровень."""
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    try:
        idx = levels.index(level)
        if idx < len(levels) - 1:
            return levels[idx + 1]
        return "🏆 Мастер"
    except ValueError:
        return "B2"