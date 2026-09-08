from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db


def _build_menu(telegram_id: int) -> InlineKeyboardMarkup:
    """До первого завершённого боя — только один вход в ARENA.
    После первого боя — полное меню: новая встреча, свободный разговор,
    профиль, достижения."""
    if not db.has_completed_first_battle(telegram_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏛️ ENTER ARENA", callback_data="menu_enter_arena")],
        ])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏛️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("⚔️ Battle", callback_data="menu_play")],
        [InlineKeyboardButton("💬 Free talk", callback_data="freetalk")],
        [InlineKeyboardButton("👤 Profile", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Achievements", callback_data="menu_achievements")],
    ])


def _welcome_text(user, first_time: bool) -> str:
    if first_time:
        return (
            f"👋 {user.first_name}\n"
            f"Welcome to <b>ARENA</b>.\n\n"
            f"🏛️ <b>ENTER ARENA</b>\n"
            f"Let Arena listen to you and decide who you meet."
        )
    return (
        f"👋 {user.first_name}\n"
        f"Welcome back to <b>ARENA</b>."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    first_time = not db.has_completed_first_battle(user.id)

    await update.message.reply_text(
        _welcome_text(user, first_time),
        reply_markup=_build_menu(user.id),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    first_time = not db.has_completed_first_battle(user.id)

    await query.edit_message_text(
        _welcome_text(user, first_time),
        reply_markup=_build_menu(user.id),
        parse_mode="HTML",
    )