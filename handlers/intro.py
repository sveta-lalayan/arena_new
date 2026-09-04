"""
ARENA First Encounter.

Флоу (по спецификации):
CHOOSE LANGUAGE → ENTER ARENA → "ARENA IS LISTENING. Your move." →
8 коротких ходов живого разговора (ARENA реагирует, не задаёт анкету) →
"I've seen enough." → Communication Profile → рекомендация персонажа
→ [ENTER BATTLE] → обычный flow существующего персонажа.

Уровень пользователю НЕ задаётся вопросом — ARENA определяет его сама.
Диагностика полностью скрыта.
"""
import asyncio
import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
from config import FIRST_ENCOUNTER_MOVES
from game_data import (
    LANGUAGES,
    PERSONALITIES,
    LANGUAGE_SKILLS,
    COMMUNICATION_SKILLS,
    PERSONALITY_MISSIONS,
    BATTLE_COMPLEXITY,
    PERSONALITY_MISSION_TEMPLATES,
    PERSONALITY_VOICE,
)

logger = logging.getLogger(__name__)

FE_STATE_KEYS = ["fe_language", "fe_dialogue", "fe_awaiting_response"]


def _reset_fe_state(context: ContextTypes.DEFAULT_TYPE):
    for key in FE_STATE_KEYS:
        context.user_data.pop(key, None)


# ---------- Вход ----------

async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Точка входа — команда /arena или кнопка '⚔️ ENTER ARENA'."""
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
        "🏛️ <b>ARENA</b>\n\n"
        "<i>Ты входишь в пространство, где слова становятся отражением.</i>\n\n"
        "<b>Говори о том, что важно.</b>\n"
        "<i>что я делаю · что я люблю · о чём я думаю · что угодно</i>\n\n"
        "ARENA слушает.",
        parse_mode="HTML",
    )


# ---------- 8 ходов First Encounter ----------

async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа пользователя в First Encounter."""
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

    # Берём только последние реплики для контекста
    recent_dialogue = dialogue[-6:] if len(dialogue) > 6 else dialogue
    history = "\n".join(f"{'User' if d['speaker'] == 'User' else 'ARENA'}: {d['text']}" for d in recent_dialogue)

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


# ---------- Reveal ----------

