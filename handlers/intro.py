"""
handlers/intro.py — Храм (первое знакомство) и вход в бой следующего дня.

Правила:
  • Храм работает на learning_language (то, что человек реально выбрал практиковать).
  • Interface_language в этом файле НЕ используется — все интерфейсные строки
    берём через i18n.t(il, ...), где il — язык интерфейса пользователя.
  • Никаких оценок, очков, обратной связи во время Храма. 8 реплик — синтез.
  • Персонаж и тема назначаются ARENA, а не пользователем.
  • Админ может проходить Храм сколько угодно раз.
  • ARENA в Храме — верховная наблюдающая сила, НЕ персонаж и НЕ робот.
"""
import asyncio
import logging
import os
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
import i18n
import voice
from config import (
    FIRST_ENCOUNTER_MOVES,
    ISO_TO_LANG_KEY,
    SUPPORTED_LANGUAGES,
    LANGUAGE_DISPLAY,
    LANGUAGE_FLAGS,
    is_admin,
)
from game_data import PERSONALITIES, COMMUNICATION_SKILLS
from handlers import start
from handlers.ui import send_or_edit, esc

logger = logging.getLogger(__name__)

FE_STATE_KEYS = ["fe_language", "fe_dialogue", "fe_awaiting_response"]
FALLBACK_TOPIC = "a topic you care about"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _reset_fe_state(context: ContextTypes.DEFAULT_TYPE):
    for key in FE_STATE_KEYS:
        context.user_data.pop(key, None)


def _read_photo(path: str | None) -> bytes | None:
    if not path:
        return None
    for candidate in (path, os.path.join(_ROOT, path)):
        if os.path.isfile(candidate):
            with open(candidate, "rb") as f:
                return f.read()
    return None


def _lang_key(iso: str) -> str:
    """en → english. Нужен для промптов GPT."""
    return ISO_TO_LANG_KEY.get(iso, "english")


# ==================================================================
# ВХОД В ХРАМ
# ==================================================================

async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Вход в Храм.
    Новичок — выбор learning_language и 8 реплик.
    Прошёл Храм и не админ — короткое сообщение и меню.
    Админ — всегда может пройти заново.
    """
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    if db.has_completed_temple(user_id) and not is_admin(user_id):
        text = i18n.t(il, "TEMPLE.ALREADY_DONE")
        await send_or_edit(update, text, reply_markup=start._menu_keyboard(user_id, il))
        return

    _reset_fe_state(context)

    rows = []
    for iso in SUPPORTED_LANGUAGES:
        flag = LANGUAGE_FLAGS.get(iso, "")
        name = LANGUAGE_DISPLAY.get(iso, iso)
        label = f"{flag} {name}".strip()
        rows.append([InlineKeyboardButton(label, callback_data=f"fe_lang_{iso}")])
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")])

    text = (
        f"🏛 <b>{esc(i18n.t(il, 'TEMPLE.LISTENING'))}</b>\n\n"
        f"{esc(i18n.t(il, 'TEMPLE.SELECT_LEARNING_LANGUAGE'))}"
    )
    await send_or_edit(update, text,
                       reply_markup=InlineKeyboardMarkup(rows),
                       parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Выбор learning_language.
    С этого момента и до конца Храма все реплики Арены — на выбранном языке.
    Interface_language остаётся неизменным.
    """
    query = update.callback_query
    await query.answer()
    iso = query.data.replace("fe_lang_", "")
    if iso not in SUPPORTED_LANGUAGES:
        return

    user_id = update.effective_user.id
    db.set_learning_language(user_id, iso)

    context.user_data["fe_language"] = iso
    context.user_data["fe_dialogue"] = []
    context.user_data["fe_awaiting_response"] = True

    il = db.get_interface_language(user_id)
    text = (
        f"🏛 <b>{esc(i18n.t(il, 'TEMPLE.LISTENING'))}</b>\n\n"
        f"{esc(i18n.t(il, 'TEMPLE.SAY_ANYTHING'))}\n\n"
        f"<b>{esc(i18n.t(il, 'TEMPLE.I_WILL_FIGURE_YOU_OUT'))}</b>"
    )
    await query.edit_message_text(text, parse_mode="HTML")


