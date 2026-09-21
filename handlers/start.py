from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
from config import is_admin


def post_battle_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Free talk", callback_data="freetalk")],
        [InlineKeyboardButton("🏛️ Моя арена", callback_data="menu_profile")],
    ])


def _build_menu(telegram_id: int) -> InlineKeyboardMarkup:
    # Админ всегда видит Храм — чтобы можно было проходить сколько угодно раз.
    if is_admin(telegram_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏛️ Арена", callback_data="menu_enter_arena")],
            [InlineKeyboardButton("⚔️ Battle", callback_data="menu_play")],
            [InlineKeyboardButton("💬 Free talk", callback_data="freetalk")],
            [InlineKeyboardButton("🏛️ Моя арена", callback_data="menu_profile")],
        ])

    # Новичок — одна кнопка.
    if not db.has_completed_first_battle(telegram_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏛️ Арена", callback_data="menu_enter_arena")],
        ])

    # После первого боя — полное меню.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Battle", callback_data="menu_play")],
        [InlineKeyboardButton("💬 Free talk", callback_data="freetalk")],
        [InlineKeyboardButton("🏛️ Моя арена", callback_data="menu_profile")],
    ])


def _welcome_text(user, first_time: bool) -> str:
    if first_time:
        return (
            f"👋 {user.first_name}\n"
            f"Welcome to <b>ARENA</b>.\n\n"
            f"🏛️ <b>Арена ждёт тебя.</b>\n"
            f"Она послушает — и решит, кого ты встретишь."
        )
    return (
        f"👋 {user.first_name}\n"
        f"Арена наблюдает. Бой — раз в 24 часа, свободный разговор — всегда."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        db.reset_user_data(user.id)
        context.user_data.clear()

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
