"""
handlers/arena.py — бой, дебрифинг, свободный разговор, арсенал.

Принципы:
  • Бой — детерминированный. Таймер и старт/стоп — в bot.py.
  • В бою НЕТ обратной связи.
  • Debrief — расследование одного разговора.
    Форма (single_insight / focused / full) выбирается LLM.
    Дополнительно LLM возвращает arena_file_update (Living My Arena) и grammar_used
    (использование grammar-фразы из арсенала).
  • Free Talk — отдельный режим.
"""
import asyncio
import logging
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
    BATTLE_DURATION_MINUTES,
    BATTLE_MAX_ROUNDS,
    BATTLE_COOLDOWN_HOURS,
    CONVICTION_START,
    CONVICTION_WIN_THRESHOLD,
    ISO_TO_LANG_KEY,
    SUPPORTED_LANGUAGES,
    LANGUAGE_DISPLAY,
    LANGUAGE_FLAGS,
    CHANNEL_URL,
    is_admin,
)
from game_data import (
    PERSONALITIES, PERSONALITY_TO_SKILL, COMMUNICATION_SKILLS, ARSENAL_TOOL_EMOJI,
)
from handlers import intro, start
from handlers.ui import send_or_edit, esc

logger = logging.getLogger(__name__)

STATE_KEYS = [
    "language", "language_iso", "level", "topic", "personality",
    "mission_weapons", "mission_tip", "win_condition", "mission",
    "used_weapons", "dialogue", "turn", "awaiting_response", "battle_type",
    "arena_analysis", "conviction", "early_win", "last_input_was_voice",
    "_freetalk_personality", "awaiting_freetalk_topic",
]


def _reset_state(ud: dict):
    for key in STATE_KEYS:
        ud.pop(key, None)


def _lang_key(iso: str) -> str:
    return ISO_TO_LANG_KEY.get(iso, "english")


def _lang_iso(ud: dict, user_id: int) -> str:
    return ud.get("language_iso") or db.get_learning_language(user_id)


# ==================================================================
# ВХОД В БОЙ ИЗ МЕНЮ
# ==================================================================

async def play_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not db.has_completed_first_battle(user_id) and not is_admin(user_id):
        await intro.enter_arena_menu(update, context)
        return

    if db.has_battled_today(user_id) and not is_admin(user_id):
        il = db.get_interface_language(user_id)
        hours = int(db.cooldown_hours_left(user_id)) + 1
        text = i18n.t(il, "BATTLE.COOLDOWN", hours=hours)
        await send_or_edit(update, text, reply_markup=start._menu_keyboard(user_id, il))
        return

    await intro.daily_battle(update, context)


# ==================================================================
# НАЧАЛО БОЯ
# ==================================================================

async def start_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = user.id
    ud = context.user_data
    il = db.get_interface_language(user_id)

    language_iso = _lang_iso(ud, user_id)
    language = _lang_key(language_iso)
    level = ud.get("level") or db.get_current_level(user_id) or "B1"
    personality = ud.get("personality") or "devil_advocate"
    topic = ud.get("topic") or "a topic you care about"
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    analysis = ud.get("arena_analysis") or db.get_latest_arena_analysis(user_id) or {}

    mission, weapons_pack = await asyncio.gather(
        asyncio.to_thread(
            ai.generate_mission_task, topic, personality,
            user.first_name or "", language, level, analysis.get("pattern", ""),
        ),
        asyncio.to_thread(
            ai.generate_mission_weapons, topic, level, personality,
            language, analysis, analysis.get("weakest_skill"),
        ),
    )
    weapons, tip, win_condition = weapons_pack

    claim = ud.pop("opening_claim", "")
    opening = await asyncio.to_thread(
        ai.generate_opening_statement, personality, topic, level, language, mission, claim
    )

    ud.update({
        "language": language,
        "language_iso": language_iso,
        "level": level,
        "personality": personality,
        "topic": topic,
        "mission": mission,
        "mission_weapons": weapons,
        "mission_tip": tip,
        "win_condition": win_condition,
        "used_weapons": [],
        "dialogue": [{"speaker": "AI", "text": opening}],
        "battle_type": "battle",
        "conviction": CONVICTION_START,
        "early_win": False,
        "awaiting_response": True,
    })

    from bot import start_arena_timer
    start_arena_timer(context, user_id, update.effective_chat.id, BATTLE_DURATION_MINUTES)

    emoji = person["name"].split(" ")[0]
    short_name = person["full_name"].split(" —")[0].upper()

    text = (
        f"{emoji} <b>{esc(short_name)}</b>\n\n"
        f"<i>{esc(opening)}</i>\n\n"
        f"────────────\n\n"
        f"🎯 <b>{esc(i18n.t(il, 'BATTLE.MISSION'))}</b>\n"
        f"<b>{esc(mission)}</b>\n\n"
        f"⏱ <i>{esc(i18n.t(il, 'BATTLE.TIME_LIMIT', n=BATTLE_DURATION_MINUTES))}</i>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARSENAL"), callback_data="menu_arsenal")],
    ])

    await context.bot.send_message(update.effective_chat.id, text,
                                   reply_markup=keyboard, parse_mode="HTML")


