import re
import logging
import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import LANGUAGES, PERSONALITIES, LEVEL_DESCRIPTIONS, ROLE_STYLE

logger = logging.getLogger(__name__)

GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def ask_gpt(prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str | None:
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        return None

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
        "completionOptions": {"temperature": temperature, "maxTokens": max_tokens},
        "messages": [{"role": "user", "text": prompt}],
    }

    try:
        resp = requests.post(GPT_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()["result"]["alternatives"][0]["message"]["text"]
    except Exception as e:
        logger.error(f"GPT error: {e}")
    return None


# ========== ARENA REACTION (для First Encounter) ==========
# ВАЖНО: move_number используется только ВНУТРИ промпта для ориентации модели.
# Номер хода НИКОГДА не должен попадать в текст, который видит пользователь —
# по этой причине handlers/intro.py не подставляет move_number в reply-текст.

def generate_arena_reaction(dialogue_history: str, last_user_response: str, language: str, move_number: int) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = f"""
    Ты — ARENA. Ты наблюдаешь за человеком и даёшь проницательный комментарий.
    Твой ответ должен быть:
    - коротким (1-2 предложения)
    - живым, как реальный комментарий
    - либо острым наблюдением, либо уточняющим вопросом
    - НЕ давай оценок, НЕ говори "хорошо" или "плохо"
    - НИКОГДА не используй слова "помочь", "assist", "help", "support"
    - Обращайся к собеседнику на "ты"
    - НИКОГДА не упоминай номер хода или счётчик (например "ход 3 из 8")

    Язык: {lang_name}
    Ход (только для твоей ориентации, не упоминай его): {move_number} из 8

    История разговора:
    {dialogue_history}

    Последнее сообщение человека:
    {last_user_response}

    Твой ответ (живой, проницательный, без «I see», без оценки, без номеров ходов):
    """
    response = ask_gpt(prompt, temperature=0.85, max_tokens=150)
    if not response:
        return "Это интересно. Расскажи подробнее."
    return response.strip()


# ========== ОРУЖИЕ ПО УРОВНЯМ ==========

def generate_weapons_by_level(topic: str, level: str, personality: str, language: str) -> tuple:
    """Генерирует слова, фразы и условия победы в зависимости от уровня."""
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    person = PERSONALITIES.get(personality, {})

    level_key = level.upper()

    level_config = {
        "A1": {
            "weapons_prompt": f"Generate 5 simple vocabulary words for debating '{topic}' in {lang_name} for beginner level. Format (separated by · ): word1 · word2 · word3 · word4 · word5",
            "condition": "Make a claim.\nGive a reason.\nUse 3 weapons."
        },
        "A2": {
            "weapons_prompt": f"Generate 5 vocabulary words and 2 basic phrases for debating '{topic}' in {lang_name} for elementary level. Format (separated by · ): word1 · word2 · word3 · word4 · word5 · phrase1 · phrase2",
            "condition": "Make a claim.\nGive a reason.\nSupport it with an example."
        },
        "B1": {
            "weapons_prompt": f"Generate 5 collocations and 3 useful phrases for debating '{topic}' in {lang_name} for intermediate level. Format (separated by · ): collocation1 · collocation2 · collocation3 · collocation4 · collocation5 · phrase1 · phrase2 · phrase3",
            "condition": "Make a claim.\nSupport it with evidence.\nAnswer the objection."
        },
        "B2": {
            "weapons_prompt": f"Generate 5 collocations and 4 natural expressions for debating '{topic}' in {lang_name} for upper-intermediate level. Format (separated by · ): collocation1 · collocation2 · collocation3 · collocation4 · collocation5 · expression1 · expression2 · expression3 · expression4",
            "condition": "Challenge the assumption.\nAdapt your argument.\nGet closer to saying yes."
        },
        "C1": {
            "weapons_prompt": f"Generate 3 nuanced phrases, 2 rhetorical devices, and 2 idioms for debating '{topic}' in {lang_name} for advanced level. Format (separated by · ): nuance1 · nuance2 · nuance3 · rhetoric1 · rhetoric2 · idiom1 · idiom2",
            "condition": "Reframe the objection.\nConcede without giving up position.\nLead toward conclusion."
        },
        "C2": {
            "weapons_prompt": f"Generate 3 nuanced expressions, 2 register variations, and 2 implied meaning phrases for debating '{topic}' in {lang_name} for expert level. Format (separated by · ): nuance1 · nuance2 · nuance3 · register1 · register2 · implied1 · implied2",
            "condition": "Control the conversation.\nAdapt to the opponent's style.\nInfluence the outcome."
        }
    }

    config = level_config.get(level_key, level_config["B1"])

    weapons_response = ask_gpt(config["weapons_prompt"], temperature=0.7, max_tokens=150)
    if not weapons_response:
        weapons_response = "argue · convince · evidence · logic · debate"

    return weapons_response, "", config["condition"]


def generate_situation(topic: str, personality: str, language: str) -> str:
    """Генерирует ситуацию для миссии."""
    person = PERSONALITIES.get(personality, {})
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    prompt = f"""
    Create a short, specific situation for a debate about "{topic}" with {person.get('name', 'a person')}.
    Language: {lang_name}.

    The situation should be:
    - 2-3 sentences
    - Concrete and realistic
    - Create tension or conflict

    Examples:
    "Your company wants to introduce a new employee wellbeing programme. Sarah controls the budget."
    "You have an idea that could revolutionize your industry. Richard is skeptical."

    Write in English:
    """

    response = ask_gpt(prompt, temperature=0.7, max_tokens=100)
    if not response:
        return f"You need to discuss '{topic}' with {person.get('name', 'the expert')}. They are not convinced."
    return response.strip()


def generate_persuasion_phrases(personality: str, topic: str, level: str, language: str) -> str:
    """Генерирует 5 фраз-убеждений для миссии."""
    person = PERSONALITIES.get(personality, {})
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    prompt = f"""
    Generate 5 persuasive phrases that help convince {person.get('name', 'собеседника')} on topic "{topic}".
    Level: {level}.
    Language: {lang_name}.
    Format (separated by commas): phrase1, phrase2, phrase3, phrase4, phrase5
    """
    response = ask_gpt(prompt, temperature=0.7, max_tokens=100)
    if not response:
        return "I believe, Let's consider, The point is, What if, Imagine"
    return response.strip()


def generate_tips(personality: str) -> str:
    person = PERSONALITIES.get(personality, {})
    prompt = f"""
    Дай 3 коротких совета как общаться с {person.get('name', 'собеседником')}.
    Формат: совет1 · совет2 · совет3
    """
    response = ask_gpt(prompt, temperature=0.7, max_tokens=80)
    if not response:
        return "Будь уверен · Приводи примеры · Слушай внимательно"
    return response.strip()


# ========== КОЛКАЯ ФРАЗА И ЗАДАНИЕ ==========

def generate_character_insight(personality: str, topic: str, user_name: str, language: str) -> str:
    """
    Колкая яркая фраза — почему стоит поговорить именно с этим персонажем.
    """
    person = PERSONALITIES.get(personality, {})
    prompt = f"""
    Ты — ARENA. Ты только что порекомендовал {person.get('name', 'персонажа')} для {user_name}.
    Тема: {topic}.

    Скажи ОДНУ яркую, колкую фразу (на РУССКОМ языке) о том, почему {user_name} стоит поговорить с {person.get('name', 'ним')} именно сейчас.

    Примеры:
    "Этот разговор сломает твой шаблон."
    "Он вытащит из тебя то, что ты даже не знал, что можешь сказать."
    "Она заставит тебя увидеть это иначе."

    Фраза должна быть живой, без 'потому что', без объяснений.
    """
    response = ask_gpt(prompt, temperature=0.85, max_tokens=80)
    if not response:
        return f"Разговор с {person.get('name', 'этим персонажем')} изменит твой взгляд на тему."
    return response.strip()


def generate_mission_task(topic: str, personality: str, user_name: str, language: str) -> str:
    """
    Конкретное задание по теме.
    """
    person = PERSONALITIES.get(personality, {})
    prompt = f"""
    Придумай конкретное задание для {user_name} в разговоре с {person.get('name', 'персонажем')}.
    Тема: {topic}.

    Задание должно быть:
    - конкретным
    - связанным с темой
    - звучать как вызов
    - на РУССКОМ языке

    Примеры:
    "Убеди его, что эта идея стоит инвестиций."
    "Заставь его признать, что ты прав."
    "Докажи ей, что твой подход более эффективен."

    Напиши 1 предложение на РУССКОМ языке.
    """
    response = ask_gpt(prompt, temperature=0.7, max_tokens=100)
    if not response:
        return f"Убеди {person.get('name', 'собеседника')} в своей правоте по теме «{topic}»."
    return response.strip()


# ========== ДИАЛОГ С ПЕРСОНАЖЕМ ==========

def generate_opening_statement(personality: str, topic: str, level: str, language: str) -> str:
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")
    role_style = ROLE_STYLE.get(personality, "")
    prompt = f"""
    Ты — {person_name}. Начни дебаты на тему "{topic}" на языке {lang_name}.
    Твой стиль поведения в разговоре: {role_style}
    Уровень собеседника: {level}. {level_desc}
    Скажи 1-2 предложения — жёсткое утверждение, в своём характере, а не нейтральное вступление.
    Обращайся к собеседнику на "ты".
    """
    response = ask_gpt(prompt, temperature=0.8, max_tokens=100)
    if not response:
        return f"Let's discuss {topic}."
    return response.strip()


def generate_ai_response(personality: str, dialogue_history: str, last_user_response: str, level: str,
                         language: str, mission: str = None, user_name: str = "") -> str:
    """
    mission — короткое напоминание о том, чего персонаж добивается от пользователя
    в этом бою (например: "Убедить Sarah, что тема X стоит внимания").
    Подмешивается в промпт на КАЖДОМ ходу, чтобы персонаж не "забывал" миссию
    и не соскальзывал в обычный small talk посреди боя.

    role_style — стиль поведения персонажа (провокационные вопросы, взгляд с
    другой стороны и т.д.), чтобы персонажи не были "удобными собеседниками",
    а вели себя согласно своему характеру.
    """
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")
    role_style = ROLE_STYLE.get(personality, "")

    mission_block = ""
    if mission:
        mission_block = f"""
    ТВОЯ МИССИЯ В ЭТОМ РАЗГОВОРЕ (никогда не забывай её и не отклоняйся от неё):
    {mission}
    Если пользователь уходит от темы — верни его к миссии в своём характере,
    не переключайся на посторонний small talk.
    """

    name_instruction = (
        f'Если уместно — обращайся к собеседнику по имени ({user_name}). '
        if user_name else ""
    )

    prompt = f"""
    Ты — {person_name}. Продолжай диалог на {lang_name}, ВЕСЬ ответ строго на {lang_name}.
    Твой стиль поведения (следуй ему, не будь нейтральным "удобным" собеседником):
    {role_style}
    {mission_block}
    Уровень собеседника: {level}. {level_desc}
    История: {dialogue_history}
    Последний ответ: {last_user_response}
    {name_instruction}Обращайся к собеседнику на "ты"/"you".
    Твой ответ (1-2 предложения, строго в своём характере и стиле, не забывай про миссию):
    """
    response = ask_gpt(prompt, temperature=0.8, max_tokens=150)
    if not response:
        return "That's interesting. Tell me more."
    return response.strip()


# ========== ВЕРДИКТ ПОСЛЕ БИТВЫ ==========

def generate_arena_verdict(user_responses: list[str], user_name: str, language: str) -> str:
    """
    Живой вердикт судьи ПОСЛЕ битвы (не в First Encounter).
    Используется только в конце игры. Тон — тёплый, не агрессивный, сначала
    что было круто, потом — зона роста. Обращение по имени, никогда не
    "пользователь"/"участник".
    """
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    user_text = " ".join(user_responses)[:1500]

    prompt = f"""
    Ты — ARENA, судья. Ты только что наблюдал за битвой.

    Человек: {user_name}
    Язык: {lang_name}
    Вот что он говорил:
    {user_text}

    Напиши живой, тёплый, НЕ агрессивный вердикт (3-5 предложений на РУССКОМ
    языке). Структура обязательна:
    1) Сначала — что было круто (конкретно: грамматика, слова, или мягкие
       навыки — уверенность, аргументация, адаптивность).
    2) Потом — одна конкретная зона роста, без critики в лоб, по-доброму.
    Без сухих списков, без оценок в процентах, без слова "пользователь".
    Обращайся к {user_name} по имени.

    Вердикт (на РУССКОМ):
    """
    response = ask_gpt(prompt, temperature=0.7, max_tokens=300)
    if not response:
        return f"{user_name}, ты показал интересный подход к разговору. Есть куда расти, но основа хорошая."
    return response.strip()


def generate_growth_plan(user_name: str, strength: str, growth: str, language: str) -> str:
    """
    План развития на 10 раундов вперёд — используется в профиле после
    завершения боя. Короткий, конкретный, по шагам.
    """
    prompt = f"""
    {user_name} только что закончил бой на ARENA.
    Сильная сторона: {strength}
    Зона роста: {growth}

    Составь короткий план развития на 10 следующих раундов (боёв) — 3-4
    пункта, конкретных и выполнимых, на РУССКОМ языке. Без воды, по делу.
    Формат: список с "•" в начале каждой строки.
    """
    response = ask_gpt(prompt, temperature=0.6, max_tokens=200)
    if not response:
        return f"• Продолжай использовать {strength.lower()}\n• Обрати внимание на: {growth}\n• Сыграй ещё 10 боёв с разными персонажами"
    return response.strip()


def extract_vocabulary_mistakes(user_responses: list[str], language: str) -> list[dict]:
    """
    Достаёт из ответов пользователя слова/выражения, использованные
    НЕПРАВИЛЬНО, вместе с правильной формой — чтобы добавить их в личный
    словарь "слов для заучивания" в профиле.
    Возвращает список [{"wrong": "...", "correct": "...", "note": "..."}]
    """
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    user_text = " ".join(user_responses)[:1500]

    prompt = f"""
    Проанализируй текст на {lang_name} и найди СЛОВА ИЛИ ВЫРАЖЕНИЯ, использованные
    неправильно (грамматически или лексически). Текст:
    {user_text}

    Для каждой ошибки (максимум 5) дай строку строго в формате:
    неправильно :: правильно

    Если ошибок нет, ответь: НЕТ ОШИБОК
    """
    raw = ask_gpt(prompt, temperature=0.3, max_tokens=250)
    mistakes = []
    if not raw or "НЕТ ОШИБОК" in raw.upper():
        return mistakes

    for line in raw.split("\n"):
        line = line.strip()
        if "::" in line:
            wrong, correct = line.split("::", 1)
            wrong, correct = wrong.strip(" -•"), correct.strip()
            if wrong and correct:
                mistakes.append({"wrong": wrong, "correct": correct})
    return mistakes


def generate_daily_push(personality: str, topics: list[str], user_name: str, language: str) -> str:
    """
    Провокационное сообщение "от персонажа" для ежедневного пуша — со ссылкой
    на то, что человек уже обсуждал раньше, и приглашением продолжить.
    """
    person = PERSONALITIES.get(personality, {})
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    topics_text = ", ".join(topics[:3]) if topics else "то, о чём вы говорили"

    prompt = f"""
    Ты — {person.get('full_name', personality)}. Твой стиль: {ROLE_STYLE.get(personality, '')}

    Ты пишешь короткое push-уведомление для {user_name} в мессенджере — вы
    уже обсуждали: {topics_text}.

    Сообщение должно:
    - быть 1-2 предложения, на РУССКОМ языке
    - содержать провокационное утверждение или вызов, в твоём характере
    - предлагать продолжить разговор именно по одной из этих тем
    - НЕ быть нейтральным/вежливым — оставайся собой

    Сообщение:
    """
    response = ask_gpt(prompt, temperature=0.85, max_tokens=120)
    if not response:
        return f"{person.get('name', 'Я')}: помнишь, о чём мы говорили про {topics_text}? Я так и не услышал(а) от тебя финальный аргумент. Заходи."
    return response.strip()


# ========== АНАЛИЗ ==========

def analyze_first_encounter(user_responses: list[str], language: str) -> dict:
    user_text = " ".join(user_responses)
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    prompt = f"""
    Проанализируй ответы пользователя на языке {lang_name}.
    Ответы: {user_text[:1000]}

    Формат:
    УРОВЕНЬ: [A1/A2/B1/B2/C1/C2]
    ИНТЕРЕСЫ: [тема1, тема2, тема3]
    СИЛЬНОЕ: [что хорошо]
    РОСТ: [что можно улучшить]
    ПЕРСОНАЖ: [hr_manager/ceo/journalist/professor/philosopher/devil_advocate]
    """
    raw = ask_gpt(prompt, temperature=0.5, max_tokens=300)

    result = {
        "estimated_level": "B1",
        "interests": ["интересная тема"],
        "strength": "Хорошо выражает мысли",
        "growth": "Можно больше внимания деталям",
        "recommended_personality": "hr_manager",
    }

    if raw:
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("УРОВЕНЬ:"):
                lvl = line.replace("УРОВЕНЬ:", "").strip().upper()
                if lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                    result["estimated_level"] = lvl
            elif line.startswith("ИНТЕРЕСЫ:"):
                interests_str = line.replace("ИНТЕРЕСЫ:", "").strip()
                if interests_str:
                    result["interests"] = [i.strip() for i in interests_str.split(",")]
            elif line.startswith("СИЛЬНОЕ:"):
                result["strength"] = line.replace("СИЛЬНОЕ:", "").strip()
            elif line.startswith("РОСТ:"):
                result["growth"] = line.replace("РОСТ:", "").strip()
            elif line.startswith("ПЕРСОНАЖ:"):
                key = line.replace("ПЕРСОНАЖ:", "").strip().lower()
                if key in PERSONALITIES:
                    result["recommended_personality"] = key

    return result


def analyze_debate(user_responses: list[str], dialogue: list[dict], topic: str, level: str, language: str,
                   personality: str, mission_words: str = "") -> dict:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", "English")
    user_text_full = " ".join(user_responses)

    # --- Аргументация ---
    arg_keywords = ["because", "since", "therefore", "however", "although", "but"]
    arg_count = sum(1 for w in arg_keywords if w in user_text_full.lower())
    argumentation_score = max(30, min(100, 40 + arg_count * 10))

    # --- Словарный запас ---
    vocab_prompt = f"Оцени словарный запас пользователя на {lang_name}. Ответы: {user_text_full[:500]}\nФормат: СКОР: [число]"
    vocab_raw = ask_gpt(vocab_prompt, temperature=0.5, max_tokens=50)
    vocab_score = 70
    if vocab_raw:
        nums = re.findall(r"\d+", vocab_raw)
        if nums:
            vocab_score = min(100, int(nums[0]))

    # --- Грамматика ---
    grammar_prompt = f"Оцени грамматику пользователя на {lang_name}. Ответы: {user_text_full[:500]}\nФормат: СКОР: [число]"
    grammar_raw = ask_gpt(grammar_prompt, temperature=0.5, max_tokens=50)
    grammar_score = 70
    if grammar_raw:
        nums = re.findall(r"\d+", grammar_raw)
        if nums:
            grammar_score = min(100, int(nums[0]))

    # --- Беглость ---
    avg_len = sum(len(r.split()) for r in user_responses) / len(user_responses) if user_responses else 0
    fluency_score = max(30, min(100, round(40 + avg_len * 4)))

    # --- Анализ ---
    verdict_prompt = f"""
    Проанализируй ответы пользователя с {person['full_name']} на тему "{topic}".
    Язык: {lang_name}.
    Ответы: {user_text_full[:1500]}

    Формат:
    СИЛЬНЫЙ_МОМЕНТ: [1 предложение на русском — что было круто]
    ЗОНА_РОСТА: [1 предложение на русском — что доработать]
    ФРАЗА: [одна фраза на {lang_name} длиной 4-10 слов]
    """
    verdict_raw = ask_gpt(verdict_prompt, temperature=0.6, max_tokens=250)

    moment_text = ""
    unique_phrase = "Используй больше связок."

    if verdict_raw:
        for line in verdict_raw.split("\n"):
            line = line.strip()
            if line.startswith("СИЛЬНЫЙ_МОМЕНТ:"):
                moment_text = f"🌟 <b>Сильный момент:</b> {line.replace('СИЛЬНЫЙ_МОМЕНТ:', '').strip()}"
            elif line.startswith("ЗОНА_РОСТА:"):
                growth = line.replace("ЗОНА_РОСТА:", "").strip()
                if moment_text:
                    moment_text += f"\n📈 <b>Зона роста:</b> {growth}"
            elif line.startswith("ФРАЗА:"):
                unique_phrase = line.replace("ФРАЗА:", "").strip()

    return {
        "scores": {
            "argumentation": argumentation_score,
            "vocabulary": vocab_score,
            "grammar": grammar_score,
            "fluency": fluency_score,
        },
        "unique_phrase": unique_phrase,
        "moment_text": moment_text,
    }