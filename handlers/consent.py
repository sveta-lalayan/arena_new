"""
handlers/consent.py — согласие, раздел «Privacy & data», /privacy, /reset, экспорт данных.
"""
import io
import json
import os

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

import database as db
from config import is_admin
from handlers.ui import send_or_edit

POLICY_URL = os.getenv("ARENA_POLICY_URL", "https://telegra.ph/REPLACE-ME")

ACCEPT_CALLBACK = "policy_accept"
PRIVACY_CALLBACK = "menu_privacy"
EXPORT_CALLBACK = "privacy_export"
RESET_ASK = "reset_ask"
RESET_CONFIRM = "reset_confirm"
RESET_CANCEL = "reset_cancel"

CONSENT_TEXT = (
    "BEFORE YOU ENTER ARENA\n\n"
    "ARENA is a closed beta with about 10 people. "
    "Please read this first.\n\n"
    "By continuing, you agree that:\n\n"
    "• ARENA stores what you write and say in the bot: your messages, "
    "voice transcriptions and your results.\n"
    "• From this, ARENA builds a personal profile (interests, goals, "
    "speaking patterns, strengths and weaknesses) to personalise your training.\n"
    "• Your texts and voice messages are processed by OpenAI (USA). "
    "Voice is turned into text; the audio file is not kept.\n"
    "• ARENA may send you reminder messages in Telegram.\n"
    "• Your data is not sold and not shared with anyone else.\n"
    "• You can read this notice, download your data or delete it at any time "
    "in Settings → Privacy & data (or with /privacy and /reset).\n\n"
    "Please don't share sensitive information (health, religion, politics): "
    "ARENA doesn't need it.\n"
    "You must be 18 or older to take part."
)

FALLBACK_TEXT = "✅ Thank you! Send /start to enter ARENA."

# Таблицы с данными пользователя (как в db.reset_user_data)
USER_TABLES = (
    "game_sessions", "achievements", "vocabulary_mistakes", "user_level_history",
    "arena_analyses", "freetalk_sessions", "user_criteria", "user_arsenal", "user_nemesis",
    "user_weapons", "user_skills", "user_topics", "user_tools", "user_arsenal_usage",
    "user_patterns", "user_interest_clusters", "notification_log",
    "user_goals", "user_avoids",
    "user_current_read", "user_under_pressure", "user_unsolved",
    "user_evidence", "user_discoveries", "user_notification_state",
)


# ============================================================
# Экран согласия + «страж»
# ============================================================

async def _send_consent_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I understand and agree", callback_data=ACCEPT_CALLBACK)],
        [InlineKeyboardButton("📄 Read full privacy notice", url=POLICY_URL)],
    ])
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=CONSENT_TEXT,
        reply_markup=keyboard,
    )


async def consent_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Срабатывает ПЕРЕД всеми остальными хендлерами (group=-1)."""
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None or chat.type != "private":
        return
    if is_admin(user.id):
        return

    query = update.callback_query

    if query is not None and query.data == ACCEPT_CALLBACK:
        db.get_or_create_user(user.id, user.username, user.first_name)
        db.accept_policy(user.id)
        await query.answer()
        try:
            from handlers.start import show_main_menu
            await show_main_menu(update, context)
        except Exception:
            try:
                await query.edit_message_text(FALLBACK_TEXT)
            except Exception:
                await context.bot.send_message(chat_id=chat.id, text=FALLBACK_TEXT)
        raise ApplicationHandlerStop

    if db.has_accepted_policy(user.id):
        return

    if query is not None:
        await query.answer()
    await _send_consent_screen(update, context)
    raise ApplicationHandlerStop


# ============================================================
# Раздел «Privacy & data»
# ============================================================

async def privacy_screen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Открывается из Настроек (кнопка) и командой /privacy."""
    user = update.effective_user
    if update.callback_query is not None:
        await update.callback_query.answer()

    row = db.get_user(user.id)
    accepted = ""
    if row and row["policy_accepted_at"]:
        accepted = f"You agreed to the privacy notice on {row['policy_accepted_at'][:10]}.\n\n"

    text = (
        "🔒 PRIVACY & YOUR DATA\n\n"
        f"{accepted}"
        "ARENA stores your messages, voice transcriptions, results and the "
        "personal profile it builds from them. Texts and voice are processed "
        "by OpenAI (USA). Nothing is sold or shared.\n\n"
        "Here you can read the full notice, download a copy of your data, "
        "or delete everything."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Read privacy notice", url=POLICY_URL)],
        [InlineKeyboardButton("📥 Download my data", callback_data=EXPORT_CALLBACK)],
        [InlineKeyboardButton("🗑 Delete all my data", callback_data=RESET_ASK)],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_settings")],
    ])
    await send_or_edit(update, text, reply_markup=keyboard)


# ============================================================
# Экспорт данных (право на копию)
# ============================================================

def _collect_user_data(user_id: int) -> dict:
    data: dict = {}
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,)).fetchone()
        data["users"] = [dict(row)] if row else []
        for table in USER_TABLES:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE telegram_id = ?", (user_id,)
            ).fetchall()
            data[table] = [dict(r) for r in rows]
    return data


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer("Preparing your file…")
    payload = json.dumps(_collect_user_data(user.id), ensure_ascii=False, indent=2, default=str)
    bio = io.BytesIO(payload.encode("utf-8"))
    bio.name = "arena_my_data.json"
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=bio,
        filename="arena_my_data.json",
        caption="📥 Here is a copy of the data ARENA stores about you.",
    )


# ============================================================
# Удаление данных (/reset и кнопка)
# ============================================================

def _reset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Yes, delete everything", callback_data=RESET_CONFIRM)],
        [InlineKeyboardButton("Cancel", callback_data=RESET_CANCEL)],
    ])


RESET_WARNING = (
    "This will permanently delete all your ARENA data: your profile, "
    "battles, free talks, Arsenal and everything the bot learned about you.\n\n"
    "This cannot be undone. Continue?"
)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(RESET_WARNING, reply_markup=_reset_keyboard())


async def reset_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await send_or_edit(update, RESET_WARNING, reply_markup=_reset_keyboard())


async def reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    db.reset_user_data(user.id)      # удаляет и строку users, поэтому согласие тоже сбрасывается
    context.user_data.clear()
    await send_or_edit(
        update,
        "✅ All your data has been deleted.\n"
        "Send /start to begin again. You will be asked for consent again.",
    )


async def reset_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await privacy_screen(update, context)


# ============================================================
# Подключение
# ============================================================

async def set_commands(app: Application) -> None:
    """Список команд в кнопке «Menu» рядом с полем ввода."""
    await app.bot.set_my_commands([
        BotCommand("start", "Open ARENA"),
        BotCommand("privacy", "Privacy & my data"),
        BotCommand("reset", "Delete all my data"),
    ])


def register(app: Application) -> None:
    app.add_handler(TypeHandler(Update, consent_gate), group=-1)
    app.add_handler(CommandHandler("privacy", privacy_screen))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(privacy_screen, pattern=f"^{PRIVACY_CALLBACK}$"))
    app.add_handler(CallbackQueryHandler(export_data, pattern=f"^{EXPORT_CALLBACK}$"))
    app.add_handler(CallbackQueryHandler(reset_ask, pattern=f"^{RESET_ASK}$"))
    app.add_handler(CallbackQueryHandler(reset_confirm, pattern=f"^{RESET_CONFIRM}$"))
    app.add_handler(CallbackQueryHandler(reset_cancel, pattern=f"^{RESET_CANCEL}$"))