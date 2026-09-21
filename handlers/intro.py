import asyncio
import logging
import os
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
import voice
from config import FIRST_ENCOUNTER_MOVES, is_admin
from game_data import LANGUAGES, PERSONALITIES, ARENA_UI_STRINGS, COMMUNICATION_SKILLS
from handlers import start
from handlers.ui import esc, send_or_edit

logger = logging.getLogger(__name__)

FE_STATE_KEYS = ["fe_language", "fe_dialogue", "fe_awaiting_response"]
FALLBACK_TOPIC = "a topic you care about"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reset_fe_state(context: ContextTypes.DEFAULT_TYPE):
    for key in FE_STATE_KEYS:
        context.user_data.pop(key, None)


def _ui(language: str) -> dict:
    return ARENA_UI_STRINGS.get(language) or ARENA_UI_STRINGS["english"]


def cooldown_message(user_id: int) -> str:
    hours = int(db.cooldown_hours_left(user_id)) + 1
    return (
        f"⚔️ Следующий бой будет через ~{hours} ч.\n"
        f"Арена даёт время всё обдумать. А пока можно просто поговорить."
    )


def _read_photo(path: str | None) -> bytes | None:
    if not path:
        return None
    for candidate in (path, os.path.join(_ROOT, path)):
        if os.path.isfile(candidate):
            with open(candidate, "rb") as f:
                return f.read()
    return None


# ------------------------------------------------------------------
# ХРАМ: язык → 8 реплик → «я услышала достаточно» → персонаж
# ------------------------------------------------------------------

async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход в Храм. Первый раз — выбор языка + 8 реплик. Админ может проходить сколько угодно раз."""
    user_id = update.effective_user.id
    if db.has_completed_temple(user_id) and not is_admin(user_id):
        text = (
            "🏛️ Ты уже прошёл знакомство с Храмом — второй раз оно не нужно.\n"
            "Дальше Арена сама решает, когда пришло время для боя."
        )
        await send_or_edit(update, text, reply_markup=start.post_battle_keyboard())
        return

    _reset_fe_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"fe_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    await send_or_edit(update, "🏛️ <b>ARENA</b>\n\nВыбери язык.",
                       reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """После выбора языка — СРАЗУ начинаем слушать. Уровень не спрашиваем."""
    query = update.callback_query
    await query.answer()
    language = query.data.replace("fe_lang_", "")
    if language not in LANGUAGES:
        return
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    db.set_user_language(user.id, language)

    context.user_data["fe_language"] = language
    context.user_data["fe_dialogue"] = []
    context.user_data["fe_awaiting_response"] = True

    ui = _ui(language)
    await query.edit_message_text(
        f"🏛️ <b>{esc(ui['listening'])}</b>\n\n"
        f"<b>{esc(ui['your_move'])}</b>\n\n"
        f"<i>{esc(ui['listen_hint'])}</i>",
        parse_mode="HTML",
    )


async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = await voice.get_pending_text(update, context)
    if len(user_text) < 1:
        return

    ud = context.user_data
    dialogue = ud.setdefault("fe_dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    ud["fe_awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")
    if user_turns >= FIRST_ENCOUNTER_MOVES:
        await _reveal(update, context)
        return

    language = ud.get("fe_language") or "english"
    history = "\n".join(f"{'User' if d['speaker'] == 'User' else 'ARENA'}: {d['text']}" for d in dialogue)

    chat_action = "record_voice" if ud.get("last_input_was_voice") else "typing"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=chat_action)
    except Exception:
        pass

    reaction = await asyncio.to_thread(ai.generate_arena_reaction, history, user_text, language, user_turns + 1)
    reaction = reaction or _ui(language)["go_on"]
    if "fe_dialogue" not in ud:  # /stop во время ожидания ответа GPT
        return
    dialogue.append({"speaker": "AI", "text": reaction})
    ud["fe_awaiting_response"] = True

    await voice.maybe_reply_voice(update, context, reaction, "_temple")
    await update.message.reply_text(reaction)


async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Конец Храма. ARENA сама назначает уровень, персонажа и тему, сохраняет разбор по 10 критериям
    и запоминает интересы — на них потом строятся бои, free talk и пуши.
    """
    ud = context.user_data
    user = update.effective_user
    user_id = user.id
    language = ud.get("fe_language") or db.get_user_language(user_id) or "english"
    ui = _ui(language)
    dialogue = ud.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    try:
        await update.message.reply_text(f"🏛️ {ui['thinking']}")
    except Exception:
        pass

    result = await asyncio.to_thread(ai.analyze_first_encounter, user_responses, language)

    level = result["estimated_level"]
    personality = result["recommended_personality"]
    topic = result["main_topic"] or FALLBACK_TOPIC
    weakest = result["weakest_skill"]

    arena_analysis = {
        "language": result["language"],
        "grammar_weak_areas": result["grammar_weak_areas"],
        "vocabulary_weak_areas": result["vocabulary_weak_areas"],
        "communication": result["communication"],
        "hidden": result["hidden"],
        "behaviour": result["behaviour"],
        "weakest_skill": weakest,
        "strongest_skill": result["strongest_skill"],
        "arena_rank": result["arena_rank"],
        "interests": result["interests"],
        "main_topic": topic,
        "estimated_level": level,
        "recommended_personality": personality,
    }

    ud.update({
        "level": level, "personality": personality, "language": language,
        "topic": topic, "arena_analysis": arena_analysis,
    })

    db.get_or_create_user(user_id, user.username, user.first_name)
    db.set_user_language(user_id, language)
    db.init_user_skills(user_id)
    db.save_arena_analysis(user_id, arena_analysis)
    db.update_criteria(user_id, {**result["language"], **result["communication"]}, weight=1.0)
    db.add_level_snapshot(user_id, level, source="arena_reveal")

    quest = gamification.generate_quest(result)
    db.set_quest(user_id, quest["type"], quest["description"], quest["target"], quest["skill_bonus"])
    db.set_nemesis(user_id, result["behaviour"])
    db.set_user_behaviour_title(user_id, result["behaviour"], gamification.get_title(result["behaviour"], 1))
    db.set_push_profile(user_id, personality, result["interests"] or [topic])
    db.mark_temple_done(user_id)

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    observation, pitch = await asyncio.gather(
        asyncio.to_thread(ai.generate_arena_observation, user.first_name or "", user_responses,
                          language, level, topic, personality, weakest),
        asyncio.to_thread(ai.generate_character_pitch, personality, topic, language, level,
                          user.first_name or "", weakest),
    )

    parts = [
        f"🏛️ <b>{esc(ui['heard_enough'])}</b>",
        esc(observation),
        f"🎭 <b>{esc(person['name'])}</b> — <i>{esc(person['role'])}</i>",
        esc(pitch),
        f"<i>«{esc(person['phrase'])}»</i>",
    ]
    text = "\n\n".join(p for p in parts if p)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ {ui['enter_battle']} →", callback_data="fe_start_battle")]
    ])

    photo = _read_photo(person.get("photo"))
    if photo:
        try:
            await update.message.reply_photo(photo=photo, caption=f"🎭 {person['name']}")
        except Exception:
            logger.warning("Не удалось отправить фото персонажа %s", personality)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

    _reset_fe_state(context)


