"""
AI-логика арены: обращение к GPT, реплики персонажей, финальный анализ.
"""
import re
import logging

import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import (
    LEVEL_DESCRIPTIONS,
    PERSONALITIES,
    LANGUAGES,
    ROLE_STYLE,
    LEVELS,
    COMMON_GRAMMAR_ERRORS,
    FALLBACK_LINKING_PHRASES,
    GROWTH_TO_PERSONALITY,
    SKILL_WEIGHTS,
    LANGUAGE_SKILLS,
    COMMUNICATION_SKILLS,
    PERSONALITY_MISSIONS,
    ARENA_MOVES,
    BATTLE_COMPLEXITY,
    LEVEL_WORDS,
    PERSONALITY_MISSION_TEMPLATES,
    MISSION_SCENARIOS,
    BATTLE_OBJECTIVES,
    PERSONALITY_VOICE,
    RESPONSE_LENGTH,
)

logger = logging.getLogger(__name__)

GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def ask_gpt(prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str | None:
    """Синхронный вызов GPT. Вызывай из хендлеров через asyncio.to_thread."""
    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        logger.warning("YANDEX_API_KEY / YANDEX_FOLDER_ID не заданы")
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
        logger.error("GPT error %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("GPT request failed")
    return None


# ---------- ГЕНЕРАЦИЯ КЕЙСА (ТЕМЫ) ----------

def generate_case_topic(personality: str, level: str, language: str, user_interests: list = None) -> dict:
    """
    Генерирует КЕЙС для обсуждения с персонажем.
    Возвращает: {"title": "...", "description": "...", "challenge": "...", "words": [...], "tips": [...]}
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    # Описания уровней
    level_desc = {
        "A1": "очень простой, базовый (используй простые слова)",
        "A2": "простой, с базовыми конструкциями",
        "B1": "средний, с простыми аргументами",
        "B2": "средний+, с аргументацией",
        "C1": "сложный, с академической лексикой",
        "C2": "максимально сложный, с нюансами"
    }.get(level, "средний")

    interests_text = ", ".join(user_interests[:2]) if user_interests else "общие темы"

    # Жёсткие характеристики персонажей для кейса
    personality_case = {
        "ceo": {
            "style": "жёсткий, требовательный, только факты и цифры",
            "goal": "убедить инвестировать в твою идею",
            "questions": ["ROI?", "Market size?", "Competitors?", "Risk?"]
        },
        "journalist": {
            "style": "провокационный, ищет сенсацию",
            "goal": "дать интервью, которое не разрушит твою репутацию",
            "questions": ["Are you hiding something?", "Who's really behind this?", "What's the scandal?"]
        },
        "professor": {
            "style": "строгий академический, требует доказательств",
            "goal": "защитить свою научную работу",
            "questions": ["What's your thesis?", "Where's your evidence?", "What's your methodology?"]
        },
        "hr_manager": {
            "style": "деловой, оценивает по STAR-методу",
            "goal": "пройти собеседование на работу мечты",
            "questions": ["Tell me about a time when...", "What was the result?", "What did you learn?"]
        },
        "philosopher": {
            "style": "глубокий, задаёт сложные вопросы о смысле",
            "goal": "ответить на вопрос 'в чём смысл?'",
            "questions": ["Why does it matter?", "What is truth?", "What is a good life?"]
        },
        "devil_advocate": {
            "style": "агрессивный, давит, ищет слабые места",
            "goal": "отстоять свою позицию под давлением",
            "questions": ["What if you're wrong?", "Prove it.", "Is that all you've got?"]
        }
    }

    case_info = personality_case.get(personality, personality_case["devil_advocate"])

    # Формируем промпт для генерации кейса
    prompt = f"""
    Ты — ARENA. Ты создаёшь КЕЙС для битвы с {person['full_name']}.

    Персонаж: {person['name']} — {person['desc']}
    Стиль персонажа: {case_info['style']}
    Цель участника: {case_info['goal']}

    Уровень участника: {level} ({level_desc})
    Язык: {lang_name}
    Интересы участника: {interests_text}

    Твоя задача — создать яркий, живой кейс:
    1. СИТУАЦИЯ (1-2 предложения) — конкретная, реальная ситуация
    2. ЗАДАЧА (1 предложение) — что должен сделать участник
    3. 5 СЛОВ для использования (с переводом на русский) — соответствующих уровню
    4. 3 ЛАЙФХАКА для общения (на русском) — как лучше общаться с этим персонажем

    Формат (строго):
    ТЕМА: [название кейса]
    СИТУАЦИЯ: [описание ситуации]
    ЗАДАЧА: [что нужно сделать]
    СЛОВА: [слово1: перевод1, слово2: перевод2, слово3: перевод3, слово4: перевод4, слово5: перевод5]
    ЛАЙФХАКИ: [совет1, совет2, совет3]
    """

    response = ask_gpt(prompt, temperature=0.8, max_tokens=600)

    # Fallback
    if not response:
        return {
            "title": f"Кейс с {person['name']}",
            "description": f"Ты встречаешься с {person['full_name']}. Он ждёт от тебя чётких аргументов.",
            "challenge": f"Убеди {person['name']} в своей правоте.",
            "words": ["argue: спорить", "convince: убеждать", "evidence: доказательство", "strategy: стратегия",
                      "result: результат"],
            "tips": ["Говори чётко и по делу", "Используй факты", "Не бойся спорить"]
        }

    # Парсим ответ
    result = {
        "title": "Кейс",
        "description": "",
        "challenge": "",
        "words": [],
        "tips": []
    }

    lines = response.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("ТЕМА:") or line.startswith("СИТУАЦИЯ:"):
            result["title"] = line.replace("ТЕМА:", "").replace("СИТУАЦИЯ:", "").strip()
        elif line.startswith("ЗАДАЧА:"):
            result["challenge"] = line.replace("ЗАДАЧА:", "").strip()
        elif line.startswith("СЛОВА:"):
            words_part = line.replace("СЛОВА:", "").strip()
            result["words"] = [w.strip() for w in words_part.split(",") if w.strip()]
        elif line.startswith("ЛАЙФХАКИ:"):
            tips_part = line.replace("ЛАЙФХАКИ:", "").strip()
            result["tips"] = [t.strip() for t in tips_part.split(",") if t.strip()]

    # Если не распарсилось, используем fallback
    if not result["title"] or result["title"] == "Кейс":
        result["title"] = f"Кейс с {person['name']}"
        result["description"] = f"Ты встречаешься с {person['full_name']}. Он ждёт от тебя чётких аргументов."
        result["challenge"] = f"Убеди {person['name']} в своей правоте."
        result["words"] = ["argue: спорить", "convince: убеждать", "evidence: доказательство"]
        result["tips"] = ["Говори чётко и по делу", "Используй факты"]

    return result


def generate_mission_words_from_case(case_topic: dict, level: str) -> str:
    """Возвращает строку слов из кейса"""
    if case_topic and case_topic.get("words"):
        return ", ".join(case_topic["words"])
    return "argue: спорить, convince: убеждать, evidence: доказательство"


# ---------- РЕПЛИКИ ПЕРСОНАЖА (ЖЁСТКИЕ) ----------

def generate_opening_statement(personality: str, topic: str, level: str, language: str, case_topic: dict = None) -> str:
    person = PERSONALITIES.get(personality, {}).get("full_name", personality)
    voice = PERSONALITY_VOICE.get(personality, PERSONALITY_VOICE["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")

    # Жёсткие открывающие фразы по персонажам
    hard_openings = {
        "ceo": "I don't have time for small talk. Give me ONE reason why I should listen to you. And make it good.",
        "journalist": "I've heard this story before. Unless you've got something I haven't seen, this interview is over.",
        "professor": "Your thesis is weak. I can see the holes from here. Try again with real evidence.",
        "hr_manager": "I've interviewed 500 people this month. Don't give me generic answers. Impress me.",
        "philosopher": "You think you have answers? I have questions. Deeper ones. Let's see if you can keep up.",
        "devil_advocate": "I'm going to tear your argument apart. I hope you're ready to fight for your position."
    }

    opening = hard_openings.get(personality, voice.get("opening", ["Let's begin."])[0])

    # Если есть кейс — используем его
    if case_topic and case_topic.get("description"):
        opening += f"\n\n{case_topic['description']}"

    prompt = f"""
    Ты — {person}. Ты ведёшь дебаты на языке {lang_name}.

    Твой характер: 
    - Ты жёсткий, требовательный
    - Ты не принимаешь слабые аргументы
    - Ты давишь на собеседника
    - Ты проверяешь его на прочность

    Уровень собеседника: {level}. Соблюдай этот уровень в лексике.

    Твоя первая фраза (1-2 предложения) — сразу в атаку, без приветствий.
    Используй свой стиль: {opening}

    Ответь ТОЛЬКО репликой, без лишних слов.
    """

    response = ask_gpt(prompt, temperature=0.8, max_tokens=150)
    if not response:
        return opening

    return response.strip()


def generate_ai_response(personality: str, dialogue_history: str, last_user_response: str,
                         level: str, language: str, case_topic: dict = None) -> str:
    """Реплика персонажа — жёсткая, в характере, с учётом темы"""
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    voice = PERSONALITY_VOICE.get(personality, PERSONALITY_VOICE["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")
    response_length = RESPONSE_LENGTH.get(level, RESPONSE_LENGTH["B1"])

    # Жёсткие характеры персонажей
    hard_traits = {
        "ceo": "Ты — CEO. Говори коротко, жёстко, по делу. Требуй цифры, факты, стратегию. Сразу отсекай слабые аргументы. Не терпишь эмоций и воды. Если аргумент слабый — говори об этом прямо.",
        "journalist": "Ты — журналист-расследователь. Ты ищешь скандал, сенсацию, правду. Задавай провокационные вопросы, ищи противоречия. Не давай уйти от ответа. Если собеседник уклоняется — дави.",
        "professor": "Ты — профессор. Ты видишь каждую логическую ошибку. Требуй структуру: тезис → аргумент → вывод. Исправляй неточности. Спрашивай 'откуда ты это взял?' и 'где доказательства?'",
        "hr_manager": "Ты — HR-директор. Ты проводишь стресс-собеседование. Требуй конкретные примеры из жизни. Если ответ общий — переспрашивай 'а конкретно?' и 'какой был результат?'",
        "philosopher": "Ты — философ. Ты никогда не даёшь прямых ответов. Отвечай вопросом на вопрос. Копай глубже. Спрашивай 'почему это важно?' и 'а что если посмотреть иначе?'",
        "devil_advocate": "Ты — дьявольский адвокат. Ты всегда споришь, даже если согласен. Находи слабые места в каждом аргументе. Дави, провоцируй. Говори 'это слабо', 'докажи', 'а если ты не прав?'"
    }

    trait = hard_traits.get(personality, hard_traits["devil_advocate"])

    # Жёсткие фразы для каждого персонажа
    hard_phrases = {
        "ceo": ["That's weak.", "Show me the numbers.", "I'm not convinced.", "That doesn't work.", "Try again."],
        "journalist": ["That's what they all say.", "I don't believe you.", "What are you hiding?", "Prove it."],
        "professor": ["Your logic is flawed.", "That's not a valid argument.", "Where's your evidence?",
                      "You're missing a step."],
        "hr_manager": ["Give me a real example.", "That's too vague.", "What was the result?",
                       "Tell me about a specific situation."],
        "philosopher": ["But why?", "What does that really mean?", "Is that truly what you believe?",
                        "And if you're wrong?"],
        "devil_advocate": ["That's not good enough.", "I can tear that apart.", "Is that all you've got?",
                           "You can do better."]
    }

    phrases = hard_phrases.get(personality, hard_phrases["devil_advocate"])
    phrases_sample = " ".join(phrases[:2])

    # Формируем контекст с темой кейса
    case_context = ""
    if case_topic:
        case_context = f"""
Тема кейса: {case_topic.get('title', '')}
Задача участника: {case_topic.get('challenge', '')}
"""

    prompt = f"""
    Ты — {person['full_name']}. {person['desc']}

    {trait}

    {case_context}

    Ты разговариваешь на языке {lang_name} с человеком уровня {level}.

    История диалога:
    {dialogue_history}

    Последний ответ собеседника:
    {last_user_response}

    Твои любимые фразы: {phrases_sample}

    Сложность речи: {level_desc}
    Длина ответа: {response_length}

    Правила:
    1. Отвечай жёстко, в своём характере
    2. Используй одну из своих фраз в ответе
    3. Не теряй тему кейса
    4. Дави на слабые места аргументов
    5. Не хвали собеседника — он должен заслужить твоё уважение
    6. Без AI-терминологии

    Твой ответ на языке {lang_name}:
    """

    response = ask_gpt(prompt, temperature=0.85, max_tokens=150)

    if not response or len(response.split()) < 2:
        import random
        return random.choice(phrases)

    return response.strip()


# ---------- ARENA: First Encounter ----------

def generate_arena_reaction(
        dialogue_history: str,
        last_user_response: str,
        language: str,
        move_number: int
) -> str:
    """ARENA — просто внимательный собеседник. Без анализа."""
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    history_lines = dialogue_history.split("\n") if dialogue_history else []
    recent = history_lines[-3:] if len(history_lines) > 3 else history_lines
    context = "\n".join(recent)

    prompt = f"""
Ты — ARENA. Ты просто разговариваешь с человеком на языке {lang_name}.

Это ход {move_number} из 8. Ты ещё слушаешь, не оцениваешь.

Вот недавний разговор:
{context}

Человек только что сказал:
{last_user_response}

Твоя задача — продолжить разговор естественно, как живой человек.
Сделай так, чтобы человеку было интересно говорить дальше.
Не используй слова "анализ", "паттерн", "гипотеза" — ты просто собеседник.

Ответь 1-2 предложениями.
"""

    response = ask_gpt(prompt, temperature=0.85, max_tokens=120)

    if not response or len(response.split()) < 2:
        fallbacks = [
            "Расскажи подробнее, мне правда интересно.",
            "А что для тебя в этом самое важное?",
            "Звучит увлекательно. Как ты к этому пришёл?",
            "Понятно. Что дальше?"
        ]
        return fallbacks[move_number % len(fallbacks)]

    return response.strip()


def generate_arena_closing(
        user_responses: list[str],
        user_level: str,
        language: str,
        recommended_personality: str,
        interests: list[str],
        strengths: list[str],
        weaknesses: list[str]
) -> str:
    """Финальная реплика ARENA — тёплая, человеческая."""
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    person = PERSONALITIES.get(recommended_personality, PERSONALITIES["hr_manager"])

    interest = interests[0] if interests else "интересную тему"
    weakness = weaknesses[0] if weaknesses else "аргументацию"

    prompt = f"""
Ты — ARENA. Ты только что 8 раз разговаривала с человеком на языке {lang_name}.

Он говорил о: {interest} (несколько раз)
Его уровень: {user_level}

Ты заметила, что ему стоит развить: {weakness}

Ты хочешь предложить ему поговорить с {person['full_name']}.

Скажи ему тёплую, живую фразу на языке {lang_name}:
1. Покажи, что ты его услышала
2. Скажи, что он интересовался {interest} несколько раз
3. Предложи обсудить это с {person['name']}
4. Без AI-терминологии

Ответь 2-3 предложениями. Как человек человеку.
"""

    response = ask_gpt(prompt, temperature=0.8, max_tokens=150)

    if not response:
        return f"You mentioned {interest} several times. I think you should talk to {person['full_name']} about this. He's great at helping people develop their {weakness}."

    return response.strip()


def analyze_first_encounter(user_responses: list[str], language: str) -> dict:
    """Полный анализ после 8 ходов с персонализацией."""
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    user_text_full = " ".join(user_responses)[:1500]

    prompt = f"""
    Ты — ARENA. Ты внимательно слушала человека на языке {lang_name} в течение 8 ходов.

    Вот что он говорил:
    {user_text_full}

    Проведи полный анализ и определи:

    1. УРОВЕНЬ ЯЗЫКА (A1-C2) — по грамматике, словарю, сложности конструкций
    2. ИНТЕРЕСЫ (2-3 темы, которые чаще всего упоминались)
    3. СИЛЬНЫЕ СТОРОНЫ (2-3 навыка из списка: vocabulary, grammar, fluency, clarity, precision, argumentation, persuasion, adaptability, confidence, critical_thinking)
    4. СЛАБЫЕ СТОРОНЫ (2-3 навыка из того же списка, которые нужно развивать)

    Формат (текст на РУССКОМ):
    УРОВЕНЬ: [A1/A2/B1/B2/C1/C2]
    ИНТЕРЕСЫ: [тема1, тема2, тема3]
    СИЛЬНЫЕ: [навык1, навык2, навык3]
    СЛАБЫЕ: [навык1, навык2, навык3]
    """

    raw = ask_gpt(prompt, temperature=0.5, max_tokens=400)

    result = {
        "estimated_level": "B1",
        "interests": ["работа", "команда", "развитие"],
        "strength_skills": ["clarity", "fluency"],
        "weakness_skills": ["precision", "argumentation"],
        "recommended_personality": "hr_manager",
    }

    if raw and len(raw) > 30:
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("УРОВЕНЬ:"):
                lvl = line.replace("УРОВЕНЬ:", "").strip().upper()
                if lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                    result["estimated_level"] = lvl
            elif line.startswith("ИНТЕРЕСЫ:"):
                interests = line.replace("ИНТЕРЕСЫ:", "").strip()
                result["interests"] = [i.strip() for i in interests.split(",")][:3]
            elif line.startswith("СИЛЬНЫЕ:"):
                skills = line.replace("СИЛЬНЫЕ:", "").strip()
                result["strength_skills"] = [s.strip().lower() for s in skills.split(",")][:3]
            elif line.startswith("СЛАБЫЕ:"):
                skills = line.replace("СЛАБЫЕ:", "").strip()
                result["weakness_skills"] = [s.strip().lower() for s in skills.split(",")][:3]

    # Выбор персонажа по слабым сторонам
    weakness = result["weakness_skills"]
    recommended = "hr_manager"

    for skill in weakness:
        if skill in GROWTH_TO_PERSONALITY:
            recommended = GROWTH_TO_PERSONALITY[skill]
            break

    if recommended == "hr_manager" and weakness:
        for skill in weakness:
            for key in GROWTH_TO_PERSONALITY:
                if key in skill or skill in key:
                    recommended = GROWTH_TO_PERSONALITY[key]
                    break
            if recommended != "hr_manager":
                break

    result["recommended_personality"] = recommended

    print(f"🎯 Анализ ARENA:")
    print(f"   Уровень: {result['estimated_level']}")
    print(f"   Интересы: {result['interests']}")
    print(f"   Слабые: {result['weakness_skills']}")
    print(f"   → Рекомендован: {recommended}")

    return result


def generate_mission(
        personality: str,
        topic: str,
        user_level: str,
        language: str,
        interests: list[str],
        strength_skills: list[str],
        weakness_skills: list[str]
) -> dict:
    """Миссия с кейсом и словами."""
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    # Создаём кейс
    case = generate_case_topic(personality, user_level, language, interests)

    return {
        "challenge_description": case.get("challenge", f"Убеди {person['name']} в своей правоте."),
        "target_words": [w.split(":")[0].strip() for w in case.get("words", [])],
        "personality_phrase": person.get("phrase", "Убеди меня."),
        "case_title": case.get("title", "Кейс"),
        "case_description": case.get("description", ""),
        "tips": case.get("tips", []),
        "full_words": case.get("words", [])
    }


def generate_battle_card(
        personality: str,
        topic: str,
        user_level: str,
        language: str,
        interests: list[str],
        weakness_skills: list[str]
) -> dict:
    """Генерирует Battle Card для пользователя."""
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    objectives = BATTLE_OBJECTIVES.get(personality, BATTLE_OBJECTIVES["hr_manager"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    # Создаём кейс
    case = generate_case_topic(personality, user_level, language, interests)

    mission_prompt = f"""
    Ты — ARENA. Придумай миссию для битвы с {person['full_name']} на языке {lang_name}.

    Тема: {topic}
    Уровень пользователя: {user_level}

    Что нужно сделать пользователю, чтобы убедить {person['name']}?
    Напиши 1 предложение.
    """

    mission_text = ask_gpt(mission_prompt, temperature=0.7, max_tokens=100)
    if not mission_text:
        mission_text = case.get("challenge", f"Убеди {person['name']} что {topic} — это важно.")

    return {
        "personality": personality,
        "personality_name": person['name'],
        "personality_full": person['full_name'],
        "mission": mission_text,
        "topic": topic,
        "time_limit": 15,
        "objectives": objectives.get("objectives", []),
        "user_weapons": case.get("words", [])[:5],
        "character_weapons": ", ".join(objectives.get("weapons", [])[:3]),
        "win_condition": objectives.get("win_condition", "Убеди персонажа"),
        "case_title": case.get("title", "Кейс"),
        "case_description": case.get("description", ""),
        "tips": case.get("tips", [])
    }


def check_battle_completion(
        dialogue: list[dict],
        objectives: list[str],
        user_weapons: list[str],
        time_elapsed: int = None,
        time_limit: int = 15
) -> dict:
    """Проверяет, выполнены ли условия битвы."""
    user_responses = [d["text"] for d in dialogue if d["speaker"] == "User"]
    user_text = " ".join(user_responses).lower()

    weapons_used = []
    for weapon in user_weapons:
        if weapon.lower() in user_text:
            weapons_used.append(weapon)

    objectives_completed = []
    for objective in objectives:
        keywords = objective.lower().split()
        if any(k in user_text for k in keywords if len(k) > 3):
            objectives_completed.append(objective)

    time_up = time_elapsed is not None and time_elapsed >= time_limit

    if time_up:
        status = "time_up"
        message = "Время вышло! Давай подведём итоги."
    elif len(objectives_completed) >= len(objectives) * 0.6:
        status = "completed"
        message = "Ты выполнил основные условия миссии. Впечатляет!"
    else:
        status = "in_progress"
        message = "Продолжай битву."

    return {
        "status": status,
        "message": message,
        "objectives_completed": objectives_completed,
        "objectives_total": len(objectives),
        "weapons_used": weapons_used,
        "weapons_total": len(user_weapons),
        "time_up": time_up,
    }


# ---------- Финальный анализ ----------

def _parse_scored_response(raw: str | None, score_marker: str, text_marker: str,
                           default_score: int, default_text: str) -> tuple[int, str]:
    score, text = default_score, default_text
    if raw and len(raw) > 10:
        for line in raw.split("\n"):
            if score_marker in line:
                nums = re.findall(r"\d+", line)
                if nums:
                    score = min(100, int(nums[0]))
            if text_marker in line:
                text = line.replace(text_marker, "").strip()
    return max(30, score), text


def analyze_debate(user_responses: list[str], dialogue: list[dict], topic: str,
                   level: str, language: str, personality: str, mission_words: str = "") -> dict:
    """Упрощённый финальный разбор."""
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", "English")

    user_text_full = " ".join(user_responses)
    total_words = len(user_text_full.split())
    questions = sum(1 for r in user_responses if "?" in r)

    # 1. Аргументация
    arg_keywords = ["because", "since", "therefore", "thus", "consequently",
                    "for example", "for instance", "however", "although"]
    arg_count = sum(1 for w in arg_keywords if w in user_text_full.lower())
    argumentation_score = max(30, min(100, 40 + arg_count * 8))

    # 2. Словарный запас
    vocab_prompt = f"""
    Проанализируй словарный запас пользователя в дебатах на тему "{topic}" на языке {lang_name}.

    Ответы пользователя:
    {user_text_full[:500]}

    Оцени словарный запас от 1 до 100 и напиши 1 предложение с анализом на русском языке.

    Формат:
    СКОР: [число]
    АНАЛИЗ: [текст на русском]
    """
    vocab_score, vocab_text = _parse_scored_response(
        ask_gpt(vocab_prompt), "СКОР:", "АНАЛИЗ:",
        default_score=70, default_text="Хороший словарный запас для твоего уровня.",
    )

    # 3. Грамматика
    grammar_issues = []
    for error, correction in COMMON_GRAMMAR_ERRORS.items():
        if error in user_text_full.lower():
            grammar_issues.append(f"'{error}' → '{correction}'")

    grammar_score = 100 - len(grammar_issues) * 10
    grammar_score = max(35, grammar_score)

    grammar_prompt = f"""
    Проанализируй грамматику пользователя в дебатах на тему "{topic}" на языке {lang_name}.

    Ответы пользователя:
    {user_text_full[:500]}

    Оцени грамматику от 1 до 100 и напиши 1 предложение с советом на русском языке.

    Формат:
    СКОР: [число]
    СОВЕТ: [текст на русском]
    """
    grammar_score, grammar_advice_text = _parse_scored_response(
        ask_gpt(grammar_prompt), "СКОР:", "СОВЕТ:",
        default_score=grammar_score, default_text="Продолжай практиковаться, грамматика станет лучше!",
    )
    grammar_score = max(35, grammar_score)

    # 4. Беглость
    avg_len = sum(len(r.split()) for r in user_responses) / len(user_responses) if user_responses else 0
    fluency_score = max(30, min(100, round(40 + avg_len * 4)))

    # 5. Реальный уровень
    if avg_len < 5:
        detected_level = "A1"
    elif avg_len < 8:
        detected_level = "A2"
    elif avg_len < 12:
        detected_level = "B1"
    elif avg_len < 18:
        detected_level = "B2"
    elif avg_len < 25:
        detected_level = "C1"
    else:
        detected_level = "C2"

    if grammar_score < 50 and detected_level in ("C1", "C2"):
        detected_level = "B2"
    elif grammar_score < 40 and detected_level in ("B2", "C1"):
        detected_level = "B1"

    if detected_level == level:
        level_emoji = "🔥"
    elif level in ("A1", "A2"):
        level_emoji = "🌱"
    elif level in ("C1", "C2"):
        level_emoji = "💎"
    else:
        level_emoji = "📈"

    # 6. Миссия
    mission_display = ""
    if mission_words:
        words_list = [w.strip() for w in mission_words.split(",")]
        mission_lines = ["📋 МИССИЯ"]
        for word in words_list:
            # Проверяем, есть ли перевод
            if ":" in word:
                word_clean = word.split(":")[0].strip()
            else:
                word_clean = word
            mark = "✅" if word_clean.lower() in user_text_full.lower() else "❌"
            mission_lines.append(f"   {mark} {word}")
        mission_display = "\n".join(mission_lines)

    # 7. Грамматический отчёт
    if grammar_issues:
        grammar_report = "\n".join(f"   ❌ {issue}" for issue in grammar_issues[:5])
        if len(grammar_issues) > 5:
            grammar_report += f"\n   ... и ещё {len(grammar_issues) - 5} замечаний"
        grammar_report += f"\n\n   💡 {grammar_advice_text}"
    else:
        grammar_report = f"   ✅ Грамматика на уровне! Отлично справляешься.\n\n   💡 {grammar_advice_text}"

    return {
        "scores": {
            "argumentation": argumentation_score,
            "vocabulary": vocab_score,
            "grammar": grammar_score,
            "fluency": fluency_score,
        },
        "total_words": total_words,
        "questions": questions,
        "vocab_text": vocab_text,
        "grammar_text": grammar_advice_text,
        "grammar_report": grammar_report,
        "detected_level": detected_level,
        "level_emoji": level_emoji,
        "unique_phrase": "Используй больше связок для усиления аргументов.",
        "moment_text": "",
        "linking_phrases_display": "\n".join(FALLBACK_LINKING_PHRASES.get(level, FALLBACK_LINKING_PHRASES["B1"])),
        "mission_display": mission_display,
        "psychology_text": person.get("psychology", ""),
        "arg_desc": "аргументы есть",
        "vocab_desc": vocab_text,
    }