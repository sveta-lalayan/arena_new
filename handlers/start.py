"""
handlers/start.py — точка входа и главное меню ARENA.

Здесь:
  • определяем interface_language по Telegram language_code (только при первом заходе);
  • показываем одну кнопку ENTER ARENA, пока Храм не пройден;
  • после первого боя — полное меню: BATTLE / FREE TALK / MY ARENA / MY ARSENAL / SETTINGS;
  • админ видит всё меню сразу и может заходить в Храм сколько угодно раз.
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
)
from handlers.ui import send_or_edit


def _ensure_interface_language(user) -> str:
    """
    Возвращает interface_language пользователя.
    При первом заходе (в БД пусто) определяет его по Telegram language_code.
    Если язык не поддержан — English.
    """
    current = db.get_interface_language(user.id)
    if current:
        return current

    detected = telegram_lang_to_iso(getattr(user, "language_code", None))
    if detected not in SUPPORTED_LANGUAGES:
        detected = DEFAULT_INTERFACE_LANGUAGE
    db.set_interface_language(user.id, detected)
    return detected


def _main_menu_keyboard(il: str) -> InlineKeyboardMarkup:
    """
    Полное меню: 5 кнопок по принципу «минимум RPG, максимум действий».
    Локализуется по interface_language.
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.BATTLE"), callback_data="menu_play")],
        [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
        [InlineKeyboardButton(i18n.t(il, "MENU.SETTINGS"), callback_data="menu_settings")],
    ])


def _entry_keyboard(il: str) -> InlineKeyboardMarkup:
    """Пока Храм не пройден — только вход в Арену. Плюс настройки и язык."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.ENTER_ARENA"), callback_data="menu_enter_arena")],
        [InlineKeyboardButton(i18n.t(il, "MENU.SETTINGS"), callback_data="menu_settings")],
    ])


def _menu_keyboard(user_id: int, il: str) -> InlineKeyboardMarkup:
    # Админ всегда видит полное меню + кнопку Храма сверху.
    if is_admin(user_id):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.t(il, "MENU.ENTER_ARENA"), callback_data="menu_enter_arena")],
            [InlineKeyboardButton(i18n.t(il, "MENU.BATTLE"), callback_data="menu_play")],
            [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
            [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
            [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
            [InlineKeyboardButton(i18n.t(il, "MENU.SETTINGS"), callback_data="menu_settings")],
        ])

    # Новичок — одна кнопка входа в Храм + настройки.
    if not db.has_completed_temple(user_id) and not db.has_completed_first_battle(user_id):
        return _entry_keyboard(il)

    # Прошёл Храм — полное меню.
    return _main_menu_keyboard(il)


def _welcome_text(user, il: str, first_time: bool) -> str:
    key = "START.WELCOME_FIRST" if first_time else "START.WELCOME_BACK"
    return i18n.t(il, key, name=user.first_name or "")


def _is_first_time(user_id: int) -> bool:
    return not db.has_completed_temple(user_id) and not db.has_completed_first_battle(user_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Админ при /start сбрасывает свои данные — можно пройти весь флоу заново.
    if is_admin(user.id):
        db.reset_user_data(user.id)
        context.user_data.clear()
        db.get_or_create_user(user.id, user.username, user.first_name)

    # Создаём пользователя (если ещё нет) и определяем interface_language.
    db.get_or_create_user(user.id, user.username, user.first_name)
    il = _ensure_interface_language(user)

    first_time = _is_first_time(user.id)

    await update.message.reply_text(
        _welcome_text(user, il, first_time),
        reply_markup=_menu_keyboard(user.id, il),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback для кнопки «Назад в меню» и возврата с любых экранов."""
    user = update.effective_user
    il = db.get_interface_language(user.id)
    first_time = _is_first_time(user.id)

    await send_or_edit(
        update,
        _welcome_text(user, il, first_time),
        reply_markup=_menu_keyboard(user.id, il),
        parse_mode="HTML",
    )