# ==================================================================
# ХОДЫ БОЯ
# ==================================================================

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = await voice.get_pending_text(update, context)
    if len(user_text) < 2:
        return

    ud = context.user_data
    dialogue = ud.setdefault("dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    ud["awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")
    if user_turns >= BATTLE_MAX_ROUNDS:
        await finish_arena(update, context)
        return

    await _continue_round(update, context)

    if ud.get("conviction", CONVICTION_START) <= CONVICTION_WIN_THRESHOLD:
        ud["early_win"] = True
        await finish_arena(update, context)


async def _continue_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    dialogue = ud["dialogue"]
    personality = ud.get("personality", "devil_advocate")
    user_id = update.effective_user.id
    language_iso = _lang_iso(ud, user_id)
    language = _lang_key(language_iso)
    level = ud.get("level") or db.get_current_level(user_id) or "B1"
    il = db.get_interface_language(user_id)

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    weapons = ud.get("mission_weapons", "")
    mission = ud.get("mission")
    used_weapons = ud.get("used_weapons", [])
    user_name = update.effective_user.first_name or ""

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text_full = " ".join(user_responses)
    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else person['short_name']}: {d['text']}"
        for d in dialogue
    )

    chat_action = "record_voice" if ud.get("last_input_was_voice") else "typing"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=chat_action)
    except Exception:
        pass

    if ud.get("battle_type") == "free_talk":
        memory = db.get_memory(user_id)
        reply = await asyncio.to_thread(
            ai.generate_ai_response, personality, history, last_user, level,
            language, None, user_name, memory,
        )
        if not reply:
            logger.warning("generate_ai_response вернул пусто — показываю fallback")
            reply = i18n.t(il, "ERROR.AI_UNAVAILABLE")
        dialogue.append({"speaker": "AI", "text": reply})
        ud["awaiting_response"] = True

        await voice.maybe_reply_voice(update, context, reply, personality)
        await update.message.reply_text(reply, parse_mode="HTML")
        return

    conviction = ud.get("conviction", CONVICTION_START)
    turn = await asyncio.to_thread(
        ai.generate_battle_turn, personality, history, last_user, level,
        language, mission, user_name, conviction,
    )
    reply = turn["reply"]
    if not reply:
        logger.warning("generate_battle_turn вернул пусто — показываю fallback")
        reply = i18n.t(il, "ERROR.AI_UNAVAILABLE")
    ud["conviction"] = turn["conviction"]
    dialogue.append({"speaker": "AI", "text": reply})
    ud["awaiting_response"] = True

    _, used_count, updated_used = _weapons_status(weapons, user_text_full, used_weapons)
    ud["used_weapons"] = updated_used

    await voice.maybe_reply_voice(update, context, reply, personality)
    await update.message.reply_text(reply, parse_mode="HTML")


def _weapons_status(weapons: str, user_text: str, used_weapons: list):
    if not weapons:
        return "", 0, used_weapons
    items = [w.strip() for w in weapons.replace("·", "|").split("|") if w.strip()]
    new_used = used_weapons.copy()
    user_lower = user_text.lower()
    for item in items:
        key = item.lower()
        if key in user_lower and key not in new_used:
            new_used.append(key)
    lines = ["🗡️ <b>Arsenal:</b>"]
    for item in items:
        mark = "✅" if item.lower() in user_lower else "⬜"
        lines.append(f"  {mark} {esc(item)}")
    return "\n".join(lines), len(new_used), new_used


