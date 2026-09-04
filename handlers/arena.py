import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import ai
import database as db
import gamification
from config import CHECKPOINT_TURNS
from game_data import LANGUAGES, LEVELS, PERSONALITIES, BADGES, PERSONALITY_COMMENTS
from handlers import intro

STATE_KEYS = [
    "language", "level", "topic", "personality", "mission_words",
    "dialogue", "turn", "awaiting_topic", "awaiting_response", "asked_continue",
    "case_topic", "tips", "used_words", "word_hint_index"
]


def _reset_state(context: ContextTypes.DEFAULT_TYPE):
    for key in STATE_KEYS:
        context.user_data.pop(key, None)


# ---------- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ФОРМАТИРОВАНИЯ СЛОВ ----------

def format_words_status(mission_words: str, user_text_full: str, used_words: list = None) -> tuple[str, int, list]:
    """
    Форматирует статус слов с определениями.
    Возвращает: (текст_статуса, количество_использованных, список_использованных_слов)
    """
    if not mission_words:
        return "", 0, []

    if used_words is None:
        used_words = []

    # Парсим слова с определениями
    words_list = []
    for item in mission_words.split(","):
        item = item.strip()
        if ":" in item:
            word, definition = item.split(":", 1)
            words_list.append({"word": word.strip(), "definition": definition.strip()})
        else:
            words_list.append({"word": item.strip(), "definition": ""})

    # Проверяем, какие слова использованы
    user_text_lower = user_text_full.lower()
    used_count = 0
    status_lines = ["📋 <b>Слова для использования:</b>"]

    for w in words_list:
        word = w["word"].lower()
        if word in user_text_lower:
            status_lines.append(f"  ✅ <s>{w['word']}</s> — {w['definition']}")
            used_count += 1
            if word not in used_words:
                used_words.append(word)
        else:
            status_lines.append(f"  ⬜ {w['word']} — {w['definition']}")

    status_lines.append(f"\n📊 <b>Прогресс:</b> {used_count}/{len(words_list)}")

    # Находим следующее неиспользованное слово для подсказки
    word_hint = ""
    for w in words_list:
        if w["word"].lower() not in user_text_lower:
            word_hint = f"\n💡 <b>Попробуй использовать:</b> {w['word']} — {w['definition']}"
            break

    return "\n".join(status_lines) + word_hint, used_count, used_words


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
        "🎯 <b>ARENA 2.0</b>\n\n"
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

    # Если персонаж уже рекомендован ARENA — пропускаем выбор
    pre_selected = context.user_data.get("personality")
    if pre_selected and pre_selected in PERSONALITIES:
        await _send_personality_card(update, context, pre_selected)
        return

    keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"debate_personality_{key}")]
                for key, p in PERSONALITIES.items()]
    keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")])

    await update.message.reply_text(
        f"📚 <b>Тема:</b> {topic}\n\n🎭 <b>Выбери персонажа</b> для игры:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )


async def _send_personality_card(update: Update, context: ContextTypes.DEFAULT_TYPE, personality: str):
    """Карточка персонажа с кейсом, словами и лайфхаками"""
    context.user_data["personality"] = personality
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "english")
    interests = context.user_data.get("user_interests", [])

    # Генерируем КЕЙС с темой
    case_topic = await asyncio.to_thread(
        ai.generate_case_topic, personality, level, language, interests
    )
    context.user_data["case_topic"] = case_topic
    context.user_data["tips"] = case_topic.get("tips", [])
    context.user_data["used_words"] = []
    context.user_data["word_hint_index"] = 0

    # Сохраняем слова
    mission_words = ai.generate_mission_words_from_case(case_topic, level)
    context.user_data["mission_words"] = mission_words

    # Формируем отображение слов с определениями
    words_list = []
    for item in mission_words.split(","):
        if ":" in item:
            word, definition = item.split(":", 1)
            words_list.append({"word": word.strip(), "definition": definition.strip()})
        else:
            words_list.append({"word": item.strip(), "definition": ""})

    words_display = "\n".join([f"  • {w['word']} — {w['definition']}" for w in words_list])

    tips_display = "\n".join([f"  • {t}" for t in case_topic.get("tips", [])]) if case_topic.get("tips") else ""
    tips_section = f"\n💡 <b>Лайфхаки:</b>\n{tips_display}" if tips_display else ""

    rules = (
        "\n\n⚔️ <b>Правила:</b>\n"
        "• Отвечай на утверждение соперника\n"
        "• Используй слова из миссии\n"
        "• Аргументируй свою позицию\n"
        "• Победитель определяется по количеству использованных слов"
    )

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ ДЕБАТЫ", callback_data="debate_start")]])

    await update.message.reply_text(
        f"🎭 <b>ТВОЙ ПРОТИВНИК</b>\n\n"
        f"<b>{person['name']}</b>\n"
        f"<i>{person['desc']}</i>\n\n"
        f"📝 <b>Стиль:</b> {person['style']}\n"
        f"💬 <b>Фирменная фраза:</b> \"{person['phrase']}\"\n\n"
        f"📚 <b>Кейс:</b> {case_topic.get('title', '')}\n"
        f"{case_topic.get('description', '')}\n\n"
        f"🎯 <b>Задача:</b>\n{case_topic.get('challenge', 'Убеди персонажа')}\n\n"
        f"📋 <b>Слова для использования:</b>\n{words_display}\n"
        f"{tips_section}\n"
        f"{rules}\n\n"
        f"⚔️ <i>Нажми «Начать дебаты», когда будешь готов!</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def select_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    personality = query.data.replace("debate_personality_", "")
    context.user_data["personality"] = personality

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    topic = context.user_data.get("topic", "")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "english")
    interests = context.user_data.get("user_interests", [])

    await query.edit_message_text("🎭 Готовлю персонажа...", parse_mode="HTML")

    # Генерируем КЕЙС
    case_topic = await asyncio.to_thread(
        ai.generate_case_topic, personality, level, language, interests
    )
    context.user_data["case_topic"] = case_topic
    context.user_data["tips"] = case_topic.get("tips", [])
    context.user_data["used_words"] = []
    context.user_data["word_hint_index"] = 0

    mission_words = ai.generate_mission_words_from_case(case_topic, level)
    context.user_data["mission_words"] = mission_words

    words_list = []
    for item in mission_words.split(","):
        if ":" in item:
            word, definition = item.split(":", 1)
            words_list.append({"word": word.strip(), "definition": definition.strip()})
        else:
            words_list.append({"word": item.strip(), "definition": ""})

    words_display = "\n".join([f"  • {w['word']} — {w['definition']}" for w in words_list])

    tips_display = "\n".join([f"  • {t}" for t in case_topic.get("tips", [])]) if case_topic.get("tips") else ""
    tips_section = f"\n💡 <b>Лайфхаки:</b>\n{tips_display}" if tips_display else ""

    rules = (
        "\n\n⚔️ <b>Правила:</b>\n"
        "• Отвечай на утверждение соперника\n"
        "• Используй слова из миссии\n"
        "• Аргументируй свою позицию\n"
        "• Победитель определяется по количеству использованных слов"
    )

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ НАЧАТЬ ДЕБАТЫ", callback_data="debate_start")]])
    await query.edit_message_text(
        f"🎭 <b>ТВОЙ ПРОТИВНИК</b>\n\n"
        f"<b>{person['name']}</b>\n"
        f"<i>{person['desc']}</i>\n\n"
        f"📝 <b>Стиль:</b> {person['style']}\n"
        f"💬 <b>Фирменная фраза:</b> \"{person['phrase']}\"\n\n"
        f"📚 <b>Кейс:</b> {case_topic.get('title', '')}\n"
        f"{case_topic.get('description', '')}\n\n"
        f"🎯 <b>Задача:</b>\n{case_topic.get('challenge', 'Убеди персонажа')}\n\n"
        f"📋 <b>Слова для использования:</b>\n{words_display}\n"
        f"{tips_section}\n"
        f"{rules}\n\n"
        f"⚔️ <i>Нажми «Начать дебаты», когда будешь готов!</i>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


async def start_arena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⚔️ Игра начинается! Генерирую первое утверждение...")

    user = update.effective_user

    language = context.user_data.get("language", "English")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")
    mission_words = context.user_data.get("mission_words", "")
    case_topic = context.user_data.get("case_topic", {})
    tips = context.user_data.get("tips", [])

    context.user_data["turn"] = 0
    context.user_data["dialogue"] = []
    context.user_data["awaiting_response"] = True
    context.user_data["used_words"] = []

    # Запускаем таймер
    from bot import start_arena_timer
    start_arena_timer(context, user.id, update.effective_chat.id, minutes=2)

    statement = await asyncio.to_thread(
        ai.generate_opening_statement, personality, topic, level, language, case_topic
    )
    context.user_data["dialogue"].append({"speaker": "AI", "text": statement})

    person = PERSONALITIES.get(personality, {})

    # Форматируем статус слов (пока ничего не использовано)
    words_status, used_count, used_words = format_words_status(mission_words, "", [])

    # Лайфхаки
    tips_display = ""
    if tips:
        tips_display = "\n💡 <b>Лайфхаки:</b>\n" + "\n".join([f"  • {t}" for t in tips[:3]])

    rules = (
        "\n\n⚔️ <b>Правила:</b>\n"
        "• Отвечай на утверждение соперника\n"
        "• Используй слова из миссии ✅\n"
        "• Аргументируй свою позицию"
    )

    await query.message.reply_text(
        f"💬 <b>Раунд 1</b>\n\n"
        f"<b>{person.get('name', personality)}:</b>\n<i>{statement}</i>\n\n"
        f"🎤 <b>Твой ответ</b> — просто напиши сообщение.\n"
        f"<i>Чтобы завершить раньше, отправь /stop</i>\n\n"
        f"⏰ <i>У тебя 2 минуты!</i>\n\n"
        f"{words_status}\n"
        f"{tips_display}"
        f"{rules}",
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

    # Проверяем использованные слова и обновляем статус
    mission_words = context.user_data.get("mission_words", "")
    used_words = context.user_data.get("used_words", [])

    if mission_words:
        user_text_full = " ".join([d["text"] for d in dialogue if d["speaker"] == "User"])
        # Проверяем, какие слова использованы
        words_list = []
        for item in mission_words.split(","):
            if ":" in item:
                word = item.split(":", 1)[0].strip().lower()
            else:
                word = item.strip().lower()
            words_list.append(word)

        new_used = []
        for word in words_list:
            if word in user_text_full.lower() and word not in used_words:
                new_used.append(word)

        if new_used:
            used_words.extend(new_used)
            context.user_data["used_words"] = used_words
            # Показываем подтверждение
            used_display = ", ".join([f"✅ {w}" for w in new_used])
            await update.message.reply_text(
                f"📝 <b>Новые слова использованы:</b> {used_display}\n"
                f"📊 <b>Всего использовано:</b> {len(used_words)}/{len(words_list)}",
                parse_mode="HTML"
            )

    if user_turns % CHECKPOINT_TURNS == 0 and not context.user_data.get("asked_continue"):
        await _ask_continue(update, context)
        return

    await _continue_round(update, context)


async def _continue_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dialogue = context.user_data["dialogue"]
    personality = context.user_data.get("personality", "devil_advocate")
    level = context.user_data.get("level", "B1")
    language = context.user_data.get("language", "english")
    mission_words = context.user_data.get("mission_words", "")
    case_topic = context.user_data.get("case_topic", {})
    used_words = context.user_data.get("used_words", [])

    # Получаем все ответы пользователя для проверки слов
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text_full = " ".join(user_responses)

    last_user = next((d["text"] for d in reversed(dialogue) if d["speaker"] == "User"), "")
    history = "\n".join(f"{'Ты' if d['speaker'] == 'User' else 'AI'}: {d['text']}" for d in dialogue)

    ai_reply = await asyncio.to_thread(
        ai.generate_ai_response, personality, history, last_user, level, language, case_topic
    )
    dialogue.append({"speaker": "AI", "text": ai_reply})
    context.user_data["awaiting_response"] = True

    person = PERSONALITIES.get(personality, {})

    # ===== ВСЕГДА ПОКАЗЫВАЕМ СЛОВА =====
    words_status, used_count, updated_used = format_words_status(mission_words, user_text_full, used_words)
    context.user_data["used_words"] = updated_used

    rules = (
        "\n\n⚔️ <b>Правила:</b>\n"
        "• Отвечай на утверждение соперника\n"
        "• Используй слова из миссии ✅\n"
        "• Аргументируй свою позицию"
    )

    # Подсчёт прогресса
    total_words = len(mission_words.split(",")) if mission_words else 0
    progress_text = f"\n🎯 <b>Прогресс:</b> {used_count}/{total_words} слов использовано"

    await update.message.reply_text(
        f"<b>{person.get('name', personality)}:</b>\n<i>{ai_reply}</i>\n\n"
        f"💬 <i>Напиши ответ или /stop, чтобы завершить</i>\n\n"
        f"{words_status}\n"
        f"{progress_text}\n"
        f"{rules}",
        parse_mode="HTML",
    )


async def _ask_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["asked_continue"] = True

    # Показываем текущий прогресс перед вопросом
    mission_words = context.user_data.get("mission_words", "")
    used_words = context.user_data.get("used_words", [])
    total_words = len(mission_words.split(",")) if mission_words else 0

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Продолжить", callback_data="continue_yes")],
        [InlineKeyboardButton("🏁 Завершить и получить фидбэк", callback_data="continue_no")],
    ])
    await update.message.reply_text(
        f"⏸️ Ты уже прошёл {CHECKPOINT_TURNS} раундов!\n"
        f"📊 Использовано слов: {len(used_words)}/{total_words}\n\n"
        f"Продолжаем или подводим итоги?",
        reply_markup=keyboard,
    )


