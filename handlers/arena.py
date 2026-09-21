"""
handlers/arena.py — бой, свободный разговор, подведение итогов.

Бой: миссия от Арены → арсенал слов → персонаж сопротивляется через generate_battle_turn,
«убеждённость» падает только за сильные аргументы (AI решает, не формула).
Победа/поражение — gamification.battle_result: 50% убеждённость + 50% средний балл
по 10 критериям. Обратная связь — ai.generate_arena_feedback (на языке пользователя,
по имени, с ошибками из реального диалога и фразами для «кражи»).
"""
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
import voice
from config import (
    BATTLE_DURATION_MINUTES,
    BATTLE_MAX_ROUNDS,
    CONVICTION_START,
    CONVICTION_WIN_THRESHOLD,
    is_admin,
)
from game_data import (
    LEVELS, PERSONALITIES, BADGES, ARENA_UI_STRINGS,
    PERSONALITY_TO_SKILL, CRITERIA_LABELS_RU,
)
from handlers import intro, start
from handlers.ui import esc

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_weapons", "mission_tip",
    "win_condition", "mission", "used_weapons", "dialogue", "turn",
    "awaiting_response", "asked_continue", "battle_type",
    "arena_analysis", "conviction", "early_win", "quest_done",
    "_freetalk_personality", "awaiting_freetalk_topic", "last_input_was_voice",
]


def _reset_state(ud: dict):
    for key in STATE_KEYS:
        ud.pop(key, None)


def _ui(language: str) -> dict:
    return ARENA_UI_STRINGS.get(language) or ARENA_UI_STRINGS["english"]


def _effective_level(context, user_id) -> str:
    level = context.user_data.get("level") or db.get_current_level(user_id)
    if level not in LEVELS:
        level = db.get_current_level(user_id) or "B1"
    context.user_data["level"] = level
    return level


def format_weapons_status(weapons: str, user_text: str, used_weapons: list):
    if not weapons:
        return "", 0, used_weapons
    items = [w.strip() for w in weapons.replace("·", "|").split("|") if w.strip()]
    new_used = used_weapons.copy()
    user_lower = user_text.lower()
    for item in items:
        key = item.lower()
        if key in user_lower and key not in new_used:
            new_used.append(key)
    lines = ["🗡️ <b>Арсенал:</b>"]
    for item in items:
        mark = "✅" if item.lower() in user_lower else "⬜"
        lines.append(f"  {mark} {item}")
    return "\n".join(lines), len(new_used), new_used


# ------------------------------------------------------------------
# Вход в бой из меню
# ------------------------------------------------------------------

async def play_entry(update, context):
    """⚔️ Battle. Первый раз — Храм. Дальше — бой следующего дня."""
    user_id = update.effective_user.id

    if not db.has_completed_first_battle(user_id) and not is_admin(user_id):
        await intro.enter_arena_menu(update, context)
        return

    if db.has_battled_today(user_id) and not is_admin(user_id):
        hours_left = db.cooldown_hours_left(user_id)
        text = (
            f"⚔️ Следующий бой будет через ~{int(hours_left) + 1} ч.\n"
            f"Арена даёт время всё обдумать. А пока можно просто поговорить."
        )
        markup = start.post_battle_keyboard()
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=markup)
        else:
            await update.message.reply_text(text, reply_markup=markup)
        return

    await intro.daily_battle(update, context)


async def stop_command(update, context):
    if not context.user_data.get("dialogue"):
        await update.message.reply_text("Нет активной игры.")
        return
    await update.message.reply_text("🏁 Завершаем...")
    await finish_arena(update, context)


# ------------------------------------------------------------------
# НАЧАЛО БОЯ (кнопка "⚔️ ENTER BATTLE")
# ------------------------------------------------------------------