# ==================================================================
# ЗАВЕРШЕНИЕ БОЯ И ДЕБРИФИНГ
# ==================================================================

async def finish_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot import stop_arena_timer
    user = update.effective_user
    stop_arena_timer(context, user.id)
    await _do_finish(context.bot, user.id, update.effective_chat.id,
                     context.user_data, user.first_name or "")


async def finish_arena_by_timeout(context, user_id: int, chat_id: int):
    ud = context.application.user_data.get(user_id) or {}
    if not ud.get("dialogue"):
        return
    first_name = db.get_user_first_name(user_id)
    await _do_finish(context.bot, user_id, chat_id, ud, first_name)


async def _do_finish(bot, user_id: int, chat_id: int, ud: dict, first_name: str):
    il = db.get_interface_language(user_id)
    dialogue = ud.get("dialogue", [])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    if not user_responses:
        await bot.send_message(chat_id, "❌ …")
        _reset_state(ud)
        return

    language_iso = _lang_iso(ud, user_id)
    language = _lang_key(language_iso)
    level = ud.get("level") or db.get_current_level(user_id) or "B1"
    topic = ud.get("topic", "")
    personality = ud.get("personality", "devil_advocate")
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    weapons = ud.get("mission_weapons", "")
    used_weapons = ud.get("used_weapons", [])

    if ud.get("battle_type") == "free_talk":
        try:
            analysis = await asyncio.to_thread(
                ai.analyze_freetalk, user_responses, language
            )
            db.save_freetalk_session(user_id, personality, language_iso, level, topic,
                                     dialogue, analysis)
            db.update_criteria(user_id, {**analysis["language"], **analysis["communication"]},
                               weight=0.2)
            if analysis.get("interests"):
                db.add_interests(user_id, analysis["interests"])
            est = analysis.get("estimated_level")
            if est:
                db.add_level_snapshot(user_id, est, source="freetalk")
        except Exception:
            pass

        try:
            await asyncio.to_thread(
                personalization.record_session, user_id, "free_talk", user_responses, language
            )
        except Exception:
            logger.exception("personalization.record_session(free_talk) упал")

        skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
        db.add_skill_progress(user_id, skill, 5, battles=0)

        text = i18n.t(il, "FT.DONE", name=first_name or "")
        await bot.send_message(chat_id, text,
                               reply_markup=start._menu_keyboard(user_id, il),
                               parse_mode="HTML")
        _reset_state(ud)
        return

    mission = ud.get("mission", "")
    dialogue_text = "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else person['short_name']}: {d['text']}"
        for d in dialogue
    )

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue_text, topic, level, language,
        personality, weapons, mission,
    )
    criteria = analysis["criteria"]
    conviction = min(ud.get("conviction", CONVICTION_START), analysis.get("conviction", 70))
    rounds_completed = len(user_responses)
    result = gamification.battle_result(criteria, conviction, rounds_completed,
                                        early_win=bool(ud.get("early_win")))
    won = result["won"]
    overall = result["overall"]
    win_score = result["win_score"]

    try:
        previous_criteria = db.get_criteria(user_id)
        unlocked_tools = db.get_unlocked_tools(user_id)
    except Exception:
        logger.exception("Не удалось получить предыдущий профиль/арсенал")
        previous_criteria, unlocked_tools = {}, set()

    try:
        unsolved_now = [q["question"] for q in db.get_unsolved(user_id, limit=5)]
    except Exception:
        unsolved_now = []

    try:
        grammar_phrases_now = [p["phrase"] for p in db.get_grammar_phrases(user_id, limit=40)]
    except Exception:
        grammar_phrases_now = []

    try:
        fb = await asyncio.to_thread(
            ai.generate_battle_debrief, first_name, language, level, personality,
            topic, mission, won, win_score, conviction, criteria, dialogue,
            ud.get("arena_analysis", {}).get("pattern", ""),
            previous_criteria, unlocked_tools,
            unsolved_now, grammar_phrases_now,
        )
    except Exception:
        logger.exception("generate_battle_debrief упал — используем безопасный фолбэк")
        fb = {}
    if not fb:
        fb = {"result_state": "VICTORY" if won else "DEFEATED", "debrief_shape": "full"}

    afu = fb.get("arena_file_update")
    if isinstance(afu, dict):
        try:
            if afu.get("current_read") and afu.get("current_read_changed"):
                db.set_current_read(user_id, afu["current_read"])
            if afu.get("under_pressure"):
                db.set_under_pressure(user_id, afu["under_pressure"])
            for q in afu.get("unsolved_add") or []:
                db.add_unsolved(user_id, q)
            for q in afu.get("unsolved_resolve") or []:
                db.resolve_unsolved(user_id, q)
        except Exception:
            logger.exception("arena_file_update не применён")

    mistakes = fb.get("mistakes", [])
    if mistakes:
        try:
            db.add_vocabulary_mistakes(user_id, mistakes)
        except Exception:
            logger.exception("add_vocabulary_mistakes упал")

    skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
    skill_delta = gamification.calculate_skill_delta(conviction, len(used_weapons), False, won)
    try:
        db.add_skill_progress(user_id, skill, skill_delta)
    except Exception:
        logger.exception("add_skill_progress упал")
    try:
        session_id = db.save_game_session(
            user_id, personality, language_iso, level, topic, rounds_completed,
            criteria, 0, growth_plan="", conviction_final=conviction,
            won=1 if won else 0, overall=overall, mission=mission,
            result_state=fb.get("result_state", ""),
        )
        db.save_session_debrief(session_id, fb)
    except Exception:
        logger.exception("save_game_session упал")
    try:
        db.update_criteria(user_id, criteria, weight=0.4)
    except Exception:
        logger.exception("update_criteria упал")
    if topic:
        try:
            db.add_interests(user_id, [topic])
        except Exception:
            logger.exception("add_interests упал")

    try:
        avg_recent = db.get_recent_avg_scores(user_id, n=3, level=level)
        new_level = gamification.adapt_level(level, avg_recent)
        if new_level != level:
            db.add_level_snapshot(user_id, new_level, source="battle_finish")
            ud["level"] = new_level
    except Exception:
        logger.exception("adapt_level упал")

    try:
        db.mark_first_battle_done(user_id)
        db.mark_temple_done(user_id)
    except Exception:
        logger.exception("mark_first_battle_done/mark_temple_done упали")

    try:
        nemesis = db.get_nemesis(user_id)
        is_nemesis = bool(nemesis and nemesis["personality"] == personality and not nemesis["defeated"])
        if is_nemesis and won:
            db.mark_nemesis_fought(user_id, defeated=True)
        gamification.check_and_unlock_achievements(
            user_id, personality, rounds_completed, criteria, conviction,
            mistakes=mistakes, is_nemesis=is_nemesis, won=won,
        )
    except Exception:
        logger.exception("achievements/nemesis упали")

    # Приём применён в этом бою — увеличиваем счётчик и, если это НОВЫЙ приём, разблокируем.
    newly_unlocked_tool = None
    try:
        tool_key = fb.get("tool_used")
        if tool_key:
            # unlock_tool вернёт True только если это первое появление приёма
            if db.unlock_tool(user_id, tool_key):
                newly_unlocked_tool = tool_key
            db.record_tool_use(user_id, tool_key, won=won, source=f"battle")
    except Exception:
        logger.exception("tool_used / record_tool_use упали")

    # Grammar-фраза использована в бою — увеличиваем счётчик usage.
    try:
        gu = fb.get("grammar_used")
        if gu:
            db.record_phrase_use(user_id, gu, won=won)
    except Exception:
        logger.exception("record_phrase_use упал")

    try:
        gfg = fb.get("grammar_for_goal")
        if isinstance(gfg, dict) and gfg.get("phrases") and gfg.get("goal"):
            db.add_grammar_phrases(user_id, gfg["goal"], gfg["phrases"])
    except Exception:
        logger.exception("add_grammar_phrases упал")

    if is_admin(user_id):
        next_battle_text = i18n.t(il, "DEBRIEF.NEXT_BATTLE_NOW")
    elif BATTLE_COOLDOWN_HOURS <= 0:
        next_battle_text = i18n.t(il, "DEBRIEF.NEXT_BATTLE_NOW")
    elif BATTLE_COOLDOWN_HOURS >= 20:
        next_battle_text = i18n.t(il, "DEBRIEF.NEXT_BATTLE_TOMORROW")
    else:
        next_battle_text = i18n.t(il, "DEBRIEF.NEXT_BATTLE_HOURS").format(h=BATTLE_COOLDOWN_HOURS)

    text = _format_debrief(il, fb, result, person, mistakes, next_battle_text, newly_unlocked_tool)
    keyboard = _debrief_keyboard(il, has_deeper=bool(fb.get("deeper_content")))

    await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

    try:
        await asyncio.to_thread(
            personalization.record_session, user_id, "battle", user_responses, language
        )
    except Exception:
        logger.exception("personalization.record_session(battle) упал")

    _reset_state(ud)


