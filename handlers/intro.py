"""
Вступительный диалог с гидом Alex.

Флоу (по ТЗ):
CHOOSE LANGUAGE → CHOOSE LEVEL → MEET INTRO CHARACTER → 6 коротких
раундов живого разговора → "Окей, кажется, я тебя раскусил" → первое
впечатление → наблюдения → зона роста → рекомендация ОДНОГО из
существующих персонажей → [ПОЗНАКОМИТЬСЯ] → обычный flow этого персонажа.

Важно: диагностика полностью скрыта от пользователя (никаких слов
"тест"/"оценка"/"ошибки"), персонажи не создаются заново и не меняются —
только выбираются из уже существующих (см. game_data.PERSONALITIES).
Это ДОБАВОЧНЫЙ модуль, обычный поток "Играть" (handlers/arena.py) не трогает.
"""
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
from config import INTRO_ROUNDS
from game_data import LANGUAGES, LEVELS, GUIDE_PERSONALITY, PERSONALITIES
import logging
logger = logging.getLogger(__name__)

INTRO_STATE_KEYS = ["intro_language", "intro_level", "intro_dialogue", "intro_awaiting_response"]


def _reset_intro_state(context: ContextTypes.DEFAULT_TYPE):
    for key in INTRO_STATE_KEYS:
        context.user_data.pop(key, None)


# ---------- Язык → уровень → старт разговора ----------

async def intro_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Точка входа во вступительный диалог — команда /guide или кнопка в меню."""
    _reset_intro_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"intro_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    text = (
        f"🧭 <b>{GUIDE_PERSONALITY['name']}</b>\n\n"
        f"<i>{GUIDE_PERSONALITY['desc']}</i>\n\n"
        "На каком языке пообщаемся?"
    )
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.replace("intro_lang_", "")
    context.user_data["intro_language"] = language

    keyboard = [[InlineKeyboardButton(lvl, callback_data=f"intro_level_{lvl}")] for lvl in LEVELS]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_intro")])

    await query.edit_message_text(
        "📊 <b>Какой у тебя уровень?</b>\n\n"
        "<i>Подберу вопросы под него — простые факты для начала или "
        "неоднозначные сценарии для продвинутого уровня.</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.replace("intro_level_", "")
    context.user_data["intro_level"] = level
    context.user_data["intro_dialogue"] = []
    context.user_data["intro_awaiting_response"] = True

    await query.edit_message_text(f"🧭 {GUIDE_PERSONALITY['name']} печатает...")

    language = context.user_data.get("intro_language", "english")
    opening = await asyncio.to_thread(ai.generate_guide_opening, language, level)
    context.user_data["intro_dialogue"].append({"speaker": "AI", "text": opening})

    await query.message.reply_text(f"<i>{opening}</i>", parse_mode="HTML")


# ---------- 6 раундов живого разговора ----------

async def handle_intro_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if len(user_text) < 1:
        return

    dialogue = context.user_data.setdefault("intro_dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    context.user_data["intro_awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")

    if user_turns >= INTRO_ROUNDS:
        await _reveal(update, context)
        return

    language = context.user_data.get("intro_language", "english")
    level = context.user_data.get("intro_level", "B1")
    history = "\n".join(f"{'Ты' if d['speaker'] == 'User' else 'Alex'}: {d['text']}" for d in dialogue)

    reply = await asyncio.to_thread(
        ai.generate_guide_response, history, user_text, language, level, user_turns + 1
    )
    dialogue.append({"speaker": "AI", "text": reply})
    context.user_data["intro_awaiting_response"] = True

    await update.message.reply_text(f"<i>{reply}</i>", parse_mode="HTML")
    if not context.user_data.get("intro_awaiting_response", False):
        # Если не в диалоге с гидом — просто игнорируем или перенаправляем
        return


# ---------- Wow-момент: впечатление → наблюдения → рекомендация ----------

async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.user_data.get("intro_language", "english")
    level = context.user_data.get("intro_level", "B1")
    dialogue = context.user_data.get("intro_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    # Реплика-крючок — сразу, без долгой паузы на "думаю"
    await update.message.reply_text("Окей. Кажется, я тебя немного раскусил. 👀")

    result = await asyncio.to_thread(ai.analyze_intro_conversation, user_responses, language, level)

    observations_text = "\n".join(f"• {obs}" for obs in result["observations"])
    impression_text = (
        "🔎 <b>МОЁ ПЕРВОЕ ВПЕЧАТЛЕНИЕ</b>\n\n"
        f"«{result['impression']}»\n\n"
        "Почему я так думаю?\n"
        f"{observations_text}\n\n"
        "Но есть одна вещь, которую я бы прокачал.\n"
        f"«{result['growth']}»"
    )
    await update.message.reply_text(impression_text, parse_mode="HTML")

    recommended_key = result["recommended_personality"]
    recommended = PERSONALITIES.get(recommended_key, PERSONALITIES["hr_manager"])
    context.user_data["intro_recommended_personality"] = recommended_key

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🤝 ПОЗНАКОМИТЬСЯ", callback_data="intro_meet_character")]])
    recommendation_text = (
        f"Кажется, тебе стоит познакомиться с {recommended['name']}.\n\n"
        f"<i>Почему: {result['reasoning']}</i>"
    )
    await update.message.reply_text(recommendation_text, reply_markup=keyboard, parse_mode="HTML")

    # Язык/уровень/персонаж передаём в обычный flow арены как есть, без
    # изменения его промптов, характера или механики
    context.user_data["language"] = language
    context.user_data["level"] = level
    context.user_data["personality"] = recommended_key
    for key in ("intro_dialogue", "intro_awaiting_response"):
        context.user_data.pop(key, None)


async def meet_character(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """[ПОЗНАКОМИТЬСЯ] — переход в обычный, ничем не изменённый flow
    существующего персонажа. Язык и уровень уже выбраны, остаётся тема."""
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_topic"] = True

    await query.edit_message_text(
        "✏️ <b>Напиши любую тему</b>, которую хочешь обсудить.",
        parse_mode="HTML",
    )