async def continue_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    from bot import start_arena_timer, stop_arena_timer
    user = update.effective_user
    stop_arena_timer(context, user.id)
    start_arena_timer(context, user.id, update.effective_chat.id, minutes=2)

    context.user_data["asked_continue"] = False
    context.user_data["awaiting_response"] = True
    await query.edit_message_text("▶️ Продолжаем! Пиши следующий ответ.")


async def continue_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    from bot import stop_arena_timer
    stop_arena_timer(context, update.effective_user.id)

    await query.edit_message_text("🏁 Завершаем раунд, считаю результаты...")
    await finish_arena(update, context, via_callback=True)


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("dialogue"):
        await update.message.reply_text("Сейчас нет активной игры. Нажми «🎮 Играть», чтобы начать.")
        return

    from bot import stop_arena_timer
    stop_arena_timer(context, update.effective_user.id)

    await update.message.reply_text("🏁 Игра завершена по твоей команде! Считаю результаты...")
    await finish_arena(update, context, via_callback=False)


# ---------- Финал: определение победителя ----------

async def finish_arena(update: Update, context: ContextTypes.DEFAULT_TYPE, via_callback: bool):
    user = update.effective_user
    dialogue = context.user_data.get("dialogue", [])
    language = context.user_data.get("language", "english")
    level = context.user_data.get("level", "B1")
    topic = context.user_data.get("topic", "")
    personality = context.user_data.get("personality", "devil_advocate")
    mission_words = context.user_data.get("mission_words", "")
    used_words = context.user_data.get("used_words", [])

    send = update.callback_query.message.reply_text if via_callback else update.message.reply_text

    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    if not user_responses:
        await send("❌ Ты не успел ничего сказать. Попробуй снова через «🎮 Играть».")
        _reset_state(context)
        return

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])

    # ===== ОПРЕДЕЛЯЕМ ПОБЕДИТЕЛЯ =====
    total_words = len(mission_words.split(",")) if mission_words else 0
    used_count = len(used_words)

    if total_words > 0:
        usage_percentage = (used_count / total_words) * 100
        if usage_percentage >= 80:
            winner = "🏆 ТЫ ПОБЕДИЛ!"
            winner_emoji = "🔥"
            winner_desc = "Ты отлично использовал все слова! Персонаж впечатлён."
        elif usage_percentage >= 50:
            winner = "🤝 НИЧЬЯ!"
            winner_emoji = "⚖️"
            winner_desc = "Хорошая попытка! Нужно использовать больше слов для полной победы."
        else:
            winner = "😈 ПОБЕДИЛ ПЕРСОНАЖ!"
            winner_emoji = "💀"
            winner_desc = "Ты использовал слишком мало слов. В следующий раз используй все!"
    else:
        winner = "🤝 НИЧЬЯ!"
        winner_emoji = "⚖️"
        winner_desc = ""

    await send(
        f"🥊 ДЕБАТЫ ЗАВЕРШЕНЫ!\n\n"
        f"📊 Язык: {LANGUAGES.get(language, {}).get('name', language)}\n"
        f"📚 Тема: {topic}\n"
        f"🎭 Противник: {person['full_name']}\n"
        f"💬 Ответов: {len(user_responses)}\n\n"
        f"{winner_emoji} <b>{winner}</b>\n"
        f"📊 Слов использовано: {used_count}/{total_words}\n"
        f"{winner_desc}\n\n"
        f"📝 Анализирую...",
        parse_mode="HTML",
    )

    analysis = await asyncio.to_thread(
        ai.analyze_debate, user_responses, dialogue, topic, level, language, personality, mission_words
    )
    scores = analysis["scores"]
    rounds_completed = len(user_responses)

    points_earned = gamification.calculate_points(rounds_completed, scores)
    db.save_game_session(user.id, personality, language, level, topic, rounds_completed, scores, points_earned)
    db.add_points(user.id, points_earned)
    new_badges = gamification.check_and_unlock_achievements(user.id, personality, rounds_completed, scores)

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

    from bot import stop_arena_timer
    stop_arena_timer(context, user.id)

    _reset_state(context)


# ---------- Диспетчер ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("fe_awaiting_response"):
        await intro.handle_fe_response(update, context)
    elif context.user_data.get("awaiting_topic"):
        await handle_topic_input(update, context)
    elif context.user_data.get("awaiting_response"):
        await handle_response(update, context)