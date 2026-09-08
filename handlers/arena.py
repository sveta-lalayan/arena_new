import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import CHECKPOINT_TURNS, BATTLE_DURATION_MINUTES
from game_data import LANGUAGES, LEVELS, PERSONALITIES, BADGES
from handlers import intro

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_weapons", "used_weapons",
    "mission", "win_condition", "dialogue", "turn",
    "awaiting_topic", "awaiting_response", "asked_continue", "battle_type",
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


def format_weapons_status(weapons: str, user_text: str, used_weapons: list) -> tuple:
    """Подсвечивает ✅/⬜ те слова/фразы-оружие, которые уже использованы."""
    if not weapons:
        return "", 0, used_weapons

    items = [w.strip() for w in weapons.replace("·", "|").split("|") if w.strip()]
    new_used = used_weapons.copy()
    user_lower = user_text.lower()

    for item in items:
        key = item.lower()
        if key in user_lower and key not in new_used:
            new_used.append(key)

    status_lines = ["🗡️ <b>Оружие:</b>"]
    for item in items:
        mark = "✅" if item.lower() in user_lower else "⬜"
        status_lines.append(f"  {mark} {item}")

    return "\n".join(status_lines), len(new_used), new_used


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
    """Карточка персонажа: задание + оружие по уровню — общая для обычного
    выбора (select_personality) и реванша (rematch)."""
    query = update.callback_query
    context.user_data["personality"] = personality

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "English")
    user_name = update.effective_user.first_name or ""

    await query.edit_message_text("🎭 Готовлю персонажа...", parse_mode="HTML")

    task = await asyncio.to_thread(ai.generate_mission_task, topic, personality, user_name, language)
    weapons, _, win_condition = await asyncio.to_thread(
        ai.generate_weapons_by_level, topic, level, personality, language
    )

    context.user_data["mission"] = task
    context.user_data["mission_weapons"] = weapons
    context.user_data["win_condition"] = win_condition
    context.user_data["used_weapons"] = []

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ", callback_data="debate_start")]])
    await query.edit_message_text(
        f"🎭 <b>{person['name']}</b>\n<i>{person['desc']}</i>\n\n"
        f"🎯 <b>Задание:</b> {task}\n\n"
        f"🗡️ <b>Оружие:</b> {weapons}\n\n"
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

    language = context.user_data.get("language", "English")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")

    context.user_data["turn"] = 0
    context.user_data["dialogue"] = []
    context.user_data["awaiting_response"] = True
    context.user_data["used_weapons"] = []

    statement = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)
    context.user_data["dialogue"].append({"speaker": "AI", "text": statement})

    person = PERSONALITIES.get(personality, {})
    await query.message.reply_text(
        f"💬 <b>{person.get('name', personality)}:</b>\n<i>{statement}</i>\n\n"
        f"🎤 Напиши ответ!\n⏰ {BATTLE_DURATION_MINUTES} мин",
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

    if context.user_data.get("battle_type") != "free_talk":
        if user_turns % CHECKPOINT_TURNS == 0 and not context.user_data.get("asked_continue"):
            await _ask_continue(update, context)
            return

    await _continue_round(update, context)


async def _continue_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dialogue = context.user_data["dialogue"]
    personality = context.user_data.get("personality", "devil_advocate")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "English")
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
    context.user_data["used_weapons"] = updated_used

    await update.message.reply_text(
        f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
        f"{weapons_status}\n\n"
        f"💬 Напиши ответ или /stop",
        parse_mode="HTML",
    )


async def _ask_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["asked_continue"] = True
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить", callback_data="continue_yes")],
        [InlineKeyboardButton("🏁 Завершить", callback_data="continue_no")],
    ])
    await update.message.reply_text(f"⏸️ Ты прошёл {CHECKPOINT_TURNS} раундов! Продолжаем?", reply_markup=keyboard)


