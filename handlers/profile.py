from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import gamification

BACK_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    [InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")],
])

ACHIEVEMENTS_BACK_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏛️ Моя арена", callback_data="menu_profile")],
    [InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")],
])


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = gamification.format_profile(user.id, user.first_name or "Игрок")
    await update.message.reply_text(text, reply_markup=BACK_KEYBOARD, parse_mode="HTML")


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    text = gamification.format_profile(user.id, user.first_name or "Игрок")
    await query.edit_message_text(text, reply_markup=BACK_KEYBOARD, parse_mode="HTML")


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = gamification.format_achievements(user.id)
    await update.message.reply_text(text, reply_markup=ACHIEVEMENTS_BACK_KEYBOARD, parse_mode="HTML")


async def achievements_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    text = gamification.format_achievements(user.id)
    await query.edit_message_text(text, reply_markup=ACHIEVEMENTS_BACK_KEYBOARD, parse_mode="HTML")