async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает результаты анализа и рекомендует персонажа."""
    language = context.user_data.get("fe_language", "English")
    dialogue = context.user_data.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    # Полный анализ через AI
    result = await asyncio.to_thread(ai.analyze_first_encounter, user_responses, language)

    # ===== СОХРАНЯЕМ ВСЁ В КОНТЕКСТ =====
    context.user_data["level"] = result["estimated_level"]
    context.user_data["personality"] = result["recommended_personality"]
    context.user_data["language"] = language
    context.user_data["user_interests"] = result.get("interests", [])
    context.user_data["strength_skills"] = result.get("strength_skills", [])
    context.user_data["weakness_skills"] = result.get("weakness_skills", [])

    # Логируем для отладки
    logger.info(f"🎯 ARENA рекомендовала: {result['recommended_personality']}")
    logger.info(f"   Уровень: {result['estimated_level']}")
    logger.info(f"   Интересы: {result.get('interests', [])}")
    logger.info(f"   Слабые стороны: {result.get('weakness_skills', [])}")

    # Генерируем миссию
    topic = result.get("interests", ["интересная тема"])[0]
    personality = result["recommended_personality"]
    level = result["estimated_level"]

    mission = await asyncio.to_thread(
        ai.generate_mission,
        personality,
        topic,
        level,
        language,
        result.get("interests", []),
        result.get("strength_skills", []),
        result.get("weakness_skills", [])
    )

    # Генерируем слова для миссии (с учётом уровня)
    # Генерируем слова для миссии
    case_topic = await asyncio.to_thread(ai.generate_case_topic, personality, level, language,
    result.get("interests", []))
    mission_words = ai.generate_mission_words_from_case(case_topic, level)
    context.user_data["case_topic"] = case_topic
    context.user_data["mission_words"] = mission_words
    context.user_data["mission"] = mission
    context.user_data["topic"] = topic

    # Финальная реплика ARENA
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    closing = await asyncio.to_thread(
        ai.generate_arena_closing,
        user_responses,
        level,
        language,
        personality,
        result.get("interests", []),
        result.get("strength_skills", []),
        result.get("weakness_skills", [])
    )

    await update.message.reply_text(
        f"🏛️ {closing}",
        parse_mode="HTML"
    )

    # ===== ПОКАЗЫВАЕМ МИССИЮ С ПЕРСОНАЖЕМ =====
    # Формируем красивое отображение слов
    words_list = []
    for item in mission_words.split(","):
        if ":" in item:
            word, translation = item.split(":", 1)
            words_list.append({"word": word.strip(), "translation": translation.strip()})
        else:
            words_list.append({"word": item.strip(), "translation": ""})

    words_display = "\n".join([f"  • {w['word']} — {w['translation']}" for w in words_list])

    mission_display = (
        f"🎯 <b>ТВОЯ МИССИЯ</b>\n\n"
        f"<b>Персонаж:</b> {person['full_name']}\n"
        f"<b>Стиль:</b> {person['style']}\n\n"
        f"<b>Задача:</b>\n"
        f"{mission['challenge_description']}\n\n"
        f"<b>Ключевые слова для победы:</b>\n"
        f"{words_display}\n\n"
        f"💬 <i>«{person.get('phrase', 'Убеди меня.')}»</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ ПРИНЯТЬ ВЫЗОВ", callback_data="fe_enter_battle")]
    ])

    await update.message.reply_text(
        mission_display,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    _reset_fe_state(context)


# ---------- Battle ----------

async def enter_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[⚔️ ПРИНЯТЬ ВЫЗОВ] — начало битвы с Battle Card."""
    query = update.callback_query
    await query.answer()

    personality = context.user_data.get("personality", "hr_manager")
    language = context.user_data.get("language", "English")
    topic = context.user_data.get("topic", "интересную тему")
    level = context.user_data.get("level", "B1")

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    battle_card = await asyncio.to_thread(
        ai.generate_battle_card,
        personality,
        topic,
        level,
        language,
        context.user_data.get("user_interests", []),
        context.user_data.get("weakness_skills", [])
    )

    context.user_data["battle_card"] = battle_card
    context.user_data["battle_start_time"] = time.time()
    context.user_data["battle_status"] = "in_progress"

    objectives_text = "\n".join(f"  • {obj}" for obj in battle_card.get("objectives", []))

    battle_card_text = (
        f"⚔️ <b>BATTLE CARD</b>\n\n"
        f"🎭 <b>{battle_card['personality_full']}</b>\n\n"
        f"📋 <b>Миссия:</b>\n"
        f"{battle_card['mission']}\n\n"
        f"🎯 <b>Цели:</b>\n"
        f"{objectives_text}\n\n"
        f"🗡️ <b>Твоё оружие:</b>\n"
        f"{', '.join(battle_card['user_weapons'])}\n\n"
        f"🛡️ <b>Оружие {battle_card['personality_name']}:</b>\n"
        f"{battle_card['character_weapons']}\n\n"
        f"⏱️ <b>Время:</b> 15 минут\n\n"
        f"<b>Готов начать?</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ НАЧАТЬ БИТВУ", callback_data="fe_start_battle")]
    ])

    await query.edit_message_text(
        battle_card_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚔️ Начало битвы — первое сообщение персонажа."""
    query = update.callback_query
    await query.answer()

    personality = context.user_data.get("personality", "hr_manager")
    language = context.user_data.get("language", "English")
    topic = context.user_data.get("topic", "интересную тему")
    level = context.user_data.get("level", "B1")
    battle_card = context.user_data.get("battle_card", {})

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    voice = PERSONALITY_VOICE.get(personality, PERSONALITY_VOICE["devil_advocate"])

    # Первое сообщение персонажа
    opening_prompt = f"""
    Ты — {person['full_name']}. {person['desc']}

    Начинаешь битву на тему "{topic}".
    Твой стиль: {person['style']}
    Ты часто говоришь фразы вроде: {', '.join(voice.get('opening', ['Let\'s begin.'])[:2])}

    Сделай вызов или задай вопрос, который начнёт битву.
    1-2 предложения на языке {LANGUAGES.get(language, {}).get('name', language)}.
    """

    opening = await asyncio.to_thread(ai.ask_gpt, opening_prompt, 0.8, 150)
    if not opening:
        opening = f"Let's discuss {topic}. What's your perspective?"

    await query.edit_message_text(
        f"⚔️ <b>БИТВА НАЧАЛАСЬ!</b>\n\n"
        f"🎭 <b>{person['full_name']}:</b>\n"
        f"<i>{opening}</i>\n\n"
        f"💬 Напиши свой ответ!\n"
        f"⏱️ У тебя 15 минут.",
        parse_mode="HTML"
    )

    context.user_data["dialogue"] = []
    context.user_data["dialogue"].append({"speaker": "AI", "text": opening})
    context.user_data["awaiting_response"] = True
    context.user_data["turn"] = 0
    context.user_data["battle_start_time"] = time.time()
    context.user_data["mission_words"] = battle_card.get("user_weapons", [])


async def finish_battle(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str = "completed"):
    """🏁 Завершение битвы с Verdict."""
    dialogue = context.user_data.get("dialogue", [])
    battle_card = context.user_data.get("battle_card", {})

    # Проверяем выполнение условий
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text = " ".join(user_responses)

    result = await asyncio.to_thread(
        ai.check_battle_completion,
        dialogue,
        battle_card.get("objectives", []),
        battle_card.get("user_weapons", []),
        15,
        15
    )

    personality = battle_card.get("personality", "hr_manager")
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    # Генерируем Verdict от персонажа
    verdict_prompt = f"""
    Ты — {person['full_name']}. Ты только что завершил битву с пользователем.

    Вот что он говорил:
    {user_text[:1500]}

    Ты должен сказать ему короткий вердикт:
    1. Выполнил ли он миссию? (да/частично/нет)
    2. Что было сильно?
    3. Что можно улучшить?
    4. Одна фраза, которая останется в памяти

    Говори как персонаж — в своём стиле, без AI-терминологии.
    """

    verdict = await asyncio.to_thread(ai.ask_gpt, verdict_prompt, 0.7, 300)
    if not verdict:
        verdict = f"{person['name']}: 'I've heard enough. Here's my verdict.'"

    # Показываем Verdict
    await update.message.reply_text(
        f"🏁 <b>BATTLE COMPLETE</b>\n\n"
        f"🎭 <b>{person['full_name']}</b>\n\n"
        f"{verdict}\n\n"
        f"📊 <b>Результат:</b>\n"
        f"  • Цели: {len(result['objectives_completed'])}/{result['objectives_total']}\n"
        f"  • Оружие: {len(result['weapons_used'])}/{result['weapons_total']}\n",
        parse_mode="HTML"
    )

    # Кнопки
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 РЕМАТЧ", callback_data="battle_rematch")],
        [InlineKeyboardButton("🏛️ СЛЕДУЮЩАЯ ВСТРЕЧА", callback_data="battle_next")],
        [InlineKeyboardButton("💬 СВОБОДНЫЙ РАЗГОВОР", callback_data="battle_free_talk")]
    ])

    await update.message.reply_text(
        "Что хочешь делать дальше?",
        reply_markup=keyboard
    )

    context.user_data["battle_status"] = "completed"


# ---------- Обработка текстовых сообщений для First Encounter ----------

async def handle_fe_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений для First Encounter."""
    if context.user_data.get("fe_awaiting_response"):
        await handle_fe_response(update, context)