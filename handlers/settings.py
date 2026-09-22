"""
handlers/settings.py — экран настроек ARENA.

Здесь пользователь раздельно меняет:
  • interface_language — язык интерфейса (меню, кнопки, системные сообщения);
  • learning_language  — язык, на котором он практикуется (Temple, Battle, Free Talk).

Правило:
  - interface_language используется для ВСЕГО текста в этом экране.
  - learning_language трогает только AI-диалоги и не влияет на язык меню.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database as db
import i18n
from config import SUPPORTED_LANGUAGES, LANGUAGE_DISPLAY, LANGUAGE_FLAGS
from handlers.ui import send_or_edit


def _lang_rows(prefix: str, current: str) -> list[list[InlineKeyboardButton]]:
    """Кнопки выбора языка. Текущий помечен ✅."""
    rows: list[list[InlineKeyboardButton]] = []
    for code in SUPPORTED_LANGUAGES:
        label = f"{LANGUAGE_FLAGS.get(code, '')} {LANGUAGE_DISPLAY.get(code, code)}".strip()
        if code == current:
            label = "✅ " + label
        rows.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{code}")])
    return rows


def _settings_keyboard(il: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "SETTINGS.CHANGE_INTERFACE"), callback_data="set_pick_iface")],
        [InlineKeyboardButton(i18n.t(il, "SETTINGS.CHANGE_LEARNING"), callback_data="set_pick_learn")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ])


def _settings_text(il: str, ll: str) -> str:
    iface_label = f"{LANGUAGE_FLAGS.get(il, '')} {LANGUAGE_DISPLAY.get(il, il)}".strip()
    learn_label = f"{LANGUAGE_FLAGS.get(ll, '')} {LANGUAGE_DISPLAY.get(ll, ll)}".strip()
    return (
        f"<b>{i18n.t(il, 'SETTINGS.TITLE')}</b>\n\n"
        f"{i18n.t(il, 'SETTINGS.INTERFACE_LANGUAGE')}: <b>{iface_label}</b>\n"
        f"{i18n.t(il, 'SETTINGS.LEARNING_LANGUAGE')}: <b>{learn_label}</b>"
    )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный экран настроек."""
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    ll = db.get_learning_language(user_id)
    await send_or_edit(
        update,
        _settings_text(il, ll),
        reply_markup=_settings_keyboard(il),
        parse_mode="HTML",
    )


async def pick_interface(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор нового interface_language. Текущий язык — язык UI, в котором идёт выбор."""
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    rows = _lang_rows("set_iface", il)
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="menu_settings")])

    await send_or_edit(
        update,
        f"<b>{i18n.t(il, 'SETTINGS.CHANGE_INTERFACE')}</b>",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


async def pick_learning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор нового learning_language. UI-язык на этом экране НЕ меняется."""
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    ll = db.get_learning_language(user_id)

    rows = _lang_rows("set_learn", ll)
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="menu_settings")])

    await send_or_edit(
        update,
        f"<b>{i18n.t(il, 'SETTINGS.CHANGE_LEARNING')}</b>",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


async def set_interface_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь выбрал новый interface_language."""
    query = update.callback_query
    user_id = update.effective_user.id
    code = query.data.replace("set_iface_", "")

    if code in SUPPORTED_LANGUAGES:
        db.set_interface_language(user_id, code)

    # Сразу показываем экран настроек уже на новом языке.
    await settings_menu(update, context)


async def set_learning_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь выбрал новый learning_language. UI-язык не меняем."""
    query = update.callback_query
    user_id = update.effective_user.id
    code = query.data.replace("set_learn_", "")

    if code in SUPPORTED_LANGUAGES:
        db.set_learning_language(user_id, code)

    # Возвращаемся в настройки; текст будет на interface_language.
    await settings_menu(update, context)