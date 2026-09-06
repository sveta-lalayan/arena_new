from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Добро пожаловать в <b>Arena 2.0</b>!\n\n"
        "🏛️ <b>ENTER ARENA</b> — пройди 8 ходов, и ARENA подберёт тебе противника.\n\n"
        "🎮 <b>Играть</b> — выбери всё сам."
    )

    keyboard = [
        [InlineKeyboardButton("🏛️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("🎮 Играть", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🏛️ ENTER ARENA", callback_data="menu_enter_arena")],
        [InlineKeyboardButton("🎮 Играть", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="menu_achievements")],
    ]

    await query.edit_message_text(
        "🏠 <b>Главное меню</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )