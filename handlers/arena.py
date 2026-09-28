"""
handlers/arena.py — бой, дебрифинг, свободный разговор, арсенал.

Принципы:
  • Бой — детерминированный. Таймер и старт/стоп — в bot.py.
  • В бою НЕТ обратной связи: ни шкал, ни «правильно/неправильно».
  • В бою НЕТ слова STOP. Останавливается сам по таймеру (bot.arena_timeout).
  • В бою НЕТ префиксов «Victor:», «Richard:» перед каждой репликой.
  • Debrief — ARENA-стиль: narrative RESULT / BEST MOVE / LOST GROUND /
    NEW WEAPON / LANGUAGE UPGRADE / OPPONENT ADVICE / ARENA NOTICED / NEXT BATTLE.
    Без /100, без «performance review», без JSON-ключей в названиях скиллов.
  • Free Talk — отдельный режим, без таймера, без миссии, без победы/поражения.
"""
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
import i18n
import voice
from config import (
    BATTLE_DURATION_MINUTES,
    BATTLE_MAX_ROUNDS,
    CONVICTION_START,
    CONVICTION_WIN_THRESHOLD,
    ISO_TO_LANG_KEY,
    SUPPORTED_LANGUAGES,
    LANGUAGE_DISPLAY,
    LANGUAGE_FLAGS,
    is_admin,
)
from game_data import (
    PERSONALITIES, PERSONALITY_TO_SKILL,
)
from handlers import intro, start
from handlers.ui import send_or_edit, esc

logger = logging.getLogger(__name__)

STATE_KEYS = [
    "language", "language_iso", "level", "topic", "personality",
    "mission_weapons", "mission_tip", "win_condition", "mission",
    "used_weapons", "dialogue", "turn", "awaiting_response", "battle_type",
    "arena_analysis", "conviction", "early_win", "last_input_was_voice",
    "_freetalk_personality", "awaiting_freetalk_topic", "_ft_language_iso",
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

    opening = await asyncio.to_thread(
        ai.generate_opening_statement, personality, topic, level, language, mission
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

    text = (
        f"⚔️ <b>{esc(i18n.t(il, 'BATTLE.BEGINS'))}</b>\n\n"
        f"<b>{esc(person['full_name'].upper())}</b>\n\n"
        f"🎯 <b>{esc(i18n.t(il, 'BATTLE.MISSION'))}</b>\n"
        f"<b>{esc(mission)}</b>\n\n"
        f"⏱ <i>{esc(i18n.t(il, 'BATTLE.TIME_LIMIT', n=BATTLE_DURATION_MINUTES))}</i>\n\n"
        f"────────────\n\n"
        f"<i>{esc(opening)}</i>"
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
        reply = reply or person.get("phrase", "…")
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
    reply = turn["reply"] or person.get("phrase", "…")
    ud["conviction"] = turn["conviction"]
    dialogue.append({"speaker": "AI", "text": reply})
    ud["awaiting_response"] = True

    _, _, updated_used = _weapons_status(weapons, user_text_full, used_weapons)
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
# ФИНАЛИЗАЦИЯ БОЯ
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
        await bot.send_message(
            chat_id,
            f"🏁 <b>{esc(i18n.t(il, 'DEBRIEF.TITLE'))}</b>\n\n"
            f"{esc(i18n.t(il, 'DEBRIEF.SILENT'))}",
            parse_mode="HTML",
            reply_markup=start._menu_keyboard(user_id, il),
        )
        db.mark_first_battle_done(user_id)
        db.mark_temple_done(user_id)
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

    # ---------- FREE TALK ----------
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
            logger.exception("Free Talk analysis failed")

        skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
        db.add_skill_progress(user_id, skill, 5, battles=0)

        text = i18n.t(il, "FT.DONE", name=first_name or "")
        await bot.send_message(chat_id, text,
                               reply_markup=start._menu_keyboard(user_id, il),
                               parse_mode="HTML")
        _reset_state(ud)
        return

    # ---------- БОЕВОЙ ДЕБРИФ ----------
    mission = ud.get("mission", "")
    dialogue_text = "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else person['short_name']}: {d['text']}"
        for d in dialogue
    )

    try:
        previous_criteria = db.get_criteria(user_id)
        weapon_tiers = db.get_weapon_tiers(user_id)
    except Exception:
        logger.exception("Не удалось получить предыдущий профиль")
        previous_criteria, weapon_tiers = {}, {}

    try:
        analysis = await asyncio.to_thread(
            ai.analyze_debate, user_responses, dialogue_text, topic, level, language,
            personality, weapons, mission,
        )
    except Exception:
        logger.exception("analyze_debate упал")
        analysis = {
            "criteria": {k: 50 for k in (
                "grammar", "vocabulary", "fluency", "naturalness",
                "clarity", "argumentation", "adaptability",
                "persuasion", "evidence", "control",
            )},
            "conviction": 70,
        }

    criteria = analysis["criteria"]
    conviction = min(ud.get("conviction", CONVICTION_START), analysis.get("conviction", 70))
    rounds_completed = len(user_responses)
    result = gamification.battle_result(criteria, conviction, rounds_completed,
                                        early_win=bool(ud.get("early_win")))
    won = result["won"]
    overall = result["overall"]
    win_score = result["win_score"]

    try:
        fb = await asyncio.to_thread(
            ai.generate_battle_debrief, first_name, language, level, personality,
            topic, mission, won, win_score, conviction, criteria, dialogue,
            ud.get("arena_analysis", {}).get("pattern", ""),
            previous_criteria, weapon_tiers,
        )
    except Exception:
        logger.exception("generate_battle_debrief упал")
        fb = {}
    if not fb:
        fb = {"result_state": "YOU HAD THE ADVANTAGE" if won else "YOU LOST THE ROOM"}

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
        db.save_game_session(
            user_id, personality, language_iso, level, topic, rounds_completed,
            criteria, 0, growth_plan=fb.get("growth", ""), conviction_final=conviction,
            won=1 if won else 0, overall=overall, mission=mission,
            result_state=fb.get("result_state", ""),
        )
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

    text = _format_debrief(il, fb, result, person, mistakes)
    keyboard = _debrief_keyboard(il, has_weapon=bool(fb.get("new_weapon")))

    await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")

    ud["_pending_weapon"] = fb.get("new_weapon")
    ud["_pending_weapon_source"] = personality
    _reset_state(ud)
    if fb.get("new_weapon"):
        ud["_pending_weapon"] = fb.get("new_weapon")
        ud["_pending_weapon_source"] = personality


def _format_debrief(il: str, fb: dict, result: dict, person: dict, mistakes: list) -> str:
    lines = [f"🏟 <b>{esc(i18n.t(il, 'DEBRIEF.TITLE'))}</b>"]

    state = fb.get("result_state") or ("YOU HAD THE ADVANTAGE" if result["won"] else "YOU LOST THE ROOM")
    state_key = state.upper().replace(" ", "_")
    state_label = i18n.t(il, f"DEBRIEF.{state_key}")
    if state_label == f"DEBRIEF.{state_key}":
        state_label = state
    lines.append(f"\n<b>{esc(state_label)}</b>")
    if fb.get("result_line"):
        lines.append(esc(fb["result_line"]))

    bm = fb.get("best_move") or {}
    if bm.get("what"):
        lines.append(f"\n🔥 <b>{esc(i18n.t(il, 'DEBRIEF.BEST_MOVE'))}</b>")
        lines.append(esc(bm["what"]))
        if bm.get("why"):
            lines.append(f"<i>{esc(bm['why'])}</i>")
        if bm.get("skill"):
            skill_label = str(bm["skill"]).replace("_", " ").upper()
            lines.append(f"🎯 <b>{esc(skill_label)}</b>")

    lg = fb.get("lost_ground") or {}
    if lg.get("what"):
        lines.append(f"\n💀 <b>{esc(i18n.t(il, 'DEBRIEF.LOST_GROUND'))}</b>")
        lines.append(esc(lg["what"]))
        if lg.get("why"):
            lines.append(f"<i>{esc(lg['why'])}</i>")

    nw = fb.get("new_weapon")
    if nw and nw.get("label"):
        lines.append(f"\n{nw['label']}")
        if nw.get("description"):
            lines.append(esc(nw["description"]))
        if nw.get("language_upgrade"):
            lines.append(f"🗣 <i>{esc(nw['language_upgrade'])}</i>")
        if nw.get("why_it_matters"):
            lines.append(esc(nw["why_it_matters"]))
        if nw.get("soft_skill"):
            lines.append(nw["soft_skill"])

    lu = fb.get("language_upgrade")
    if lu and lu.get("what"):
        lines.append(f"\n🗣 <b>{esc(i18n.t(il, 'DEBRIEF.LANGUAGE_UPGRADE'))}</b>")
        lines.append(esc(lu["what"]))
        if lu.get("why"):
            lines.append(f"<i>{esc(lu['why'])}</i>")

    if fb.get("opponent_advice"):
        lines.append(
            f"\n🎭 <b>{esc(person['short_name'])}:</b>\n<i>{esc(fb['opponent_advice'])}</i>"
        )

    if fb.get("arena_noticed"):
        lines.append(
            f"\n🏛 <b>{esc(i18n.t(il, 'DEBRIEF.ARENA_NOTICED'))}</b>\n{esc(fb['arena_noticed'])}"
        )

    nb = fb.get("next_battle") or {}
    if nb.get("target"):
        target_name = (nb["target"] or "").replace("_", " ").upper()
        lines.append(f"\n⚔️ <b>{esc(i18n.t(il, 'DEBRIEF.NEXT_BATTLE'))}: {esc(target_name)}</b>")
        if nb.get("hint"):
            lines.append(f"<i>{esc(nb['hint'])}</i>")

    if mistakes and len(mistakes) >= 3:
        mlines = "\n".join(
            f"  • {esc(m['wrong'])} → <b>{esc(m['correct'])}</b>" for m in mistakes[:3]
        )
        lines.append(f"\n📚 <b>{esc(i18n.t(il, 'DEBRIEF.LANGUAGE_CHECK'))}</b>\n{mlines}")

    return "\n".join(lines)


def _debrief_keyboard(il: str, has_weapon: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if has_weapon:
        rows.append([
            InlineKeyboardButton(
                i18n.t(il, "DEBRIEF.ADD_WEAPON"),
                callback_data="arsenal_add_pending",
            )
        ])
    rows += [
        [InlineKeyboardButton(i18n.t(il, "MENU.MY_ARENA"), callback_data="menu_profile")],
        [InlineKeyboardButton(i18n.t(il, "MENU.FREE_TALK"), callback_data="freetalk")],
        [InlineKeyboardButton(i18n.t(il, "MENU.BACK"), callback_data="back_to_main")],
    ]
    return InlineKeyboardMarkup(rows)


# ==================================================================
# АРСЕНАЛ: положить оружие в «Мой арсенал»
# ==================================================================

async def arsenal_add_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    ud = context.user_data
    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    weapon = ud.pop("_pending_weapon", None)
    source = ud.pop("_pending_weapon_source", "")

    added = False
    if isinstance(weapon, dict) and weapon.get("label"):
        added = db.add_arsenal_item(
            user_id,
            kind=weapon.get("kind", "move"),
            content=weapon.get("description") or weapon.get("label"),
            source=source,
            label=weapon.get("label", ""),
            description=weapon.get("description", ""),
            language_upgrade=weapon.get("language_upgrade", ""),
            soft_skill=weapon.get("soft_skill", ""),
        )

    text = i18n.t(il, "ARSENAL.SAVED") if added else i18n.t(il, "ARSENAL.EMPTY_ADD")
    await query.edit_message_text(text)


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
    """
    Единая точка входа для любого текстового/голосового хода.
    Порядок важен:
      1. Храм (fe_awaiting_response) — 8 реплик до назначения персонажа.
      2. Бой/Free Talk (awaiting_response).
      3. Иначе — подсказка «нет активной игры».
    """
    ud = context.user_data

    if ud.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
        return

    if ud.get("awaiting_response"):
        await handle_response(update, context)
        return

    user_id = update.effective_user.id
    il = db.get_interface_language(user_id)
    await update.message.reply_text(i18n.t(il, "MENU.NO_ACTIVE"))