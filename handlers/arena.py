import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import CHECKPOINT_TURNS
from game_data import LANGUAGES, LEVELS, PERSONALITIES, BADGES, PERSONALITY_COMMENTS

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_words",
    "dialogue", "turn", "awaiting_topic", "awaiting_response", "asked_continue",
]


def _reset_state(context: ContextTypes.DEFAULT_TYPE):
    for key in STATE_KEYS:
        context.user_data.pop(key, None)


# ---------- Выбор языка / уровня / темы ----------

async def play_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Точка входа в игру — и по команде /play, и по кнопке 'Играть'."""
    _reset_state(context)
    keyboard = [
        [InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"debate_lang_{key}")]
        for key, data in LANGUAGES.items()
    ]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])
    text = (
        "🎯 <b>ARENA 2.0 ARENA</b>\n\n"
        "Выбери язык для игры.\n\n"
        "💡 <i>Подстрою словарь, уровень сложности и стиль вопросов под тебя.</i>\n"
        "⚔️ <i>Игру можно завершить в любой момент командой /stop</i>"
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
    language = query.data.replace("debate_lang_", "")
    context.user_data["language"] = language

    lang = LANGUAGES.get(language, {})
    keyboard = [[InlineKeyboardButton(lvl, callback_data=f"debate_level_{lvl}")] for lvl in LEVELS]
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_play")])

    await query.edit_message_text(
        f"🌍 <b>Язык:</b> {lang.get('flag', '')} {lang.get('name', language)}\n\n"
        f"📊 <b>Выбери свой уровень:</b>",
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
        f"📊 <b>Уровень:</b> {level}\n\n✏️ <b>Напиши любую тему</b>, которую хочешь обсудить.",
        parse_mode="HTML",
    )


async def handle_topic_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = update.message.text.strip()
    if len(topic) < 3:
        await update.message.reply_text("❌ Тема слишком короткая. Напиши что-то более содержательное.")
        return

    context.user_data["topic"] = topic
    context.user_data.pop("awaiting_topic", None)

    keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"debate_personality_{key}")]
                for key, p in PERSONALITIES.items()]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])

    await update.message.reply_text(
        f"📚 <b>Тема:</b> {topic}\n\n🎭 <b>Выбери персонажа</b> для игры:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


# ---------- Карточка персонажа и старт ----------

async def select_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("debate_personality_", "")
    context.user_data["personality"] = personality

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "english")

    await query.edit_message_text("🎭 Готовлю персонажа...", parse_mode="HTML")
    mission_words = await asyncio.to_thread(ai.generate_mission_words, topic, level, language)
    context.user_data["mission_words"] = mission_words

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ ДЕБАТЫ", callback_data="debate_start")]])
    await query.edit_message_text(
        f"🎭 <b>ТВОЙ ПРОТИВНИК</b>\n\n"
        f"<b>{person['name']}</b>\n"
        f"<i>{person['desc']}</i>\n\n"
        f"📝 <b>Стиль:</b> {person['style']}\n"
        f"💬 <b>Фирменная фраза:</b> \"{person['phrase']}\"\n\n"
        f"📚 <b>Тема:</b> {topic}\n"
        f"📊 <b>Уровень:</b> {level}\n\n"
        f"💡 <b>Твоя задача:</b>\n"
        f"• Вырази свою точку зрения на утверждение\n"
        f"• Используй 3 слова по теме: <b>{mission_words}</b>\n"
        f"• Каждый раунд — твой ответ и реакция противника\n"
        f"⚔️ <i>Нажми «Начать дебаты», когда будешь готов!</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def start_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚔️ Игра начинается! Генерирую первое утверждение...")

    language = context.user_data.get("language", "english")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")

    context.user_data["turn"] = 0
    context.user_data["dialogue"] = []
    context.user_data["awaiting_response"] = True

    statement = await asyncio.to_thread(ai.generate_opening_statement, personality, topic, level, language)
    context.user_data["dialogue"].append({"speaker": "AI", "text": statement})

    person = PERSONALITIES.get(personality, {})
    await query.message.reply_text(
        f"💬 <b>Раунд 1</b>\n\n"
        f"<b>{person.get('name', personality)}:</b>\n<i>{statement}</i>\n\n"
        f"🎤 <b>Твой ответ</b> — просто напиши сообщение.\n"
        f"<i>Чтобы завершить раньше, отправь /stop</i>",
        parse_mode="HTML",
    )


# ---------- Игровой цикл ----------

async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if len(user_text) < 2:
        await update.message.reply_text("❌ Ответ слишком короткий. Напиши что-то содержательное.")
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
    language = context.user_data.get("language", "english")

    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(f"{'Ты' if d['speaker'] == 'User' else 'AI'}: {d['text']}" for d in dialogue)

    ai_reply = await asyncio.to_thread(
        ai.generate_ai_response, personality, history, last_user, level, language
    )
    dialogue.append({"speaker": "AI", "text": ai_reply})
    context.user_data["awaiting_response"] = True

    person = PERSONALITIES.get(personality, {})
    await update.message.reply_text(
        f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
        f"💬 <i>Напиши ответ или /stop, чтобы завершить</i>",
        parse_mode="HTML",
    )


async def _ask_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["asked_continue"] = True
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить", callback_data="continue_yes")],
        [InlineKeyboardButton("🏁 Завершить и получить фидбэк", callback_data="continue_no")],
    ])
    await update.message.reply_text(
        f"⏸️ Ты уже прошёл {CHECKPOINT_TURNS} раундов! Продолжаем или подводим итоги?",
        reply_markup=keyboard,
    )


async def continue_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["asked_continue"] = False
    context.user_data["awaiting_response"] = True
    await query.edit_message_text("▶️ Продолжаем! Пиши следующий ответ.")


async def continue_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🏁 Завершаем раунд, считаю результаты...")
    await finish_arena(update, context, via_callback=True)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("dialogue"):
        await update.message.reply_text("Сейчас нет активной игры. Нажми «🎮 Играть», чтобы начать.")
        return
    await update.message.reply_text("🏁 Игра завершена по твоей команде! Считаю результаты...")
    await finish_arena(update, context, via_callback=False)


# ---------- Финал: анализ, баллы, достижения ----------

async def finish_arena(update: Update, context: ContextTypes.DEFAULT_TYPE, via_callback: bool):
    user = update.effective_user
    dialogue = context.user_data.get("dialogue", [])
    language = context.user_data.get("language", "english")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")
    mission_words = context.user_data.get("mission_words", "")

    send = update.callback_query.message.reply_text if via_callback else update.message.reply_text

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    if not user_responses:
        await send("❌ Ты не успел ничего сказать. Попробуй снова через «🎮 Играть».")
        _reset_state(context)
        return

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    await send(
        f"🥊 ДЕБАТЫ ЗАВЕРШЕНЫ!\n\n"
        f"📊 Язык: {LANGUAGES.get(language, {}).get('name', language)}\n"
        f"📚 Тема: {topic}\n"
        f"🎭 Противник: {person['full_name']}\n"
        f"💬 Ответов: {len(user_responses)}\n\n"
        f"📝 Анализирую...",
        parse_mode="HTML",
    )

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue, topic, level, language, personality, mission_words
    )
    scores = analysis["scores"]
    rounds_completed = len(user_responses)

    # --- Геймификация Arena 2.0 (баллы/уровни/достижения) ---
    points_earned = gamification.calculate_points(rounds_completed, scores)
    db.save_game_session(user.id, personality, language, level, topic, rounds_completed, scores, points_earned)
    db.add_points(user.id, points_earned)
    new_badges = gamification.check_and_unlock_achievements(user.id, personality, rounds_completed, scores)

    # --- Уровень (реальный vs заявленный) ---
    level_text = f"\n{analysis['level_emoji']} УРОВЕНЬ {level}"
    detected_level = analysis["detected_level"]
    if detected_level != level:
        level_text += f"\n📊 Реальный уровень: {detected_level}"
    if detected_level == level:
        level_text += "\n🔥 Твой уровень полностью соответствует заявленному!"
    elif level in ("A1", "A2"):
        level_text += "\n🌱 Ты на старте! Главное — не бояться говорить!"
    elif level in ("B1", "B2"):
        level_text += "\n💪 Ты молодец! Добавляй больше объяснений: because, for example."
    else:
        level_text += "\n🧠 Сосредоточься на сложных конструкциях и идиомах."

    personality_comment = PERSONALITY_COMMENTS.get(personality, "Отличный бой! Жду тебя снова!")

    # --- Полный фидбэк — формат перенесён 1:1 из старого бота ---
    feedback_text = f"""