# ==================================================================
# 8 РЕПЛИК ХРАМА
# ==================================================================

async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Один ход Храма. Никаких оценок, очков, шкал — только живая реакция."""
    user_text = await voice.get_pending_text(update, context)
    if not user_text:
        return

    ud = context.user_data
    dialogue = ud.setdefault("fe_dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    ud["fe_awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")
    if user_turns >= FIRST_ENCOUNTER_MOVES:
        await _reveal(update, context)
        return

    language_iso = ud.get("fe_language") or db.get_learning_language(update.effective_user.id)
    language = _lang_key(language_iso)
    history = "\n".join(
        f"{'User' if d['speaker'] == 'User' else 'ARENA'}: {d['text']}" for d in dialogue
    )

    chat_action = "record_voice" if ud.get("last_input_was_voice") else "typing"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=chat_action)
    except Exception:
        pass

    reaction = await asyncio.to_thread(
        ai.generate_arena_reaction, history, user_text, language, user_turns + 1
    )
    if "fe_dialogue" not in ud:
        return
    if not reaction:
        reaction = "…"

    dialogue.append({"speaker": "AI", "text": reaction})
    ud["fe_awaiting_response"] = True

    await voice.maybe_reply_voice(update, context, reaction, "_temple")
    await update.message.reply_text(reaction)


# ==================================================================
# СИНТЕЗ ПОСЛЕ ХРАМА
# ==================================================================

async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Конец Храма.
    ARENA:
      • делает разбор по 10 критериям (языковому и коммуникационному);
      • определяет один конкретный паттерн поведения;
      • выбирает персонажа, тему и миссию;
      • сохраняет всё это, а не «случайный вердикт».
    """
    ud = context.user_data
    user = update.effective_user
    user_id = user.id
    il = db.get_interface_language(user_id)
    language_iso = ud.get("fe_language") or db.get_learning_language(user_id)
    language = _lang_key(language_iso)

    dialogue = ud.get("fe_dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    try:
        await update.message.reply_text(f"🏛 {esc(i18n.t(il, 'TEMPLE.THINKING'))}")
    except Exception:
        pass

    analysis = await asyncio.to_thread(
        ai.analyze_first_encounter, user_responses, language
    )

    level = analysis["estimated_level"]
    personality = analysis["recommended_personality"]
    topic = analysis["main_topic"] or FALLBACK_TOPIC
    weakest = analysis["weakest_skill"]
    pattern = analysis.get("pattern", "")
    pattern_evidence = analysis.get("pattern_evidence", [])

    arena_analysis = {
        "language": analysis["language"],
        "grammar_weak_areas": analysis["grammar_weak_areas"],
        "vocabulary_weak_areas": analysis["vocabulary_weak_areas"],
        "communication": analysis["communication"],
        "hidden": analysis["hidden"],
        "behaviour": analysis["behaviour"],
        "weakest_skill": weakest,
        "strongest_skill": analysis["strongest_skill"],
        "arena_rank": analysis["arena_rank"],
        "interests": analysis["interests"],
        "main_topic": topic,
        "estimated_level": level,
        "recommended_personality": personality,
        "pattern": pattern,
        "pattern_evidence": pattern_evidence,
    }

    ud.update({
        "level": level,
        "personality": personality,
        "language": language,
        "language_iso": language_iso,
        "topic": topic,
        "arena_analysis": arena_analysis,
    })

    db.get_or_create_user(user_id, user.username, user.first_name)
    db.set_learning_language(user_id, language_iso)
    db.save_arena_analysis(user_id, arena_analysis)
    db.update_criteria(user_id, {**analysis["language"], **analysis["communication"]}, weight=1.0)
    db.add_level_snapshot(user_id, level, source="arena_reveal")
    db.add_interests(user_id, analysis["interests"] or [topic])
    db.set_push_profile(user_id, personality, analysis["interests"] or [topic])
    db.set_nemesis(user_id, analysis["behaviour"])
    db.set_user_behaviour_title(
        user_id, analysis["behaviour"], gamification.get_title(analysis["behaviour"], 1)
    )
    db.mark_temple_done(user_id)

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    observation, pitch = await asyncio.gather(
        asyncio.to_thread(
            ai.generate_arena_observation,
            user.first_name or "", user_responses, language, level,
            topic, personality, weakest, pattern,
        ),
        asyncio.to_thread(
            ai.generate_character_pitch,
            personality, topic, language, level, user.first_name or "", weakest,
        ),
    )

    parts = [
        f"🏛 <b>{esc(i18n.t(il, 'TEMPLE.HEARD_ENOUGH'))}</b>",
        esc(observation),
        f"🎭 <b>{esc(person['name'])}</b> — <i>{esc(person['role'])}</i>",
        esc(pitch),
        f"<i>«{esc(person['phrase'])}»</i>",
    ]
    text = "\n\n".join(p for p in parts if p)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "TEMPLE.ENTER_BATTLE"),
                              callback_data="fe_start_battle")]
    ])

    photo = _read_photo(person.get("photo"))
    if photo:
        try:
            await update.message.reply_photo(photo=photo, caption=f"🎭 {person['name']}")
        except Exception:
            logger.warning("Не удалось отправить фото персонажа %s", personality)

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    _reset_fe_state(context)


