import asyncio
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import (
    BATTLE_DURATION_MINUTES, BATTLE_MAX_ROUNDS,
    CONVICTION_WIN_THRESHOLD,
)
from game_data import (
    LANGUAGES, LEVELS, PERSONALITIES, BADGES, ARENA_BEHAVIOURS,
    PERSONALITY_TO_SKILL, SKILL_TO_PERSONALITY, BEGINNER_LEVELS,
)
from handlers import intro

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_weapons", "mission_tip",
    "used_weapons", "mission", "win_condition", "dialogue", "turn",
    "awaiting_topic", "awaiting_response", "asked_continue", "battle_type",
    "arena_analysis", "conviction", "quest_done",
]

SCORE_LABELS = {
    "argumentation": "аргументация",
    "vocabulary": "словарный запас",
    "grammar": "грамматика",
    "fluency": "беглость",
}


def _reset_state(context: ContextTypes.DEFAULT_TYPE):
    for key in STATE_KEYS:
        context.user_data.pop(key, None)


def _get_weak_areas(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> dict:
    """
    Достаёт разбор Храма (языковые/коммуникационные слабые места) — сначала
    из user_data этой сессии, иначе из последнего сохранённого в БД. Всё
    построение "оружия" и советов опирается именно на эти данные.
    """
    analysis = context.user_data.get("arena_analysis")
    if not analysis:
        analysis = db.get_latest_arena_analysis(telegram_id)
    return analysis or {}


def format_weapons_status(weapons: str, user_text: str, used_weapons: list) -> tuple:
    if not weapons:
        return "", 0, used_weapons

    items = [w.strip() for w in weapons.replace("·", "|").split("|") if w.strip()]
    new_used = used_weapons.copy()
    user_lower = user_text.lower()

    for item in items:
        key = item.lower()
        if key in user_lower and key not in new_used:
            new_used.append(key)

    status_lines = ["🗡️ <b>Арсенал:</b>"]
    for item in items:
        mark = "✅" if item.lower() in user_lower else "⬜"
        status_lines.append(f"  {mark} {item}")

    return "\n".join(status_lines), len(new_used), new_used


def _bar(v: int) -> str:
    filled = int(round(max(0, min(100, v)) / 10))
    return "█" * filled + "░" * (10 - filled)


def _format_analysis_block(analysis: dict) -> str:
    if not analysis:
        return ""

    lang = analysis.get("language", {}) or {}
    comm = analysis.get("communication", {}) or {}
    rank = analysis.get("arena_rank", {}) or {}
    behaviour = analysis.get("behaviour", "")

    lines = ["\n📊 <b>Твой профиль ARENA</b>"]

    if lang:
        lines.append("<b>LANGUAGE</b>")
        for k, v in lang.items():
            lines.append(f"  {k.capitalize():<12} {_bar(v)} {v}")

    if comm:
        lines.append("<b>COMMUNICATION</b>")
        for k, v in comm.items():
            lines.append(f"  {k.capitalize():<14} {_bar(v)} {v}")

    if rank:
        lines.append(f"\n🏅 <b>ARENA Rank {rank.get('rank','')}: {rank.get('name','')}</b>")
        lines.append(f"   {rank.get('goal','')}")

    if behaviour:
        lines.append(f"\n🎭 <b>Стиль:</b> {ARENA_BEHAVIOURS.get(behaviour, behaviour)}")

    return "\n".join(lines) + "\n"


async def play_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _reset_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"debate_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    text = "🎯 <b>ARENA</b>\n\nВыбери язык."
    markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    language = query.data.replace("debate_lang_", "")
    context.user_data["language"] = language

    keyboard = [[InlineKeyboardButton(lvl, callback_data=f"debate_level_{lvl}")] for lvl in LEVELS]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_play")])

    await query.edit_message_text(
        f"🌍 <b>Язык:</b> {LANGUAGES.get(language, {}).get('name', language)}\n\n📊 <b>Выбери уровень:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.replace("debate_level_", "")
    context.user_data["level"] = level
    context.user_data["awaiting_topic"] = True

    await query.edit_message_text(f"📊 <b>Уровень:</b> {level}\n\n✏️ <b>Напиши тему</b>", parse_mode="HTML")


async def handle_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    if len(topic) < 3:
        await update.message.reply_text("❌ Тема слишком короткая.")
        return

    context.user_data["topic"] = topic
    context.user_data.pop("awaiting_topic", None)

    keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"debate_personality_{key}")]
                for key, p in PERSONALITIES.items()]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])

    await update.message.reply_text(
        f"📚 <b>Тема:</b> {topic}\n\n🎭 <b>Выбери персонажа:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def _show_personality_card(update: Update, context: ContextTypes.DEFAULT_TYPE, personality: str):
    query = update.callback_query
    context.user_data["personality"] = personality

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    language = context.user_data.get("language", "english")
    user_name = update.effective_user.first_name or ""

    level = (
        context.user_data.get("level")
        or db.get_current_level(update.effective_user.id)
        or "B1"
    )
    context.user_data["level"] = level

    await query.edit_message_text("🎭 Готовлю персонажа...", parse_mode="HTML")

    # Всё оружие и совет строятся на слабых местах пользователя (разбор Храма),
    # если он уже есть — иначе просто по теме и уровню.
    weak_areas = _get_weak_areas(context, update.effective_user.id)
    weakest_skill = weak_areas.get("weakest_skill")

    task = await asyncio.to_thread(ai.generate_mission_task, topic, personality, user_name, language)
    weapons, tip, win_condition = await asyncio.to_thread(
        ai.generate_mission_weapons, topic, level, personality, language, weak_areas, weakest_skill
    )

    context.user_data["mission"] = task
    context.user_data["mission_weapons"] = weapons
    context.user_data["mission_tip"] = tip
    context.user_data["win_condition"] = win_condition
    context.user_data["used_weapons"] = []

    is_beginner = level in BEGINNER_LEVELS
    weapon_label = "🗡️ <b>Твоё оружие (слова):</b>" if is_beginner else "🗡️ <b>Арсенал:</b>"
    tip_block = f"\n💡 <b>Совет:</b> {tip}\n" if tip else ""

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ", callback_data="debate_start")]])
    await query.edit_message_text(
        f"🎭 <b>{person['name']}</b>\n<i>{person['desc']}</i>\n\n"
        f"🎯 <b>Задание:</b> {task}\n\n"
        f"{weapon_label} {weapons}\n"
        f"{tip_block}\n"
        f"✅ <b>Условие победы:</b>\n{win_condition}\n\n"
        f"⚔️ <i>Нажми «Начать»!</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def select_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("debate_personality_", "")
    await _show_personality_card(update, context, personality)


async def start_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚔️ Битва начинается!")

    from bot import start_arena_timer
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    start_arena_timer(context, user_id, chat_id, minutes=BATTLE_DURATION_MINUTES)

    language = context.user_data.get("language", "english")
    level = (
        context.user_data.get("level")
        or db.get_current_level(user_id)
        or "B1"
    )
    context.user_data["level"] = level
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")

    context.user_data["turn"] = 0
    context.user_data["dialogue"] = []
    context.user_data["awaiting_response"] = True
    context.user_data["used_weapons"] = []
    context.user_data["conviction"] = 100

    statement = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)
    context.user_data["dialogue"].append({"speaker": "AI", "text": statement})

    tip = context.user_data.get("mission_tip", "")
    tip_line = f"\n💡 <i>{tip}</i>\n" if tip else ""

    person = PERSONALITIES.get(personality, {})
    await query.message.reply_text(
        f"💬 <b>{person.get('name', personality)}:</b>\n<i>{statement}</i>\n"
        f"{tip_line}\n"
        f"🎤 Напиши ответ! ({BATTLE_MAX_ROUNDS} раунда)\n⏰ {BATTLE_DURATION_MINUTES} мин",
        parse_mode="HTML",
    )


async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if len(user_text) < 2:
        await update.message.reply_text("❌ Слишком коротко.")
        return

    dialogue = context.user_data.setdefault("dialogue", [])
    dialogue.append({"speaker": "User", "text": user_text})
    context.user_data["awaiting_response"] = False

    user_turns = sum(1 for d in dialogue if d["speaker"] == "User")

    # Автофиниш после BATTLE_MAX_ROUNDS раундов
    if user_turns >= BATTLE_MAX_ROUNDS:
        await finish_arena(update, context, via_callback=False)
        return

    await _continue_round(update, context)

    # Досрочная победа: если игрок целенаправленно бил по своим слабым
    # местам (использовал оружие) и "убедил" персонажа раньше времени —
    # не заставляем его тянуть до последнего раунда.
    if (
        context.user_data.get("battle_type") != "free_talk"
        and context.user_data.get("dialogue")
        and context.user_data.get("conviction", 100) <= CONVICTION_WIN_THRESHOLD
    ):
        await update.message.reply_text("🏆 Ты убедил его раньше времени! Досрочная победа.")
        await finish_arena(update, context, via_callback=False)


async def _continue_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dialogue = context.user_data["dialogue"]
    personality = context.user_data.get("personality", "devil_advocate")
    language = context.user_data.get("language", "english")

    level = (
        context.user_data.get("level")
        or db.get_current_level(update.effective_user.id)
        or "B1"
    )
    context.user_data["level"] = level

    weapons = context.user_data.get("mission_weapons", "")
    mission = context.user_data.get("mission")
    used_weapons = context.user_data.get("used_weapons", [])
    user_name = update.effective_user.first_name or ""

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text_full = " ".join(user_responses)

    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(f"{'Ты' if d['speaker'] == 'User' else 'AI'}: {d['text']}" for d in dialogue)

    ai_reply = await asyncio.to_thread(
        ai.generate_ai_response, personality, history, last_user, level, language, mission, user_name
    )
    dialogue.append({"speaker": "AI", "text": ai_reply})
    context.user_data["awaiting_response"] = True

    person = PERSONALITIES.get(personality, {})

    if context.user_data.get("battle_type") == "free_talk":
        await update.message.reply_text(
            f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
            f"💬 Напиши ответ или /stop, чтобы закончить",
            parse_mode="HTML",
        )
        return

    weapons_status, used_count, updated_used = format_weapons_status(weapons, user_text_full, used_weapons)
    new_weapon_used = used_count > len(used_weapons)
    context.user_data["used_weapons"] = updated_used

    # Убеждённость падает быстрее, если игрок использует оружие,
    # заточенное под его слабые места (см. ai.generate_mission_weapons),
    # и медленнее — если он просто отвечает без него. Это и есть
    # "победа за несколько раундов, построенная на слабых местах".
    conviction = context.user_data.get("conviction", 100)
    if new_weapon_used:
        conviction = max(0, conviction - 20)
    else:
        conviction = max(0, conviction - 6)
    context.user_data["conviction"] = conviction

    bar = "█" * int((100 - conviction) / 10) + "░" * int(conviction / 10)
    await update.message.reply_text(
        f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
        f"{weapons_status}\n\n"
        f"🔥 Убеждённость: {bar} {conviction}%\n"
        f"💬 Напиши ответ или /stop",
        parse_mode="HTML",
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("dialogue"):
        await update.message.reply_text("Нет активной игры.")
        return
    await update.message.reply_text("🏁 Завершаем...")
    await finish_arena(update, context, via_callback=False)


async def finish_arena(update: Update, context: ContextTypes.DEFAULT_TYPE, via_callback: bool = False):
    from bot import stop_arena_timer

    user = update.effective_user
    user_name = user.first_name or ""
    stop_arena_timer(context, user.id)

    dialogue = context.user_data.get("dialogue", [])
    language = context.user_data.get("language", "english")
    level = (
        context.user_data.get("level")
        or db.get_current_level(user.id)
        or "B1"
    )
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")
    weapons = context.user_data.get("mission_weapons", "")
    used_weapons = context.user_data.get("used_weapons", [])

    send = update.callback_query.message.reply_text if via_callback else update.message.reply_text

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    if not user_responses:
        await send("❌ Ты ничего не сказал.")
        _reset_state(context)
        return

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    # Свободный разговор — без оценки
    if context.user_data.get("battle_type") == "free_talk":
        keyboard_ft = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Свободный разговор ещё раз", callback_data="freetalk")],
            [InlineKeyboardButton("⚔️ Начать бой", callback_data="menu_play")],
            [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
        ])
        await send(f"💬 Разговор с {person['name']} завершён, {user_name}. Баллы не начислялись.",
                   reply_markup=keyboard_ft)
        _reset_state(context)
        return

    await send(f"📝 {user_name}, подвожу итоги...")

    # Квест
    quest = db.get_active_quest(user.id)
    quest_desc = quest["description"] if quest else ""

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue, topic, level, language, personality, weapons, quest_desc
    )
    scores = analysis["scores"]
    rounds_completed = len(user_responses)
    # Итоговая убеждённость — минимум из живой (по ходу боя) и оценённой в
    # конце GPT-анализом: игрок не должен "терять" досрочную победу, если
    # финальный анализ оценит её мягче.
    live_conviction = context.user_data.get("conviction", 100)
    conviction = min(live_conviction, analysis.get("conviction", 70))
    quest_done = analysis.get("quest_done", False)

    verdict = await asyncio.to_thread(ai.generate_arena_verdict, user_responses, user_name, language)

    best_key = max(scores, key=scores.get)
    worst_key = min(scores, key=scores.get)
    strength_text = SCORE_LABELS.get(best_key, best_key)
    growth_text = SCORE_LABELS.get(worst_key, worst_key)
    growth_plan = await asyncio.to_thread(ai.generate_growth_plan, user_name, strength_text, growth_text, language)

    mistakes = await asyncio.to_thread(ai.extract_vocabulary_mistakes, user_responses, language)
    if mistakes:
        db.add_vocabulary_mistakes(user.id, mistakes)

    # Немезида
    nemesis = db.get_nemesis(user.id)
    is_nemesis = bool(nemesis and nemesis["personality"] == personality and not nemesis["defeated"])
    if is_nemesis and conviction <= 30:
        db.mark_nemesis_fought(user.id, defeated=True)

    # Проверка первого боя дня (упрощённо — последняя сессия >24ч)
    stats = db.get_user_stats(user.id)
    is_first_daily = True  # TODO: реализовать проверку по времени последней сессии
    is_new_character = personality not in stats["unique_personalities"]

    # Баллы
    points_earned = gamification.calculate_points(
        rounds_completed, conviction, len(used_weapons), quest_done, len(mistakes),
        is_first_daily, is_new_character, is_nemesis
    )

    # Скилл-прогресс — качаем скилл, за который отвечает ЭТОТ персонаж
    # (PERSONALITY_TO_SKILL), т.к. именно на нём его специально тренировали.
    skill = PERSONALITY_TO_SKILL.get(personality, "argumentation")
    skill_delta = gamification.calculate_skill_delta(conviction, len(used_weapons), quest_done, is_nemesis)
    db.add_skill_progress(user.id, skill, skill_delta)

    db.save_game_session(
        user.id, personality, language, level, topic, rounds_completed, scores, points_earned,
        strength=strength_text, growth=growth_text, growth_plan=growth_plan,
        conviction_final=conviction, quest_done=1 if quest_done else 0,
    )

    # Мягкая адаптация уровня
    avg_recent = db.get_recent_avg_scores(user.id, n=3)
    new_level = gamification.adapt_level(level, avg_recent)
    if new_level != level:
        db.add_level_snapshot(user.id, new_level, source="battle_finish")
        context.user_data["level"] = new_level

    db.add_points(user.id, points_earned)
    db.mark_first_battle_done(user.id)

    # Бейджи
    new_badges = gamification.check_and_unlock_achievements(
        user.id, personality, rounds_completed, scores, conviction, quest_done, mistakes,
        is_nemesis=is_nemesis, is_rematch=False, prev_defeated=False,
    )

    # Квест выполнен?
    if quest_done and quest:
        db.complete_quest(user.id)

    weapons_status, _, _ = format_weapons_status(weapons, " ".join(user_responses), used_weapons)

    mistakes_block = ""
    if mistakes:
        mistakes_lines = "\n".join(f"  • {m['wrong']} → <b>{m['correct']}</b>" for m in mistakes[:5])
        mistakes_block = f"\n📚 <b>Слова для заучивания:</b>\n{mistakes_lines}\n"

    stars, result_text = gamification._conviction_stars(conviction)

    analysis_block = ""
    arena_analysis = context.user_data.get("arena_analysis")
    if not arena_analysis:
        arena_analysis = db.get_latest_arena_analysis(user.id)
    if arena_analysis:
        analysis_block = _format_analysis_block(arena_analysis)

    feedback_text = f"""
🏟️ <b>{verdict}</b>

{stars} <b>{result_text}</b>  (убеждённость перса: {conviction}%)
{analysis_block}
{weapons_status}
{mistakes_block}
🗺️ <b>План развития:</b>
{growth_plan}

⭐ <b>+{points_earned} баллов</b>
⚡ <b>+{skill_delta} к скиллу {skill}</b>
"""

    if quest_done and quest:
        feedback_text += f"\n🎯 <b>Квест выполнен:</b> {quest['description']}\n"

    if new_badges:
        names = ", ".join(BADGES.get(b, {}).get("name", b) for b in new_badges if b in BADGES)
        feedback_text += f"\n🎉 Новые достижения: {names}"

    # Кнопки после боя
    buttons = [
        [InlineKeyboardButton("🔁 Реванш", callback_data=f"rematch_{personality}")],
        [InlineKeyboardButton("💬 Свободный диалог", callback_data="freetalk")],
    ]

    # Следующий хранитель — если скилл достаточно прокачан
    skills = db.get_all_skills(user.id)
    current_skill_data = skills.get(skill, {"points": 0, "rank": 1})
    if current_skill_data["points"] >= 200:
        # Найти следующий слабый скилл
        weakest = min(skills, key=lambda s: skills[s]["points"])
        next_personality = SKILL_TO_PERSONALITY.get(weakest, "devil_advocate")
        next_person = PERSONALITIES.get(next_personality, {})
        buttons.append([InlineKeyboardButton(f"🎯 Следующий хранитель: {next_person.get('name', '')}", callback_data=f"next_guardian_{next_personality}")])

    buttons.append([InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")])

    keyboard = InlineKeyboardMarkup(buttons)
    await send(feedback_text, reply_markup=keyboard, parse_mode="HTML")
    _reset_state(context)


async def rematch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("rematch_", "")
    context.user_data["personality"] = personality
    await _show_personality_card(update, context, personality)


async def next_guardian(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("next_guardian_", "")
    context.user_data["personality"] = personality

    # Берём тему из интересов пользователя
    analysis = db.get_latest_arena_analysis(update.effective_user.id)
    interests = analysis.get("interests", ["интересная тема"]) if analysis else ["интересная тема"]
    topic = random.choice(interests) if interests else "интересная тема"
    context.user_data["topic"] = topic

    await _show_personality_card(update, context, personality)


# ---------- Свободный разговор ----------

async def freetalk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"freetalk_pick_{key}")]
                for key, p in PERSONALITIES.items()]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])

    await query.edit_message_text(
        "💬 <b>Свободный разговор</b>\n\nС кем хочешь поговорить? Без таймера и без оценки.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def freetalk_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("freetalk_pick_", "")
    context.user_data["_freetalk_personality"] = personality
    context.user_data["awaiting_freetalk_topic"] = True

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    await query.edit_message_text(
        f"💬 Ты выбрал <b>{person['name']}</b>.\n\n✏️ На какую тему хочешь поговорить? Напиши тему.",
        parse_mode="HTML",
    )


async def handle_freetalk_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    if len(topic) < 2:
        await update.message.reply_text("❌ Слишком коротко, напиши тему ещё раз.")
        return

    personality = context.user_data.pop("_freetalk_personality", "devil_advocate")
    context.user_data.pop("awaiting_freetalk_topic", None)
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    context.user_data["personality"] = personality
    context.user_data["language"] = context.user_data.get("language", "english")
    context.user_data["level"] = (
        context.user_data.get("level")
        or db.get_current_level(update.effective_user.id)
        or "B1"
    )
    context.user_data["topic"] = topic
    context.user_data["mission"] = None
    context.user_data["mission_weapons"] = ""
    context.user_data["used_weapons"] = []
    context.user_data["battle_type"] = "free_talk"
    context.user_data["dialogue"] = []
    context.user_data["awaiting_response"] = True

    await update.message.reply_text(
        f"💬 <b>Свободный разговор с {person['name']}</b>\nТема: <b>{topic}</b>\n\n"
        f"Без таймера и без оценки — просто поговорите.\n"
        f"Чтобы закончить, напиши /stop.\n\n"
        f"<i>{person.get('phrase', '')}</i>",
        parse_mode="HTML",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
    elif context.user_data.get("awaiting_freetalk_topic"):
        await handle_freetalk_topic_input(update, context)
    elif context.user_data.get("awaiting_topic"):
        await handle_topic_input(update, context)
    elif context.user_data.get("awaiting_response"):
        await handle_response(update, context)
    else:
        await update.message.reply_text(
            "Нет активной игры. Нажми «⚔️ Battle» или «🏛️ ENTER ARENA»."
        )