async def continue_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["asked_continue"] = False
    context.user_data["awaiting_response"] = True

    from bot import start_arena_timer, stop_arena_timer
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    stop_arena_timer(context, user_id)
    start_arena_timer(context, user_id, chat_id, minutes=BATTLE_DURATION_MINUTES)

    await query.edit_message_text("▶️ Продолжаем!")


async def continue_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏁 Завершаем...")
    await finish_arena(update, context, via_callback=True)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("dialogue"):
        await update.message.reply_text("Нет активной игры.")
        return
    await update.message.reply_text("🏁 Завершаем...")
    await finish_arena(update, context, via_callback=False)


async def finish_arena(update: Update, context: ContextTypes.DEFAULT_TYPE, via_callback: bool):
    from bot import stop_arena_timer

    user = update.effective_user
    user_name = user.first_name or ""
    stop_arena_timer(context, user.id)

    dialogue = context.user_data.get("dialogue", [])
    language = context.user_data.get("language", "English")
    level = context.user_data.get("level", "B1")
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

    # ===== СВОБОДНЫЙ РАЗГОВОР: без оценки, без баллов =====
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

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue, topic, level, language, personality, weapons
    )
    scores = analysis["scores"]
    rounds_completed = len(user_responses)

    # ===== Живой вердикт судьи (тёплый тон, обращение по имени) =====
    verdict = await asyncio.to_thread(ai.generate_arena_verdict, user_responses, user_name, language)

    # ===== Сильная сторона / зона роста из очков + план на 10 раундов =====
    best_key = max(scores, key=scores.get)
    worst_key = min(scores, key=scores.get)
    strength_text = SCORE_LABELS.get(best_key, best_key)
    growth_text = SCORE_LABELS.get(worst_key, worst_key)
    growth_plan = await asyncio.to_thread(ai.generate_growth_plan, user_name, strength_text, growth_text, language)

    # ===== Слова, использованные неправильно — в личный словарь =====
    mistakes = await asyncio.to_thread(ai.extract_vocabulary_mistakes, user_responses, language)
    if mistakes:
        db.add_vocabulary_mistakes(user.id, mistakes)

    points_earned = gamification.calculate_points(rounds_completed, scores)
    db.save_game_session(
        user.id, personality, language, level, topic, rounds_completed, scores, points_earned,
        strength=strength_text, growth=growth_text, growth_plan=growth_plan,
    )
    db.add_points(user.id, points_earned)
    db.mark_first_battle_done(user.id)
    new_badges = gamification.check_and_unlock_achievements(user.id, personality, rounds_completed, scores)

    weapons_status, _, _ = format_weapons_status(weapons, " ".join(user_responses), used_weapons)

    mistakes_block = ""
    if mistakes:
        mistakes_lines = "\n".join(f"  • {m['wrong']} → <b>{m['correct']}</b>" for m in mistakes[:5])
        mistakes_block = f"\n📚 <b>Слова для заучивания:</b>\n{mistakes_lines}\n"

    feedback_text = f"""
🏟️ <b>{verdict}</b>

{weapons_status}
{mistakes_block}
🗺️ <b>План на следующие 10 раундов:</b>
{growth_plan}

⭐ <b>+{points_earned} баллов</b>
"""

    if new_badges:
        names = ", ".join(BADGES.get(b, {}).get("name", b) for b in new_badges if b in BADGES)
        feedback_text += f"\n🎉 Новые достижения: {names}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Реванш", callback_data=f"rematch_{personality}")],
        [InlineKeyboardButton("💬 Свободный разговор", callback_data="freetalk")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
    ])
    await send(feedback_text, reply_markup=keyboard, parse_mode="HTML")
    _reset_state(context)


async def rematch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("rematch_", "")
    context.user_data["personality"] = personality
    await _show_personality_card(update, context, personality)


# ---------- Свободный разговор: выбор персонажа + любая тема ----------

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
    context.user_data["level"] = context.user_data.get("level", "B1")
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