# ==================================================================
# БОЙ СЛЕДУЮЩЕГО ДНЯ
# ==================================================================

async def daily_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Бой следующего дня. Храм заново НЕ проходят.
    Персонаж подбирается по текущему слабому коммуникационному скиллу.
    Тема — из интересов (или из последнего пуша).
    Язык и уровень — из БД.
    """
    user = update.effective_user
    user_id = user.id
    il = db.get_interface_language(user_id)

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    if db.has_battled_today(user_id) and not is_admin(user_id):
        hours = int(db.cooldown_hours_left(user_id)) + 1
        text = i18n.t(il, "BATTLE.COOLDOWN", hours=hours)
        await send_or_edit(update, text, reply_markup=start._menu_keyboard(user_id, il))
        return

    analysis = db.get_latest_arena_analysis(user_id) or {}
    criteria = db.get_criteria(user_id)
    communication = {k: v for k, v in criteria.items() if k in COMMUNICATION_SKILLS}
    if communication:
        weakest = min(communication, key=communication.get)
        from game_data import SKILL_TO_PERSONALITY
        personality = SKILL_TO_PERSONALITY.get(weakest, analysis.get("recommended_personality", "hr_manager"))
    else:
        personality = analysis.get("recommended_personality", "hr_manager")

    interests = db.get_interests(user_id) or ([analysis["main_topic"]] if analysis.get("main_topic") else [])
    pushed = db.pop_push_topic(user_id)
    if pushed:
        topic = pushed
    else:
        recent = {t.lower() for t in db.get_recent_battle_topics(user_id, n=3)}
        fresh_pool = [t for t in interests if t.lower() not in recent]
        pool = fresh_pool or interests or [FALLBACK_TOPIC]
        topic = random.choice(pool)

    level = db.get_current_level(user_id) or analysis.get("estimated_level") or "B1"
    language_iso = db.get_learning_language(user_id)
    language = _lang_key(language_iso)

    context.user_data.update({
        "level": level,
        "language": language,
        "language_iso": language_iso,
        "topic": topic,
        "personality": personality,
        "arena_analysis": analysis,
    })

    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    msg = await send_or_edit(update, f"🎭 {esc(i18n.t(il, 'TEMPLE.THINKING'))}")
    weakest_skill = communication and min(communication, key=communication.get) or ""
    pitch = await asyncio.to_thread(
        ai.generate_character_pitch, personality, topic, language, level,
        user.first_name or "", weakest_skill,
    )

    text = "\n\n".join(p for p in [
        f"🏛 {esc(i18n.t(il, 'TEMPLE.HEARD_ENOUGH'))}",
        f"🎭 <b>{esc(person['full_name'])}</b>\n<i>{esc(person['role'])}</i>",
        esc(pitch),
        f"<i>«{esc(person['phrase'])}»</i>",
    ] if p)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "TEMPLE.ENTER_BATTLE"),
                              callback_data="fe_start_battle")]
    ])

    try:
        await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await context.bot.send_message(update.effective_chat.id, text,
                                       reply_markup=keyboard, parse_mode="HTML")