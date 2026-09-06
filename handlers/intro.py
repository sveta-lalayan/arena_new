import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
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
        user_turns + 1
    )
    dialogue.append({"speaker": "AI", "text": reaction})
    context.user_data["fe_awaiting_response"] = True

    await update.message.reply_text(reaction)


async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("fe_language", "English")
    dialogue = context.user_data.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    await update.message.reply_text("I've seen enough.")

    result = await asyncio.to_thread(ai.analyze_first_encounter, user_responses, language)

    context.user_data["level"] = result["estimated_level"]
    context.user_data["personality"] = result["recommended_personality"]
    context.user_data["language"] = language
    context.user_data["user_interests"] = result.get("interests", [])
    topic = result.get("interests", ["интересная тема"])[0]
    context.user_data["topic"] = topic

    person = PERSONALITIES.get(result["recommended_personality"], PERSONALITIES["hr_manager"])

    # --- Интересы ---
    interests_text = "\n".join(f"  • {i}" for i in result.get("interests", ["разные темы"])[:3])

    # --- Профиль ---
    profile_text = (
        "🧠 <b>ARENA'S READ</b>\n\n"
        f"📊 <b>Уровень:</b> {result['estimated_level']}\n\n"
        f"🔍 <b>Интересующие темы:</b>\n{interests_text}\n\n"
        f"✅ <b>Сильная сторона:</b>\n{result.get('strength', 'Хорошо выражает мысли')}\n\n"
        f"🎯 <b>Зона роста:</b>\n{result.get('growth', 'Можно больше внимания деталям')}"
    )
    await update.message.reply_text(profile_text, parse_mode="HTML")

    # --- Рекомендация персонажа ---
    recommendation = (
        f"Вижу, тебя зацепила тема <b>«{topic}»</b>.\n"
        f"Было бы круто поговорить об этом с <b>{person['full_name']}</b> — "
        f"{person['desc']}\n\n"
        f"💬 <i>«{person.get('phrase', '')}»</i>"
    )

    # --- Генерируем слова для миссии ---
    level = context.user_data.get("level", "B1")
    words = await asyncio.to_thread(ai.generate_mission_words, topic, level, language)
    tips = await asyncio.to_thread(ai.generate_tips, result["recommended_personality"])
    context.user_data["mission_words"] = words

    # --- Миссия ---
    mission_text = (
        f"⚔️ <b>ТВОЯ МИССИЯ</b>\n\n"
        f"🎭 <b>{person['full_name']}</b>\n\n"
        f"📋 <b>Задача:</b>\n"
        f"Обсуди с {person['name']} тему: <b>{topic}</b>\n\n"
        f"📚 <b>Слова для победы</b> (используй их в диалоге):\n"
        f"{' · '.join(words.split(',')[:5])}\n\n"
        f"💡 <b>Советы:</b>\n{tips}\n\n"
        f"⏱️ <b>Время:</b> {BATTLE_DURATION_MINUTES} мин"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ НАЧАТЬ БИТВУ С {person['name']}", callback_data="fe_start_battle")]
    ])

    # --- Отправка ---
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
    mission_words = context.user_data.get("mission_words", "")

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    # --- Открывающая реплика ---
    opening = await asyncio.to_thread(
        ai.generate_opening_statement, personality, topic, level, language
    )

    # --- Запускаем таймер ---
    from bot import start_arena_timer
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    start_arena_timer(context, user_id, chat_id, minutes=BATTLE_DURATION_MINUTES)

    # --- СОСТОЯНИЕ ДЛЯ arena.py (ЭТО ГЛАВНОЕ!) ---
    context.user_data["dialogue"] = []
    context.user_data["dialogue"].append({"speaker": "AI", "text": opening})
    context.user_data["awaiting_response"] = True   # ← ЭТО КЛЮЧЕВОЕ!
    context.user_data["turn"] = 0
    context.user_data["personality"] = personality
    context.user_data["mission_words"] = mission_words
    context.user_data["language"] = language
    context.user_data["level"] = level
    context.user_data["topic"] = topic

    # ===== МИССИЯ: персонаж должен помнить это на протяжении ВСЕГО боя =====
    context.user_data["mission"] = (
        f"Убедить {person['name']} в теме «{topic}». "
        f"Не отклоняться от этой темы, даже если пользователь уводит разговор в сторону."
    )

    await query.edit_message_text(
        f"⚔️ <b>БИТВА НАЧАЛАСЬ!</b>\n\n"
        f"🎭 <b>{person['full_name']}:</b>\n"
        f"<i>{opening}</i>\n\n"
        f"💬 Напиши свой ответ!\n"
        f"⏰ <i>У тебя {BATTLE_DURATION_MINUTES} минут!</i>\n\n"
        f"📚 <b>Слова для победы:</b>\n"
        f"{' · '.join(mission_words.split(',')[:5])}",
        parse_mode="HTML"
    )