🏟️ ВЫВОД АРЕНЫ

📊 ТВОИ ПОКАЗАТЕЛИ
🧠 АРГУМЕНТАЦИЯ — {int(scores['argumentation'])}% — {analysis['arg_desc']}
📚 СЛОВАРНЫЙ ЗАПАС — {int(scores['vocabulary'])}% — {analysis['vocab_text']}
📝 ГРАММАТИКА — {int(scores['grammar'])}% — {analysis['grammar_text']}
🎤 БЕГЛОСТЬ — {int(scores['fluency'])}% — речь {'плавная' if scores['fluency'] > 60 else 'уверенная'}
❓ ВОВЛЕЧЕННОСТЬ — {analysis['questions']} вопросов
📝 ВСЕГО СЛОВ — {analysis['total_words']}
{analysis['mission_display']}

{level_text}

📝 ДЕТАЛИ ПО ГРАММАТИКЕ
{analysis['grammar_report']}

{analysis['psychology_text']}

{analysis['moment_text']}

🔗 СВЯЗКИ ДЛЯ ТВОЕГО УРОВНЯ
{analysis['linking_phrases_display']}

💎 УКРАДИ ЭТУ ФРАЗУ

{analysis['unique_phrase']}

👑 СЛОВО {person['name'].upper()}
{personality_comment}

⭐ <b>+{points_earned} баллов Arena 2.0</b>
"""
    if new_badges:
        names = ", ".join(BADGES[b]["name"] for b in new_badges if b in BADGES)
        feedback_text += f"\n🎉 Новые достижения: {names}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Играть снова", callback_data="menu_play")],
        [InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")],
    ])
    await send(feedback_text, reply_markup=keyboard, parse_mode="HTML")
    _reset_state(context)


# ---------- Диспетчер текстовых сообщений ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Единая точка входа для обычных текстовых сообщений — маршрутизирует по состоянию игры."""
    if context.user_data.get("awaiting_topic"):
        await handle_topic_input(update, context)
    elif context.user_data.get("awaiting_response"):
        await handle_response(update, context)
    # иначе — вне игрового потока, молча игнорируем (или можно подсказать нажать /start)
