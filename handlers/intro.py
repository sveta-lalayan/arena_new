"""
handlers/intro.py — Храм (первое знакомство) и вход в бой следующего дня.
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
import personalization
import voice
from config import (
    FIRST_ENCOUNTER_MOVES,
    ISO_TO_LANG_KEY,
    SUPPORTED_LANGUAGES,
    LANGUAGE_DISPLAY,
    LANGUAGE_FLAGS,
    is_admin,
)
from game_data import PERSONALITIES, COMMUNICATION_SKILLS, SKILL_TO_PERSONALITY
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
    return ISO_TO_LANG_KEY.get(iso, "english")


async def enter_arena_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    if db.has_completed_temple(user_id) and not is_admin(user_id):
        text = i18n.t(il, "TEMPLE.ALREADY_DONE")
        await send_or_edit(update, text, reply_markup=start._menu_keyboard(user_id, il))
        return

    _reset_fe_state(context)

    rows = []
    for iso in SUPPORTED_LANGUAGES:
        label = f"{LANGUAGE_FLAGS.get(iso, '')} {LANGUAGE_DISPLAY.get(iso, iso)}".strip()
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
        f"{esc(i18n.t(il, 'TEMPLE.INTRO'))}"
    )
    await query.edit_message_text(text, parse_mode="HTML")


async def handle_fe_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        ai.generate_arena_reaction, history, user_text, language, user_turns
    )
    if "fe_dialogue" not in ud:
        return

    if not reaction:
        logger.warning("generate_arena_reaction вернул пусто — показываю fallback")
        il = db.get_interface_language(update.effective_user.id)
        reaction = i18n.t(il, "ERROR.AI_UNAVAILABLE")

    dialogue.append({"speaker": "AI", "text": reaction})
    ud["fe_awaiting_response"] = True

    await voice.maybe_reply_voice(update, context, reaction, "_temple")
    await update.message.reply_text(reaction)


async def _reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "claim": analysis.get("claim", ""),
    }

    ud.update({
        "level": level,
        "personality": personality,
        "language": language,
        "language_iso": language_iso,
        "topic": topic,
        "arena_analysis": arena_analysis,
        "opening_claim": arena_analysis["claim"],
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
    observation = await asyncio.to_thread(
        ai.generate_arena_observation,
        user.first_name or "", user_responses, language, level,
        topic, personality, weakest, pattern,
    )

    text = (
        f"🏛 <b>{esc(i18n.t(il, 'TEMPLE.HEARD_ENOUGH'))}</b>\n\n"
        f"<i>{esc(observation)}</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "TEMPLE.ENTER_BATTLE"),
                              callback_data="fe_start_battle")]
    ])

    photo = _read_photo(person.get("photo"))
    if photo:
        try:
            await update.message.reply_photo(photo=photo)
        except Exception:
            logger.warning("Не удалось отправить фото персонажа %s", personality)

    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

    try:
        await asyncio.to_thread(personalization.record_session, user_id, "temple", user_responses, language)
    except Exception:
        logger.exception("personalization.record_session(temple) упал")

    try:
        ev = await asyncio.to_thread(
            ai.extract_evidence, user_responses, "temple", language, [], [],
            user.first_name or "",
        )
        for item in ev:
            db.add_evidence(
                user_id, "temple", item["text_excerpt"],
                item.get("detected", ""), item.get("interpretation", ""),
                item.get("confidence", 0.5),
            )
    except Exception:
        logger.exception("extract_evidence(temple) упал")

    _reset_fe_state(context)


def _pick_personality_for_today(user_id: int, analysis: dict) -> str:
    """
    Персонаж следующего боя:
      0. Первый бой после Храма — не залипаем на hr_manager.
      1. Немезида (если настал её черёд и не побеждена).
      2. Подтверждённый growth-паттерн → SKILL_TO_PERSONALITY.
      3. Самый слабый communication-критерий → SKILL_TO_PERSONALITY.
      4. Fallback: recommended_personality из Храма.
    Антиповтор: не даём того же персонажа два дня подряд (кроме немезиды).
    """
    last = db.get_last_personality(user_id)
    battles_played = db.count_battles(user_id)

    if battles_played == 0:
        analysis_pers = analysis.get("recommended_personality", "")
        weakest = analysis.get("weakest_skill", "")
        alt = SKILL_TO_PERSONALITY.get(weakest, "") if weakest else ""
        if analysis_pers and analysis_pers != "hr_manager":
            return analysis_pers
        if alt and alt != "hr_manager":
            return alt
        if analysis_pers:
            return analysis_pers

    nemesis = db.get_nemesis(user_id)
    if nemesis and not nemesis["defeated"] and battles_played > 0 and battles_played % 4 == 3:
        if nemesis["personality"] != last:
            return nemesis["personality"]

    patterns = db.get_patterns(user_id, ("confirmed", "improving"))
    growth = [p for p in patterns if p["kind"] == "growth"]
    if growth:
        cat = growth[0]["category"]
        if cat in SKILL_TO_PERSONALITY:
            chosen = SKILL_TO_PERSONALITY[cat]
            if chosen != last:
                return chosen

    criteria = db.get_criteria(user_id)
    communication = {k: v for k, v in criteria.items() if k in COMMUNICATION_SKILLS}
    if communication:
        ranked = sorted(communication, key=communication.get)
        for weakest in ranked:
            candidate = SKILL_TO_PERSONALITY.get(weakest)
            if candidate and candidate != last:
                return candidate
        return SKILL_TO_PERSONALITY.get(ranked[0], analysis.get("recommended_personality", "hr_manager"))

    fallback = analysis.get("recommended_personality", "hr_manager")
    if fallback == last:
        return "journalist"
    return fallback


async def daily_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обёртка с защитой от двойного нажатия: пока первый запуск ещё готовит
    питч (несколько секунд ждёт AI), повторные нажатия игнорируются.
    Иначе приходили два сообщения с темой (часто с разными темами).
    """
    ud = context.user_data
    if ud.get("_daily_battle_busy"):
        if update.callback_query:
            try:
                await update.callback_query.answer()
            except Exception:
                pass
        return
    ud["_daily_battle_busy"] = True
    try:
        await _daily_battle_impl(update, context)
    finally:
        ud.pop("_daily_battle_busy", None)


