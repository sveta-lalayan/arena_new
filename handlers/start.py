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
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    context.user_data.clear()

    profile_text = gamification.format_profile(user.id, user.first_name or "Игрок")
    await update.message.reply_text(
        f"👋 Привет! Это <b>Arena 2.0</b> — тренируй язык в диалогах с яркими персонажами "
        f"и зарабатывай баллы.\n\n{profile_text}",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню по нажатию кнопки."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    context.user_data.clear()

    profile_text = gamification.format_profile(user.id, user.first_name or "Игрок")
    await query.edit_message_text(
        f"🏠 <b>Главное меню</b>\n\n{profile_text}",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
