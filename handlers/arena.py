import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import CHECKPOINT_TURNS, BATTLE_DURATION_MINUTES
from game_data import LANGUAGES, LEVELS, PERSONALITIES, BADGES, PERSONALITY_COMMENTS
from handlers import intro

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_words", "mission",
    "dialogue", "turn", "awaiting_topic", "awaiting_response", "asked_continue",
]


def _reset_state(context: ContextTypes.DEFAULT_TYPE):
    for key in STATE_KEYS:
        context.user_data.pop(key, None)


def format_words_status(mission_words: str, user_text: str, used_words: list) -> tuple:
    if not mission_words:
        return "📚 Слова не заданы", 0, used_words

    words = [w.strip() for w in mission_words.split(",")]
    new_used = used_words.copy()

    for word_item in words:
        word = word_item.split(":")[0].strip().lower() if ":" in word_item else word_item.lower()
        if word in user_text.lower() and word not in new_used:
            new_used.append(word)

    used_count = len(new_used)
    total_count = len(words)

    status_lines = ["📚 <b>Слова:</b>"]
    for w in words:
        w_clean = w.split(":")[0].strip() if ":" in w else w
        mark = "✅" if w_clean.lower() in user_text.lower() else "⬜"
        status_lines.append(f"  {mark} {w}")

    status_text = "\n".join(status_lines)
    return status_text, used_count, new_used


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
        f"🌍 <b>Язык:</b> {LANGUAGES.get(language, {}).get('name', language)}\n\n"
        f"📊 <b>Выбери уровень:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def select_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.replace("debate_level_", "")
    context.user_data["level"] = level
    context.user_data["awaiting_topic"] = True

    await query.edit_message_text(
        f"📊 <b>Уровень:</b> {level}\n\n✏️ <b>Напиши тему</b>",
        parse_mode="HTML",
    )


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
    """Общая логика показа карточки персонажа — используется и при обычном
    выборе (select_personality), и при реванше (rematch), чтобы не парсить
    callback_data дважды в разных форматах."""
    query = update.callback_query
    context.user_data["personality"] = personality

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "English")

    # ===== МИССИЯ: то, что персонаж должен помнить весь бой =====
    context.user_data["mission"] = f"Убедить {person['name']} в том, что «{topic}» — это важно и заслуживает внимания."

    await query.edit_message_text("🎭 Готовлю персонажа...", parse_mode="HTML")

    mission_words = await asyncio.to_thread(ai.generate_mission_words, topic, level, language)
    context.user_data["mission_words"] = mission_words

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ", callback_data="debate_start")]])
    await query.edit_message_text(
        f"🎭 <b>{person['name']}</b>\n"
        f"<i>{person['desc']}</i>\n\n"
        f"📚 <b>Тема:</b> {topic}\n"
        f"📊 <b>Уровень:</b> {level}\n\n"
        f"💡 <b>Слова:</b>\n{mission_words}\n\n"
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
    context.user_data["used_words"] = []

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

    if user_turns % CHECKPOINT_TURNS == 0 and not context.user_data.get("asked_continue"):
        await _ask_continue(update, context)
        return

    await _continue_round(update, context)


async def _continue_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dialogue = context.user_data["dialogue"]
    personality = context.user_data.get("personality", "devil_advocate")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "English")
    mission_words = context.user_data.get("mission_words", "")
    mission = context.user_data.get("mission")
    used_words = context.user_data.get("used_words", [])

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text_full = " ".join(user_responses)

    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(f"{'Ты' if d['speaker'] == 'User' else 'AI'}: {d['text']}" for d in dialogue)

    # mission передаётся в КАЖДЫЙ вызов — это и есть "память о миссии"
    ai_reply = await asyncio.to_thread(
        ai.generate_ai_response, personality, history, last_user, level, language, mission
    )
    dialogue.append({"speaker": "AI", "text": ai_reply})
    context.user_data["awaiting_response"] = True

    # --- Показываем статус слов ---
    words_status, used_count, updated_used = format_words_status(mission_words, user_text_full, used_words)
    context.user_data["used_words"] = updated_used

    person = PERSONALITIES.get(personality, {})
    await update.message.reply_text(
        f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
        f"{words_status}\n\n"
        f"💬 Напиши ответ или /stop",
        parse_mode="HTML",
    )


