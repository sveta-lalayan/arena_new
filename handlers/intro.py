import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
from config import FIRST_ENCOUNTER_MOVES, BATTLE_DURATION_MINUTES
from game_data import LANGUAGES, PERSONALITIES

logger = logging.getLogger(__name__)

FE_STATE_KEYS = ["fe_language", "fe_dialogue", "fe_awaiting_response"]


def _reset_fe_state(context: ContextTypes.DEFAULT_TYPE):
    for key in FE_STATE_KEYS:
        context.user_data.pop(key, None)


async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_fe_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"fe_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    text = "🏛️ <b>ARENA</b>\n\nВыбери язык."
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.replace("fe_lang_", "")
    context.user_data["fe_language"] = language
    context.user_data["fe_dialogue"] = []
    context.user_data["fe_awaiting_response"] = True

    await query.edit_message_text(
        "🏛️ <b>ARENA IS LISTENING.</b>\n\n"
        "<b>Your move.</b>\n\n"
        "<i>what I do · what I love · what I think · anything</i>",
        parse_mode="HTML",
    )


async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ВАЖНО: нигде в этой функции не показываем пользователю номер хода
    (никаких "1/8", "2/8" и т.п.) — это внутренний счётчик, скрытый от
    человека. Arena просто слушает и реагирует, без видимого таймлайна.
    """
    user_text = update.message.text.strip()
    if len(user_text) < 1:
        return

    dialogue = context.user_data.setdefault("fe_dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    context.user_data["fe_awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")

    if user_turns >= FIRST_ENCOUNTER_MOVES:
        await _reveal(update, context)
        return

    language = context.user_data.get("fe_language", "English")
    history = "\n".join(f"{'User' if d['speaker'] == 'User' else 'ARENA'}: {d['text']}" for d in dialogue)

    reaction = await asyncio.to_thread(
        ai.generate_arena_reaction,
        history,
        user_text,
        language,
        user_turns + 1,  # только для внутренней ориентации модели
    )
    dialogue.append({"speaker": "AI", "text": reaction})
    context.user_data["fe_awaiting_response"] = True

    # Отправляем ТОЛЬКО реакцию — без каких-либо счётчиков ходов
    await update.message.reply_text(reaction)


async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("fe_language", "English")
    dialogue = context.user_data.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_name = update.effective_user.first_name or ""

    result = await asyncio.to_thread(ai.analyze_first_encounter, user_responses, language)

    context.user_data["level"] = result["estimated_level"]
    context.user_data["personality"] = result["recommended_personality"]
    context.user_data["language"] = language
    context.user_data["user_interests"] = result.get("interests", [])
    topic = result.get("interests", ["интересная тема"])[0]
    context.user_data["topic"] = topic
    level = result["estimated_level"]
    personality = result["recommended_personality"]

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    # ===== Колкая фраза-рекомендация (без сухого отчёта с ярлыками) =====
    insight = await asyncio.to_thread(ai.generate_character_insight, personality, topic, user_name, language)

    recommendation = (
        f"Кажется, тебя зацепила тема <b>«{topic}»</b>.\n"
        f"Поговори об этом с <b>{person['full_name']}</b>.\n\n"
        f"💬 <i>{insight}</i>"
    )

    # ===== Короткое конкретное задание + оружие по уровню =====
    task = await asyncio.to_thread(ai.generate_mission_task, topic, personality, user_name, language)
    situation = await asyncio.to_thread(ai.generate_situation, topic, personality, language)
    weapons, _, win_condition = await asyncio.to_thread(
        ai.generate_weapons_by_level, topic, level, personality, language
    )

    context.user_data["mission"] = task
    context.user_data["mission_weapons"] = weapons
    context.user_data["win_condition"] = win_condition
    context.user_data["used_weapons"] = []

    # ===== Сохраняем персонажа/темы для ежедневного пуша (фича 4) =====
    db.set_push_profile(update.effective_user.id, personality, result.get("interests", [topic]))

    mission_text = (
        f"⚔️ <b>{task}</b>\n"
        f"<i>{situation}</i>\n\n"
        f"🗡️ <b>Оружие:</b> {weapons}\n\n"
        f"✅ <b>Условие победы:</b>\n{win_condition}\n\n"
        f"⏱️ {BATTLE_DURATION_MINUTES} мин"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ НАЧАТЬ БИТВУ С {person['name']}", callback_data="fe_start_battle")]
    ])

    photo = person.get("photo")
    if photo:
        try:
            await update.message.reply_photo(
                photo=photo,
                caption=recommendation + "\n\n" + mission_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            await update.message.reply_text(
                recommendation + "\n\n" + mission_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        await update.message.reply_text(
            recommendation + "\n\n" + mission_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    _reset_fe_state(context)


async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    personality = context.user_data.get("personality", "hr_manager")
    language = context.user_data.get("language", "English")
    topic = context.user_data.get("topic", "интересную тему")
    level = context.user_data.get("level", "B1")
    weapons = context.user_data.get("mission_weapons", "")
    mission = context.user_data.get("mission") or f"Убедить {personality} в теме «{topic}»."

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    opening = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)

    from bot import start_arena_timer
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    start_arena_timer(context, user_id, chat_id, minutes=BATTLE_DURATION_MINUTES)

    context.user_data["dialogue"] = [{"speaker": "AI", "text": opening}]
    context.user_data["awaiting_response"] = True
    context.user_data["turn"] = 0
    context.user_data["personality"] = personality
    context.user_data["mission_weapons"] = weapons
    context.user_data["used_weapons"] = []
    context.user_data["language"] = language
    context.user_data["level"] = level
    context.user_data["topic"] = topic
    context.user_data["mission"] = mission

    await query.edit_message_text(
        f"⚔️ <b>БИТВА НАЧАЛАСЬ!</b>\n\n"
        f"🎭 <b>{person['full_name']}:</b>\n"
        f"<i>{opening}</i>\n\n"
        f"💬 Напиши свой ответ!\n"
        f"⏰ <i>У тебя {BATTLE_DURATION_MINUTES} минут!</i>\n\n"
        f"🗡️ <b>Оружие:</b> {weapons}",
        parse_mode="HTML"
    )