# ------------------------------------------------------------------
# БОЙ СЛЕДУЮЩЕГО ДНЯ: питч персонажа → кнопка → arena.start_battle
# ------------------------------------------------------------------

async def daily_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Храм заново НЕ проходят. Персонаж подбирается под ТЕКУЩИЙ слабый скилл (шкала из БД),
    каждый 4-й бой — немезида. Тема — из интересов (или из сегодняшнего пуша).
    Уровень и язык — из БД.
    """
    user = update.effective_user
    user_id = user.id
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    if db.has_battled_today(user_id) and not is_admin(user_id):
        await send_or_edit(update, cooldown_message(user_id), reply_markup=start.post_battle_keyboard())
        return

    gamification.ensure_quest(user_id)
    analysis = db.get_latest_arena_analysis(user_id) or {}
    personality = gamification.pick_next_personality(user_id)
    interests = db.get_interests(user_id) or ([analysis["main_topic"]] if analysis.get("main_topic") else [])
    topic = db.pop_push_topic(user_id) or (random.choice(interests) if interests else FALLBACK_TOPIC)
    level = db.get_current_level(user_id) or analysis.get("estimated_level") or "B1"
    language = db.get_user_language(user_id) or "english"
    ui = _ui(language)

    context.user_data.update({
        "level": level, "language": language, "topic": topic,
        "personality": personality, "arena_analysis": analysis,
    })
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    msg = await send_or_edit(update, f"🎭 {ui['thinking']}")
    weakest = gamification.weakest_criterion(db.get_criteria(user_id), COMMUNICATION_SKILLS) or ""
    pitch = await asyncio.to_thread(ai.generate_character_pitch, personality, topic, language, level,
                                    user.first_name or "", weakest)

    text = "\n\n".join(p for p in [
        f"🏛️ {esc(ui['arena_returns'])}",
        f"🎭 <b>{esc(person['full_name'])}</b>\n<i>{esc(person['role'])}</i>",
        esc(pitch),
        f"<i>«{esc(person['phrase'])}»</i>",
    ] if p)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ {ui['enter_battle']}", callback_data="fe_start_battle")]
    ])
    try:
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(update.effective_chat.id, text, reply_markup=keyboard, parse_mode="HTML")