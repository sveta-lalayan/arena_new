"""
handlers/start.py — точка входа и главное меню ARENA.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import i18n
from config import (
    is_admin,
    telegram_lang_to_iso,
    SUPPORTED_LANGUAGES,
    DEFAULT_INTERFACE_LANGUAGE,
    BATTLE_COOLDOWN_HOURS,
)
from handlers.ui import send_or_edit


def _ensure_interface_language(user) -> str:
    current = db.get_interface_language(user.id)
    if current:
        return current
    detected = telegram_lang_to_iso(getattr(user, "language_code", None))
    if detected not in SUPPORTED_LANGUAGES:
        detected = DEFAULT_INTERFACE_LANGUAGE
    db.set_interface_language(user.id, detected)
    return detected


def _full_menu_keyboard(il: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.BATTLE"), callback_data="menu_play")],
        [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
        [InlineKeyboardButton(i18n.t(il, "MENU.SETTINGS"), callback_data="menu_settings")],
    ])


def _entry_keyboard(il: str) -> InlineKeyboardMarkup:
    """
    Первый экран — ОДНА кнопка, ведёт не в меню, а в Храм.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.ENTER_ARENA"),
                              callback_data="menu_enter_arena")],
    ])


def _admin_keyboard(il: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.ENTER_ARENA"),
                              callback_data="menu_enter_arena")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BATTLE"), callback_data="menu_play")],
        [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
        [InlineKeyboardButton(i18n.t(il, "MENU.SETTINGS"), callback_data="menu_settings")],
    ])


def _menu_keyboard(user_id: int, il: str) -> InlineKeyboardMarkup:
    if is_admin(user_id):
        return _admin_keyboard(il)
    if not db.has_completed_first_battle(user_id):
        return _entry_keyboard(il)
    return _full_menu_keyboard(il)


def _format_countdown(hours_left: float) -> str:
    """
    hours_left — сколько часов осталось до следующего боя.
    Возвращает "18h 42m" или похожее.
    """
    if hours_left <= 0:
        return ""
    total_minutes = int(hours_left * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    if h <= 0:
        return f"{m}m"
    return f"{h}h {m:02d}m"


def _welcome_text(user, il: str) -> str:
    """
    Экран для НОВИЧКА (ещё не прошёл первый бой).
    """
    return i18n.t(il, "START.WELCOME_FIRST", name=user.first_name or "")


def _welcome_back_text(user_id: int, user, il: str) -> str:
    """
    Экран после первого боя.
    Содержит обратный отсчёт до следующего боя, если cooldown активен.
    """
    name = user.first_name or ""
    hours_left = db.cooldown_hours_left(user_id)
    has_read = bool(db.get_current_read(user_id) or db.get_last_session(user_id))

    if is_admin(user_id) or hours_left <= 0:
        next_battle_line = i18n.t(il, "START.NEXT_BATTLE_NOW")
    else:
        cd = _format_countdown(hours_left)
        next_battle_line = i18n.t(il, "START.NEXT_BATTLE_IN", cd=cd)

    read_line = ""
    if has_read:
        read_line = i18n.t(il, "START.FIRST_READ")
    rest_line = i18n.t(il, "START.REST_WAITING")

    parts = [
        i18n.t(il, "START.WELCOME_BACK", name=name),
        read_line,
        next_battle_line,
        rest_line,
    ]
    return "\n".join(p for p in parts if p)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_admin(user.id):
        db.reset_user_data(user.id)
        context.user_data.clear()
        db.get_or_create_user(user.id, user.username, user.first_name)

    db.get_or_create_user(user.id, user.username, user.first_name)
    il = _ensure_interface_language(user)

    if not db.has_completed_first_battle(user.id) and not is_admin(user.id):
        text = _welcome_text(user, il)
    else:
        text = _welcome_back_text(user.id, user, il)

    await update.message.reply_text(
        text,
        reply_markup=_menu_keyboard(user.id, il),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    il = db.get_interface_language(user.id)

    if not db.has_completed_first_battle(user.id) and not is_admin(user.id):
        text = _welcome_text(user, il)
    else:
        text = _welcome_back_text(user.id, user, il)

    await send_or_edit(
        update,
        text,
        reply_markup=_menu_keyboard(user.id, il),
        parse_mode="HTML",
    )