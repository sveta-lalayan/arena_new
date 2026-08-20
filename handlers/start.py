from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import gamification


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Играть", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start — точка входа в бота."""
    user = update.effective_user


    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в <b>Arena 2.0</b> — твою языковую тренировочную площадку!\n\n"
        "🧭 <b>Сначала давай познакомимся</b>\n"
        "Я — Alex, твой проводник. Зададим пару вопросов, чтобы я понял,\n"
        "с каким персонажем тебе лучше всего общаться.\n\n"
        "Это не тест и не оценка. Просто живой разговор.\n"
        "Готов? 👇"
    )

    keyboard = [
        [InlineKeyboardButton("🧭 Начать знакомство", callback_data="menu_intro")],
        [InlineKeyboardButton("🎮 Сразу в игру", callback_data="menu_play")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с кнопками."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🎮 Играть", callback_data="menu_play")],
        [InlineKeyboardButton("🧭 Гид (пройти заново)", callback_data="menu_intro")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ]

    await query.edit_message_text(
        "🏠 <b>Главное меню</b>\n\n"
        "Выбери, что хочешь сделать:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