def _format_debrief(il: str, fb: dict, result: dict, person: dict, mistakes: list,
                    next_battle_text: str = "", newly_unlocked_tool: str | None = None) -> str:
    shape = (fb.get("debrief_shape") or "full").strip().lower()

    if shape == "single_insight":
        insight = fb.get("single_insight") or fb.get("notification_line") or fb.get("result_line") or ""
        headline = fb.get("headline") or i18n.t(il, "DEBRIEF.ARENA_NOTICED")
        lines = [f"🏟 <b>{esc(headline)}</b>", ""]
        if insight:
            lines.append(f"<i>{esc(insight)}</i>")
        lines.append(f"\n— {esc(person['short_name'])}")
        if newly_unlocked_tool:
            emoji = ARSENAL_TOOL_EMOJI.get(newly_unlocked_tool, "⚔️")
            name = i18n.t(il, f"TOOLS.{newly_unlocked_tool}.NAME")
            lines.append(f"\n{emoji} <b>{esc(name)}</b>")
        if next_battle_text:
            lines.append(f"\n⚔️ <b>{esc(i18n.t(il, 'DEBRIEF.NEXT_BATTLE'))}:</b> {esc(next_battle_text)}")
        return "\n".join(lines)

    lines = [f"🏟 <b>{esc(i18n.t(il, 'DEBRIEF.TITLE'))}</b>"]

    state_label = fb.get("result_state_label")
    if not state_label:
        state = fb.get("result_state") or ("VICTORY" if result["won"] else "DEFEATED")
        state_label = i18n.t(il, f"DEBRIEF.{state}")
    stars = gamification.result_stars(result["win_score"])
    lines.append(f"\n{stars} <b>{esc(state_label)}</b>")
    if fb.get("result_line"):
        lines.append(esc(fb["result_line"]))

    mq = fb.get("the_moment")
    if isinstance(mq, dict) and mq.get("quote_user"):
        lines.append(f"\n🎬 <b>{esc(i18n.t(il, 'DEBRIEF.THE_MOMENT'))}</b>")
        if mq.get("quote_opponent"):
            lines.append(f"{esc(person['short_name'])}: «{esc(mq['quote_opponent'])}»")
        lines.append(f"{esc(i18n.t(il, 'DEBRIEF.YOU_SAID'))}: «{esc(mq['quote_user'])}»")
        if mq.get("why_it_mattered"):
            lines.append(f"\n<i>{esc(mq['why_it_mattered'])}</i>")

    if fb.get("the_mechanism"):
        lines.append(
            f"\n⚙️ <b>{esc(i18n.t(il, 'DEBRIEF.THE_MECHANISM'))}</b>\n"
            f"{esc(fb['the_mechanism'])}"
        )

    sh = fb.get("the_shift")
    if isinstance(sh, dict) and sh.get("alternative"):
        lines.append(f"\n🔀 <b>{esc(i18n.t(il, 'DEBRIEF.THE_SHIFT'))}</b>")
        lines.append(
            f"{esc(i18n.t(il, 'DEBRIEF.ALTERNATIVE'))}:\n"
            f"<b>«{esc(sh['alternative'])}»</b>"
        )
        if sh.get("why_it_would_work"):
            lines.append(f"<i>{esc(sh['why_it_would_work'])}</i>")

    er = fb.get("escape_route")
    if isinstance(er, dict) and er.get("rule"):
        lines.append(f"\n🚪 <b>{esc(i18n.t(il, 'DEBRIEF.ESCAPE_ROUTE'))}</b>")
        if er.get("trap"):
            lines.append(f"<i>{esc(er['trap'])}</i>")
        lines.append(f"<b>{esc(er['rule'])}</b>")
        if er.get("example"):
            lines.append(f"💬 «{esc(er['example'])}»")

    if newly_unlocked_tool:
        emoji = ARSENAL_TOOL_EMOJI.get(newly_unlocked_tool, "⚔️")
        name = i18n.t(il, f"TOOLS.{newly_unlocked_tool}.NAME")
        desc = i18n.t(il, f"TOOLS.{newly_unlocked_tool}.DESC")
        example = i18n.t(il, f"TOOLS.{newly_unlocked_tool}.EXAMPLE")
        lines.append(f"\n{emoji} <b>{esc(i18n.t(il, 'DEBRIEF.THE_MOVE'))}: {esc(name.upper())}</b>")
        lines.append(esc(desc))
        lines.append(f"💬 {esc(example)}")

    if fb.get("opponent_advice"):
        lines.append(
            f"\n🎭 <b>{esc(person['short_name'])}:</b>\n"
            f"<i>{esc(fb['opponent_advice'])}</i>"
        )

    ar = fb.get("arena_read")
    if isinstance(ar, dict) and (ar.get("skill_now") or ar.get("test_next")):
        lines.append(f"\n🏛 <b>{esc(i18n.t(il, 'DEBRIEF.THE_ARENA_READ'))}</b>")
        if ar.get("skill_now"):
            lines.append(esc(ar["skill_now"]))
        if ar.get("test_next"):
            lines.append(f"→ <b>{esc(ar['test_next'])}</b>")

    up = fb.get("language_upgrade")
    if up:
        lines.append(
            f"\n🔧 <b>{esc(i18n.t(il, 'DEBRIEF.LANGUAGE_UPGRADE'))}</b>\n"
            f"{esc(i18n.t(il, 'DEBRIEF.YOU_SAID'))}: «{esc(up['said'])}»\n"
            f"{esc(i18n.t(il, 'DEBRIEF.BETTER'))}: <b>«{esc(up['better'])}»</b>\n"
            f"<i>{esc(up['why'])}</i>"
        )

    gfg = fb.get("grammar_for_goal")
    if isinstance(gfg, dict) and gfg.get("grammar_pattern") and gfg.get("phrases"):
        goal_label = ""
        if gfg.get("goal"):
            goal_label = i18n.t(il, f"CRITERIA.{gfg['goal']}")
        title = i18n.t(il, "DEBRIEF.GRAMMAR_FOR_GOAL")
        if goal_label:
            title = f"{title} · {goal_label.upper()}"
        lines.append(f"\n📐 <b>{esc(title)}</b>")
        lines.append(f"<b>{esc(gfg['grammar_pattern'])}</b>")
        if gfg.get("why_it_helps"):
            lines.append(f"<i>{esc(gfg['why_it_helps'])}</i>")
        phrases = gfg.get("phrases") or []
        if phrases:
            plines = "\n".join(f"  • «{esc(p)}»" for p in phrases[:4])
            lines.append(plines)
        if gfg.get("example_from_battle"):
            lines.append(
                f"\n{esc(i18n.t(il, 'DEBRIEF.YOU_COULD_SAY'))}: "
                f"<b>«{esc(gfg['example_from_battle'])}»</b>"
            )
    else:
        gf = fb.get("grammar_focus")
        if isinstance(gf, dict) and gf.get("pattern"):
            lines.append(f"\n📐 <b>{esc(i18n.t(il, 'DEBRIEF.GRAMMAR_FOCUS'))}</b>")
            lines.append(f"<b>{esc(gf['pattern'])}</b>")
            if gf.get("example_wrong"):
                lines.append(f"❌ «{esc(gf['example_wrong'])}»")
            if gf.get("example_right"):
                lines.append(f"✅ «{esc(gf['example_right'])}»")
            if gf.get("drill"):
                lines.append(f"<i>{esc(gf['drill'])}</i>")

    deeper = fb.get("deeper_content")
    if isinstance(deeper, dict) and deeper.get("topic") and deeper.get("why"):
        lines.append(
            f"\n📖 <b>{esc(i18n.t(il, 'DEBRIEF.WANT_TO_GO_DEEPER'))}</b>\n"
            f"<i>{esc(deeper['why'])}</i>"
        )

    if next_battle_text:
        lines.append(f"\n⚔️ <b>{esc(i18n.t(il, 'DEBRIEF.NEXT_BATTLE'))}:</b> {esc(next_battle_text)}")

    return "\n".join(lines)