async def start_battle(update, context):
    """fe_start_battle: миссия + арсенал + таймер + первая реплика персонажа."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = user.id
    ud = context.user_data

    language = ud.get("language") or db.get_user_language(user_id) or "english"
    level = _effective_level(context, user_id)
    personality = ud.get("personality") or "devil_advocate"
    topic = ud.get("topic") or "a topic you care about"
    ui = _ui(language)
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    gamification.ensure_quest(user_id)

    await query.edit_message_text(f"⚔️ {esc(ui['thinking'])}")

    analysis = ud.get("arena_analysis") or db.get_latest_arena_analysis(user_id) or {}
    mission, weapons_pack = await asyncio.gather(
        asyncio.to_thread(ai.generate_mission_task, topic, personality,
                          user.first_name or "", language, level),
        asyncio.to_thread(ai.generate_mission_weapons, topic, level, personality,
                          language, analysis, analysis.get("weakest_skill")),
    )
    weapons, tip, win_condition = weapons_pack
    opening = await asyncio.to_thread(ai.generate_opening_statement,
                                      personality, topic, level, language, mission)

    ud.update({
        "language": language,
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

    weapon_lines = "\n".join(f"  ⬜ {w.strip()}" for w in weapons.replace("·", "|").split("|") if w.strip())
    text = (
        f"⚔️ <b>{esc(ui['battle_begins'])}</b>\n\n"
        f"🎯 <b>{esc(ui['mission'])}:</b> {esc(mission)}\n"
        f"🗡️ <b>{esc(ui['weapons'])}:</b>\n{weapon_lines}\n"
        f"💡 <b>{esc(ui['tip'])}:</b> {esc(tip)}\n"
        f"🏁 <b>{esc(ui['how_to_win'])}:</b> {esc(win_condition)}\n"
        f"⏱️ {esc(ui['time_limit'].format(n=BATTLE_DURATION_MINUTES))}\n\n"
        f"<b>{esc(person['short_name'])}:</b> <i>{esc(opening)}</i>\n\n"
        f"<i>{esc(ui['reply_or_stop'])}</i>"
    )
    await context.bot.send_message(update.effective_chat.id, text, parse_mode="HTML")


# ------------------------------------------------------------------
# ХОДЫ БОЯ
# ------------------------------------------------------------------

async def handle_response(update, context):
    user_text = await voice.get_pending_text(update, context)
    if len(user_text) < 2:
        await update.message.reply_text("❌ Слишком коротко.")
        return

    ud = context.user_data
    dialogue = ud.setdefault("dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    ud["awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")
    if ud.get("battle_type") != "free_talk" and user_turns >= BATTLE_MAX_ROUNDS:
        await finish_arena(update, context)
        return

    await _continue_round(update, context)

    if (
        ud.get("battle_type") != "free_talk"
        and ud.get("dialogue")
        and ud.get("conviction", CONVICTION_START) <= CONVICTION_WIN_THRESHOLD
    ):
        ud["early_win"] = True
        await update.message.reply_text(f"🏆 {_ui(ud.get('language', 'english'))['early_win']}")
        await finish_arena(update, context)


async def _continue_round(update, context):
    ud = context.user_data
    dialogue = ud["dialogue"]
    personality = ud.get("personality", "devil_advocate")
    language = ud.get("language", "english")
    level = _effective_level(context, update.effective_user.id)
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    weapons = ud.get("mission_weapons", "")
    mission = ud.get("mission")
    used_weapons = ud.get("used_weapons", [])
    user_name = update.effective_user.first_name or ""

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text_full = " ".join(user_responses)
    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else person['short_name']}: {d['text']}" for d in dialogue
    )

    chat_action = "record_voice" if ud.get("last_input_was_voice") else "typing"
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=chat_action)
    except Exception:
        pass

    if ud.get("battle_type") == "free_talk":
        memory = db.get_memory(update.effective_user.id)
        ai_reply = await asyncio.to_thread(
            ai.generate_ai_response, personality, history, last_user, level, language,
            None, user_name, memory,
        )
        ai_reply = ai_reply or person.get("phrase", "...")
        dialogue.append({"speaker": "AI", "text": ai_reply})
        ud["awaiting_response"] = True
        await voice.maybe_reply_voice(update, context, ai_reply, personality)
        await update.message.reply_text(
            f"<b>{esc(person['name'])}:</b>\n<i>{esc(ai_reply)}</i>\n\n"
            f"💬 /stop — закончить",
            parse_mode="HTML",
        )
        return

    # --- боевой ход: убеждённость решает персонаж, не формула ---
    conviction = ud.get("conviction", CONVICTION_START)
    turn = await asyncio.to_thread(
        ai.generate_battle_turn, personality, history, last_user, level, language,
        mission, user_name, conviction,
    )
    ai_reply = turn["reply"] or person.get("phrase", "...")
    ud["conviction"] = turn["conviction"]
    dialogue.append({"speaker": "AI", "text": ai_reply})
    ud["awaiting_response"] = True

    ui = _ui(language)
    weapons_status, used_count, updated_used = format_weapons_status(weapons, user_text_full, used_weapons)
    new_weapon_used = used_count > len(used_weapons)
    ud["used_weapons"] = updated_used

    conv = ud["conviction"]
    bar = "█" * int((100 - conv) / 10) + "░" * int(conv / 10)
    weapon_note = "\n✨ +арсенал" if new_weapon_used else ""
    await voice.maybe_reply_voice(update, context, ai_reply, personality)
    await update.message.reply_text(
        f"<b>{esc(person['name'])}:</b>\n<i>{esc(ai_reply)}</i>\n\n"
        f"{weapons_status}\n\n"
        f"🔥 {esc(ui['persuaded'])}: {bar} {conv}%{weapon_note}\n"
        f"💬 /stop — закончить",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------
# ИТОГИ (общее ядро: и по /stop, и по таймеру)
# ------------------------------------------------------------------

async def finish_arena(update, context):
    from bot import stop_arena_timer
    user = update.effective_user
    stop_arena_timer(context, user.id)
    await _do_finish(context.bot, user.id, update.effective_chat.id,
                     context.user_data, user.first_name or "")


async def finish_arena_by_timeout(context, user_id: int, chat_id: int):
    """Вызывается из job_queue, когда вышло время боя."""
    user_data = context.application.user_data.get(user_id) or {}
    if not user_data.get("dialogue"):
        return
    first_name = db.get_user_first_name(user_id)
    await _do_finish(context.bot, user_id, chat_id, user_data, first_name)


async def _do_finish(bot, user_id: int, chat_id: int, ud: dict, first_name: str):
    language = ud.get("language") or db.get_user_language(user_id) or "english"
    ui = _ui(language)
    level = ud.get("level") or db.get_current_level(user_id) or "B1"
    topic = ud.get("topic", "")
    personality = ud.get("personality", "devil_advocate")
    weapons = ud.get("mission_weapons", "")
    used_weapons = ud.get("used_weapons", [])
    dialogue = ud.get("dialogue", [])
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]

    if not user_responses:
        await bot.send_message(chat_id, "❌ Ты ничего не сказал(а).")
        _reset_state(ud)
        return

    # ---------- Свободный разговор: без оценки, только память Арены ----------
    if ud.get("battle_type") == "free_talk":
        await bot.send_message(chat_id, f"💬 {esc(ui['judging'])}")
        try:
            analysis = await asyncio.to_thread(ai.analyze_freetalk, user_responses, language)
            db.save_freetalk_session(user_id, personality, language, level, topic, dialogue, analysis)
            db.update_criteria(user_id, {**analysis.get("language", {}),
                                         **analysis.get("communication", {})}, weight=0.2)
            if analysis.get("interests"):
                db.add_interests(user_id, analysis["interests"])
            est = analysis.get("estimated_level")
            if est in LEVELS and est != level:
                db.add_level_snapshot(user_id, est, source="freetalk")
        except Exception:
            pass
        skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
        db.add_skill_progress(user_id, skill, 8, battles=0)
        text = f"{esc(ui['ft_done'].format(name=first_name))}\n\n⚡ +8 XP — {esc(person['name'])}"
        await bot.send_message(chat_id, text, reply_markup=start.post_battle_keyboard())
        _reset_state(ud)
        return

    # ---------- Боевой разбор ----------
    mission = ud.get("mission", "")
    quest = db.get_active_quest(user_id)
    quest_desc = quest["description"] if quest else ""
    dialogue_text = "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else person['short_name']}: {d['text']}" for d in dialogue
    )

    await bot.send_message(chat_id, f"📝 {esc(ui['judging'])}")

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue_text, topic, level, language,
        personality, weapons, quest_desc,
    )
    criteria = analysis["criteria"]
    conviction = min(ud.get("conviction", CONVICTION_START), analysis.get("conviction", 70))
    rounds_completed = len(user_responses)
    result = gamification.battle_result(criteria, conviction, rounds_completed,
                                        early_win=bool(ud.get("early_win")))
    won = result["won"]
    overall = result["overall"]
    win_score = result["win_score"]

    best_key = max(criteria, key=criteria.get)
    worst_key = min(criteria, key=criteria.get)

    fb = await asyncio.to_thread(
        ai.generate_arena_feedback, first_name, language, level, personality,
        topic, mission, won, conviction, criteria, dialogue,
    )
    mistakes = fb.get("mistakes", [])
    if mistakes:
        db.add_vocabulary_mistakes(user_id, mistakes)

    quest_done = gamification.evaluate_quest(
        quest, len(used_weapons), personality, won, len(mistakes),
        bool(analysis.get("quest_done")),
    )

    nemesis = db.get_nemesis(user_id)
    is_nemesis = bool(nemesis and nemesis["personality"] == personality and not nemesis["defeated"])
    if is_nemesis:
        db.mark_nemesis_fought(user_id, defeated=won)

    stats = db.get_user_stats(user_id)
    is_new_character = personality not in stats["unique_personalities"]
    hours_since = db.get_hours_since_last_battle(user_id)
    is_first_daily = hours_since is None or hours_since >= 20

    points = gamification.calculate_points(
        rounds_completed, conviction, len(used_weapons), quest_done, len(mistakes),
        is_first_daily, is_new_character, is_nemesis, won,
    )
    skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
    skill_delta = gamification.calculate_skill_delta(conviction, len(used_weapons), quest_done, is_nemesis, won)

    db.save_game_session(
        user_id, personality, language, level, topic, rounds_completed, criteria, points,
        strength=CRITERIA_LABELS_RU.get(best_key, best_key),
        growth=CRITERIA_LABELS_RU.get(worst_key, worst_key),
        conviction_final=conviction, quest_done=1 if quest_done else 0,
        won=1 if won else 0, overall=overall,
    )
    db.update_criteria(user_id, criteria, weight=0.4)
    if topic:
        db.add_interests(user_id, [topic])
    db.add_points(user_id, points)
    db.mark_first_battle_done(user_id)

    avg_recent = db.get_recent_avg_scores(user_id, n=3)
    new_level = gamification.adapt_level(level, avg_recent)
    if new_level != level:
        db.add_level_snapshot(user_id, new_level, source="battle_finish")
        ud["level"] = new_level

    new_badges = gamification.check_and_unlock_achievements(
        user_id, personality, rounds_completed, criteria, conviction, quest_done,
        mistakes, is_nemesis=is_nemesis, won=won,
    )

    if quest_done and quest:
        db.complete_quest(user_id)
    gamification.ensure_quest(user_id)

    # ---------- Сообщение-вердикт (всё на языке пользователя) ----------
    stars = gamification.result_stars(win_score)
    lines = []
    if fb.get("wow"):
        lines.append(f"🏟️ <b>{esc(fb['wow'])}</b>")
    lines.append(f"{stars} <b>{esc(ui['victory'] if won else ui['defeat'])}</b>"
                 f" · win score {win_score}/100")
    if fb.get("worked"):
        lines.append(f"\n✅ <b>{esc(ui['worked'])}:</b> {esc(fb['worked'])}")
    why_label = ui["why_won"] if won else ui["why_lost"]
    if fb.get("why"):
        lines.append(f"{'🏆' if won else '💀'} <b>{esc(why_label)}:</b> {esc(fb['why'])}")
    if fb.get("great_phrases"):
        lines.append("🔥 " + " · ".join(f"<i>{esc(p)}</i>" for p in fb["great_phrases"]))
    if mistakes:
        mlines = "\n".join(f"  • {esc(m['wrong'])} → <b>{esc(m['correct'])}</b>" for m in mistakes[:5])
        lines.append(f"\n📚 <b>{esc(ui['language_check'])}:</b>\n{mlines}")
    if fb.get("steal"):
        slines = "\n".join(f"  • <i>{esc(p)}</i>" for p in fb["steal"])
        lines.append(f"\n🧠 <b>{esc(ui['steal'].format(name=person['short_name']))}:</b>\n{slines}")
    if fb.get("character_line"):
        lines.append(f"\n🎭 <b>{esc(person['short_name'])}:</b> <i>{esc(fb['character_line'])}</i>")

    lines.append(f"\n⭐ <b>+{points}</b> · ⚡ <b>+{skill_delta} XP</b> — {esc(person['name'])} ({skill})")
    if quest_done and quest:
        lines.append(f"🎯 <b>Quest:</b> {esc(quest['description'])}")
    if new_badges:
        names = ", ".join(BADGES[b]["name"] for b in new_badges if b in BADGES)
        lines.append(f"🎉 {esc(names)}")
    cooldown = "завтра" if not is_admin(user_id) else "когда захочешь (админ)"
    lines.append(f"\n🗓️ <b>Следующий бой — {cooldown}.</b>")

    await bot.send_message(chat_id, "\n".join(lines),
                           reply_markup=start.post_battle_keyboard(), parse_mode="HTML")
    _reset_state(ud)


async def rematch(update, context):
    await intro.daily_battle(update, context)


async def next_guardian(update, context):
    await intro.daily_battle(update, context)


# ------------------------------------------------------------------
# FREE TALK: выбираешь ТОЛЬКО персонажа — Арена всё помнит сама
# ------------------------------------------------------------------

async def freetalk(update, context):
    query = update.callback_query
    await query.answer()
    if context.user_data.get("dialogue"):
        await query.edit_message_text("Сначала закончи текущий разговор (/stop).")
        return

    keyboard = [
        [InlineKeyboardButton(p["name"], callback_data=f"freetalk_pick_{key}")]
        for key, p in PERSONALITIES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])

    await query.edit_message_text(
        "💬 <b>Свободный разговор</b>\n\nС кем хочешь поговорить? Без таймера и без оценки.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def freetalk_pick(update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ud = context.user_data
    personality = query.data.replace("freetalk_pick_", "")
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    language = db.get_user_language(user.id) or ud.get("language") or "english"
    level = db.get_current_level(user.id) or "B1"
    memory = db.get_memory(user.id)
    interests = memory.get("interests") or []
    topic = interests[0] if interests else ""

    opening = await asyncio.to_thread(ai.generate_freetalk_opening,
                                      personality, memory, language, level, user.first_name or "")

    ud.update({
        "personality": personality,
        "language": language,
        "level": level,
        "topic": topic,
        "mission": None,
        "mission_weapons": "",
        "used_weapons": [],
        "battle_type": "free_talk",
        "dialogue": [],
        "awaiting_response": True,
    })

    ui = _ui(language)
    await context.bot.send_message(
        update.effective_chat.id,
        f"💬 {esc(ui['ft_start'].format(name=person['short_name']))}\n\n"
        f"<b>{esc(person['name'])}:</b> <i>{esc(opening)}</i>",
        parse_mode="HTML",
    )
    await voice.maybe_reply_voice(update, context, opening, personality)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
    elif context.user_data.get("awaiting_response"):
        await handle_response(update, context)
    else:
        await update.message.reply_text(
            "Нет активной игры. Нажми «⚔️ Battle» или «🏛️ Арена»."
        )