async def _daily_battle_impl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    il = db.get_interface_language(user_id)

    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        data = update.callback_query.data or ""
        if data.startswith("daily_battle:"):
            try:
                db.mark_notification_clicked(int(data.split(":", 1)[1]), user_id)
            except (ValueError, Exception):
                logger.debug("не удалось отметить клик по напоминанию: %s", data)

    if db.has_battled_today(user_id) and not is_admin(user_id):
        hours = int(db.cooldown_hours_left(user_id)) + 1
        text = i18n.t(il, "BATTLE.COOLDOWN", hours=hours)
        await send_or_edit(update, text, reply_markup=start._menu_keyboard(user_id, il))
        return

    analysis = db.get_latest_arena_analysis(user_id) or {}
    personality = _pick_personality_for_today(user_id, analysis)

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
    weakest_skill = (db.get_latest_arena_analysis(user_id) or {}).get("weakest_skill", "")
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

    edited = False
    if msg is not None and hasattr(msg, "edit_text"):
        try:
            await msg.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            edited = True
        except Exception:
            logger.debug("edit_text питча не удался, отправляю заново", exc_info=True)
    if not edited:
        if msg is not None and hasattr(msg, "delete"):
            try:
                await msg.delete()      # убираем висящее «thinking…»
            except Exception:
                pass
        await context.bot.send_message(update.effective_chat.id, text,
                                       reply_markup=keyboard, parse_mode="HTML")