async def _ask_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["asked_continue"] = True
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить", callback_data="continue_yes")],
        [InlineKeyboardButton("🏁 Завершить", callback_data="continue_no")],
    ])
    await update.message.reply_text(
        f"⏸️ Ты прошёл {CHECKPOINT_TURNS} раундов! Продолжаем?",
        reply_markup=keyboard,
    )


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
    stop_arena_timer(context, user.id)

    dialogue = context.user_data.get("dialogue", [])
    language = context.user_data.get("language", "English")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")
    mission_words = context.user_data.get("mission_words", "")
    used_words = context.user_data.get("used_words", [])

    send = update.callback_query.message.reply_text if via_callback else update.message.reply_text

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    if not user_responses:
        await send("❌ Ты ничего не сказал.")
        _reset_state(context)
        return

    await send(f"📝 {user.first_name}, подвожу итоги...")

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue, topic, level, language, personality, mission_words
    )
    scores = analysis["scores"]
    rounds_completed = len(user_responses)

    points_earned = gamification.calculate_points(rounds_completed, scores)
    db.save_game_session(user.id, personality, language, level, topic, rounds_completed, scores, points_earned)
    db.add_points(user.id, points_earned)
    new_badges = gamification.check_and_unlock_achievements(user.id, personality, rounds_completed, scores)

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    # --- Статус слов ---
    total_words = len(mission_words.split(",")) if mission_words else 0
    used_count = len(used_words)
    words_status, _, _ = format_words_status(mission_words, " ".join(user_responses), used_words)

    # ===== АКЦЕНТ РАЗБОРА ПО УРОВНЮ =====
    # Новичкам (A1/A2) важнее всего словарный запас (использовал ли ключевые слова).
    # Среднему уровню (B1/B2) — ещё и грамматика.
    # Продвинутым (C1/C2) — акцент на убедительность/аргументацию.
    if level in ("A1", "A2"):
        level_emphasis = (
            f"📚 На твоём уровне сейчас важнее всего <b>словарный запас</b>: "
            f"ты использовал {used_count} из {total_words} ключевых слов."
        )
    elif level in ("B1", "B2"):
        level_emphasis = (
            f"📝 На твоём уровне важны <b>грамматика</b> ({int(scores['grammar'])}%) "
            f"и словарный запас ({int(scores['vocabulary'])}%)."
        )
    else:
        level_emphasis = (
            f"⚔️ На твоём уровне мы смотрим на <b>умение убеждать</b>: "
            f"аргументация {int(scores['argumentation'])}%, беглость {int(scores['fluency'])}%."
        )

    feedback_text = f"""
🏟️ <b>ВЕРДИКТ АРЕНЫ</b>

{level_emphasis}

📊 <b>ТВОИ ПОКАЗАТЕЛИ</b>
🧠 Аргументация — {int(scores['argumentation'])}%
📚 Словарный запас — {int(scores['vocabulary'])}%
📝 Грамматика — {int(scores['grammar'])}%
🎤 Беглость — {int(scores['fluency'])}%

{analysis.get('moment_text', '')}

💎 <b>Укради эту фразу</b>
{analysis.get('unique_phrase', 'Используй больше связок.')}

{words_status}

👑 <b>{person['name'].upper()}</b>
{PERSONALITY_COMMENTS.get(personality, 'Отличный бой!')}

⭐ <b>+{points_earned} баллов</b>
"""

    if new_badges:
        names = ", ".join(BADGES.get(b, {}).get("name", b) for b in new_badges if b in BADGES)
        feedback_text += f"\n🎉 Новые достижения: {names}"

    context.user_data["last_personality"] = personality

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Реванш", callback_data=f"rematch_{personality}")],
        [InlineKeyboardButton("🎭 Другой персонаж", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
    ])
    await send(feedback_text, reply_markup=keyboard, parse_mode="HTML")
    _reset_state(context)


async def rematch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("rematch_", "")
    # используем то же topic/level/language, что были в прошлом бою с этим персонажем
    context.user_data["personality"] = personality
    await _show_personality_card(update, context, personality)


async def freetalk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💬 Свободный разговор — скоро!")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
    elif context.user_data.get("awaiting_topic"):
        await handle_topic_input(update, context)
    elif context.user_data.get("awaiting_response"):
        await handle_response(update, context)
    else:
        await update.message.reply_text(
            "Нет активной игры. Нажми «🎮 Играть» или «🏛️ ENTER ARENA»."
        )