def _debrief_keyboard(il: str, has_deeper: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
    ]
    if has_deeper:
        rows.append([InlineKeyboardButton(i18n.t(il, "DEBRIEF.READ_THE_BREAKDOWN"), url=CHANNEL_URL)])
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")])
    return InlineKeyboardMarkup(rows)


async def arsenal_add_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    await query.edit_message_text(_build_arsenal_text_compat(user_id, il), parse_mode="HTML")


def _build_arsenal_text_compat(user_id: int, il: str) -> str:
    from handlers.profile import _build_arsenal_text
    return _build_arsenal_text(user_id, il)


# ==================================================================
# FREE TALK
# ==================================================================

async def freetalk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    if context.user_data.get("dialogue"):
        await query.edit_message_text(i18n.t(il, "FT.BUSY"))
        return

    rows = []
    for iso in SUPPORTED_LANGUAGES:
        label = f"{LANGUAGE_FLAGS.get(iso, '')} {LANGUAGE_DISPLAY.get(iso, iso)}".strip()
        rows.append([InlineKeyboardButton(label, callback_data=f"ft_lang_{iso}")])
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")])

    await query.edit_message_text(
        i18n.t(il, "FT.SELECT_LANGUAGE"),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


async def ft_select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    iso = query.data.replace("ft_lang_", "")
    if iso not in SUPPORTED_LANGUAGES:
        return
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)

    context.user_data["_ft_language_iso"] = iso

    rows = [
        [InlineKeyboardButton(p["name"], callback_data=f"freetalk_pick_{key}")]
        for key, p in PERSONALITIES.items()
    ]
    rows.append([InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")])

    await query.edit_message_text(
        i18n.t(il, "FT.SELECT_CHARACTER"),
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="HTML",
    )


async def freetalk_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = user.id
    ud = context.user_data
    il = db.get_interface_language(user_id)

    personality = query.data.replace("freetalk_pick_", "")
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    language_iso = ud.pop("_ft_language_iso", None) or db.get_learning_language(user_id)
    db.set_learning_language(user_id, language_iso)
    language = _lang_key(language_iso)
    level = db.get_current_level(user_id) or "B1"
    memory = db.get_memory(user_id)
    interests = memory.get("interests") or []
    topic = interests[0] if interests else ""

    opening = await asyncio.to_thread(
        ai.generate_freetalk_opening, personality, memory, language, level,
        user.first_name or "",
    )

    ud.update({
        "personality": personality,
        "language": language,
        "language_iso": language_iso,
        "level": level,
        "topic": topic,
        "mission": None,
        "mission_weapons": "",
        "used_weapons": [],
        "battle_type": "free_talk",
        "dialogue": [],
        "awaiting_response": True,
    })

    await context.bot.send_message(
        update.effective_chat.id,
        f"<i>{esc(opening)}</i>",
        parse_mode="HTML",
    )
    await voice.maybe_reply_voice(update, context, opening, personality)


# ==================================================================
# ТЕКСТОВЫЙ РОУТЕР
# ==================================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ud = context.user_data
    if ud.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
    elif ud.get("awaiting_response"):
        await handle_response(update, context)
    else:
        user_id = update.effective_user.id
        il = db.get_interface_language(user_id)
        await update.message.reply_text(i18n.t(il, "MENU.NO_ACTIVE"))