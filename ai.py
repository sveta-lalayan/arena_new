import re
import random
import logging
import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import (
    LANGUAGES, PERSONALITIES, LEVEL_DESCRIPTIONS, ROLE_STYLE,
    SKILL_TO_PERSONALITY, ARENA_RANKS, ARENA_BEHAVIOURS, PERSONA_TIP_FALLBACK,
)

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


def _normalize_level(level: str) -> str:
    level_key = (level or "B1").strip().upper()
    m = re.match(r"(A1|A2|B1|B2|C1|C2)", level_key)
    return m.group(1) if m else "B1"


# ========== ARENA REACTION (Храм шумит, копает глубже) ==========

def generate_arena_reaction(dialogue_history: str, last_user_response: str, language: str, move_number: int) -> str:
    """
    Храм: живой, проницательный, слегка провокационный. Не просто комментирует —
    копает глубже, переспрашивает, вытаскивает конкретику.
    Номер хода НИКОГДА не попадает в текст пользователю.
    """
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = f"""
    Ты — ARENA. Ты слушаешь человека и хочешь узнать его по-настоящему.
    Ты не просто комментируешь — ты КОПАЕШЬ, ПЕРЕСПРАШИВАЕШЬ, ПРОВОЦИРУЕШЬ.

    Твой ответ должен быть:
    - коротким (1-2 предложения)
    - живым, как реакция внимательного собеседника
    - содержать одну из тактик (выбирай по ситуации):
        * неожиданный уточняющий вопрос ("А что именно тебя в этом зацепило?")
        * лёгкая провокация ("Звучит как отговорка. Попробуй ещё раз.")
        * зеркалирование с обострением ("То есть для тебя это важнее, чем кажется?")
        * требование конкретики ("Дай пример. Один. Реальный.")
        * неожиданный поворот ("А если бы наоборот — что тогда?")
    - НЕ давай оценок ("хорошо", "интересно", "классно")
    - НЕ используй слова "помочь", "assist", "help", "support"
    - НИКОГДА не упоминай номер хода или счётчик
    - Обращайся на "ты"

    Язык: {lang_name}
    Ход (только для твоей ориентации, не упоминай его): {move_number} из 8

    История разговора:
    {dialogue_history}

    Последнее сообщение человека:
    {last_user_response}

    Твой ответ (короче, острее, конкретнее — как будто тебе реально важно понять этого человека):
    """
    response = ask_gpt(prompt, temperature=0.9, max_tokens=180)
    if not response:
        return "Дай пример. Конкретный."
    return response.strip()


# ========== ОРУЖИЕ ПО УРОВНЯМ + ПЕРСОНАЛИЗАЦИЯ ПОД СЛАБЫЕ МЕСТА ==========

def generate_mission_weapons(topic: str, level: str, personality: str, language: str,
                              weak_areas: dict | None = None, weakest_skill: str | None = None) -> tuple:
    """
    Генерирует "оружие" (слова/фразы) под тему, уровень и, если есть разбор
    Храма (weak_areas), — конкретно под слабые места пользователя.

    weak_areas ожидает ключи: grammar_weak_areas (list), vocabulary_weak_areas (list).

    Возвращает (weapons: str, tip: str, win_condition: str).
    Для A1/A2 win_condition упрощённое и добавляется совет-подсказка (tip) —
    как именно разговаривать с этим персонажем, привязанный к слабому скиллу.
    """
    weak_areas = weak_areas or {}
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_key = _normalize_level(level)

    grammar_weak = weak_areas.get("grammar_weak_areas") or []
    vocabulary_weak = weak_areas.get("vocabulary_weak_areas") or []

    weak_focus = ""
    if grammar_weak or vocabulary_weak:
        weak_focus = (
            f" Пользователь слабее всего в: словарь — {', '.join(vocabulary_weak) or 'нет данных'}; "
            f"грамматика — {', '.join(grammar_weak) or 'нет данных'}. "
            f"Подбирай слова/фразы так, чтобы они закрывали именно ЭТИ пробелы, "
            f"а не просто были связаны с темой."
        )

    level_config = {
        "A1": {
            "weapons_prompt": (
                f"Generate 5 simple vocabulary words for debating '{topic}' in {lang_name} "
                f"for beginner level.{weak_focus} "
                f"Format (separated by · ): word1 · word2 · word3 · word4 · word5"
            ),
            "condition": "Сделай заявление.\nДай одну причину.\nИспользуй 3 слова из арсенала.",
        },
        "A2": {
            "weapons_prompt": (
                f"Generate 5 vocabulary words and 2 basic phrases for debating '{topic}' in {lang_name} "
                f"for elementary level.{weak_focus} "
                f"Format (separated by · ): word1 · word2 · word3 · word4 · word5 · phrase1 · phrase2"
            ),
            "condition": "Сделай заявление.\nДай причину.\nПодкрепи примером.",
        },
        "B1": {
            "weapons_prompt": (
                f"Generate 5 collocations and 3 useful phrases for debating '{topic}' in {lang_name} "
                f"for intermediate level.{weak_focus} "
                f"Format (separated by · ): collocation1 · collocation2 · collocation3 · collocation4 · collocation5 · phrase1 · phrase2 · phrase3"
            ),
            "condition": "Сделай заявление.\nПодкрепи доказательством.\nОтветь на возражение.",
        },
        "B2": {
            "weapons_prompt": (
                f"Generate 5 collocations and 4 natural expressions for debating '{topic}' in {lang_name} "
                f"for upper-intermediate level.{weak_focus} "
                f"Format (separated by · ): collocation1 · collocation2 · collocation3 · collocation4 · collocation5 · expression1 · expression2 · expression3 · expression4"
            ),
            "condition": "Оспорь допущение.\nАдаптируй аргумент.\nПриблизь его к согласию.",
        },
        "C1": {
            "weapons_prompt": (
                f"Generate 3 nuanced phrases, 2 rhetorical devices, and 2 idioms for debating '{topic}' in {lang_name} "
                f"for advanced level.{weak_focus} "
                f"Format (separated by · ): nuance1 · nuance2 · nuance3 · rhetoric1 · rhetoric2 · idiom1 · idiom2"
            ),
            "condition": "Переформулируй возражение.\nУступи, не сдавая позицию.\nПриведи к выводу.",
        },
        "C2": {
            "weapons_prompt": (
                f"Generate 3 nuanced expressions, 2 register variations, and 2 implied meaning phrases for "
                f"debating '{topic}' in {lang_name} for expert level.{weak_focus} "
                f"Format (separated by · ): nuance1 · nuance2 · nuance3 · register1 · register2 · implied1 · implied2"
            ),
            "condition": "Держи разговор под контролем.\nАдаптируйся к стилю оппонента.\nВлияй на исход.",
        },
    }

    config = level_config.get(level_key, level_config["B1"])

    weapons_response = ask_gpt(config["weapons_prompt"], temperature=0.7, max_tokens=150)
    if not weapons_response:
        weapons_response = "argue · convince · evidence · logic · debate"

    tip = generate_persona_tip(personality, level_key, weakest_skill, language)

    return weapons_response.strip(), tip, config["condition"]


# Обратная совместимость со старым именем функции.
def generate_weapons_by_level(topic: str, level: str, personality: str, language: str) -> tuple:
    weapons, _tip, win_condition = generate_mission_weapons(topic, level, personality, language)
    return weapons, "", win_condition


def generate_persona_tip(personality: str, level: str, weakest_skill: str | None, language: str) -> str:
    """
    Один конкретный совет: КАК разговаривать именно с этим персонажем, с упором
    на слабый скилл пользователя. Для начальных уровней (A1/A2) это особенно
    важно — вместо сложной "победной формулы" человек получает одну понятную
    подсказку по стилю общения.
    """
    person = PERSONALITIES.get(personality, {})
    role_style = ROLE_STYLE.get(personality, "")
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    skill_line = f"Слабое место ученика, на которое стоит опереться в совете: {weakest_skill}." if weakest_skill else ""

    prompt = f"""
    Дай ОДИН короткий практический совет (1 предложение, на РУССКОМ языке) —
    как эффективнее всего разговаривать с персонажем {person.get('full_name', personality)}
    в разговоре на {lang_name}.

    Характер и стиль поведения персонажа: {role_style}
    {skill_line}
    Уровень ученика: {level}.

    Совет должен быть КОНКРЕТНЫМ и ПРАКТИЧНЫМ (что говорить, с чего начать,
    чего избегать), а не общими словами вроде "будь увереннее".
    Ответь ТОЛЬКО одним предложением, без вступлений и кавычек.
    """
    response = ask_gpt(prompt, temperature=0.6, max_tokens=90)
    if not response:
        return PERSONA_TIP_FALLBACK.get(personality, "Говори по делу и подкрепляй слова примерами.")
    return response.strip().strip('"')


# ========== ЗАДАНИЕ ПО ТЕМЕ (неприкосновенная тема) ==========

def generate_mission_task(topic: str, personality: str, user_name: str, language: str) -> str:
    person = PERSONALITIES.get(personality, {})
    prompt = f"""
    Придумай конкретное задание для {user_name} в разговоре с {person.get('name', 'персонажем')}.

    ТЕМА (НЕ МЕНЯЙ ЕЁ, НЕ ОБОБЩАЙ, НЕ ЗАМЕНЯЙ НА ДРУГУЮ):
    "{topic}"

    Задание должно:
    - быть конкретным
    - напрямую касаться темы "{topic}"
    - звучать как вызов
    - на РУССКОМ языке
    - уложиться в 1 предложение

    Примеры формата (не копируй дословно):
    "Убеди его, что эта идея стоит инвестиций."
    "Заставь его признать, что ты прав."
    "Докажи ей, что твой подход более эффективен."

    Напиши 1 предложение на РУССКОМ языке:
    """
    response = ask_gpt(prompt, temperature=0.6, max_tokens=100)
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
    2) Потом — одна конкретная зона роста, без критики в лоб, по-доброму.
    Без сухих списков, без оценок в процентах, без слова "пользователь".
    Обращайся к {user_name} по имени.

    Вердикт (на РУССКОМ):
    """
    response = ask_gpt(prompt, temperature=0.7, max_tokens=300)
    if not response:
        return f"{user_name}, ты показал интересный подход к разговору. Есть куда расти, но основа хорошая."
    return response.strip()


def generate_growth_plan(user_name: str, strength: str, growth: str, language: str) -> str:
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
    person = PERSONALITIES.get(personality, {})
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


# ========== 3-СЛОЙНЫЙ АНАЛИЗ ХРАМА ==========

def analyze_first_encounter(user_responses: list[str], language: str) -> dict:
    """
    Полный разбор после 8 сообщений в Храме.
    3 слоя: LANGUAGE + COMMUNICATION + ARENA BEHAVIOUR.
    """
    user_text = " ".join(user_responses)
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    prompt = f"""
    Проанализируй ответы пользователя на языке {lang_name} по системе ARENA.

    Ответы пользователя (что он сам рассказал о себе):
    ---
    {user_text[:2500]}
    ---

    === СЛОЙ 1: LANGUAGE ===
    Оцени 4 метрики от 0 до 100 (строго формат "ИМЯ: число"):
    GRAMMAR: [0-100]
    VOCABULARY: [0-100]
    EXPRESSION: [0-100]
    COMPLEXITY: [0-100]

    GRAMMAR_WEAK: [1-2 подкатегории из списка: sentence structure, verb tenses,
    articles, prepositions, word order, agreement, complex structures.
    Разделитель — запятая.]
    VOCABULARY_WEAK: [1-2 подкатегории из списка: range, repetition, precision,
    topic-specific vocabulary, collocations, naturalness, word choice.
    Разделитель — запятая.]

    === СЛОЙ 2: COMMUNICATION ===
    Оцени 6 метрик от 0 до 100:
    CLARITY: [0-100]
    ARGUMENTATION: [0-100]
    EVIDENCE: [0-100]
    ADAPTABILITY: [0-100]
    PERSUASION: [0-100]
    CONTROL: [0-100]

    Скрытая метрика (не будет показана пользователю):
    RESILIENCE: [0-100]

    === СЛОЙ 3: ARENA BEHAVIOUR ===
    Определи ОДИН стиль игрока из списка (ровно одно слово):
    BEHAVIOUR: [analyst | challenger | explorer | precise | defender]

    Расшифровка:
    - analyst: много объясняет, любит логику, может быть сухим
    - challenger: сразу спорит, уверенный, иногда не слушает
    - explorer: легко поддерживает разговор, задаёт вопросы, но может не иметь чёткой позиции
    - precise: краткий и точный, но недостаточно развивает мысль
    - defender: хорошо защищается, но плохо начинает собственную стратегию

    === УРОВЕНЬ И ТЕМЫ ===
    УРОВЕНЬ: [ровно одна из строк: A1, A2, B1, B2, C1, C2 — без пояснений]

    ИНТЕРЕСЫ: [3-5 конкретных тем, которые ЧЕЛОВЕК САМ упомянул.
    Каждая тема — 1-3 слова, разделитель — запятая.
    Используй ЕГО слова, не обобщай.]

    ГЛАВНАЯ_ТЕМА: [одна самая эмоционально заряженная тема из списка.
    Только текст темы, без пояснений.]

    ВАЖНО: отвечай СТРОГО в этом формате, без markdown-разметки
    (никаких ** и ##), без вступлений и без пояснений.
    """
    # Было 600 — конец ответа (УРОВЕНЬ/ИНТЕРЕСЫ/ГЛАВНАЯ_ТЕМА) обрезался,
    # и бот молча падал в дефолты B1 + «то, о чём ты говорил в Храме».
    raw = ask_gpt(prompt, temperature=0.4, max_tokens=900)

    language_metrics = {"grammar": 60, "vocabulary": 60, "expression": 60, "complexity": 60}
    grammar_weak = []
    vocabulary_weak = []

    communication_metrics = {
        "clarity": 60, "argumentation": 60, "evidence": 60,
        "adaptability": 60, "persuasion": 60, "control": 60,
    }
    hidden_metrics = {"resilience": 60}

    behaviour = "explorer"
    estimated_level = "B1"
    interests = []
    main_topic = ""

    def _clean(line: str) -> str:
        # GPT любит markdown: **УРОВЕНЬ:** B1 → УРОВЕНЬ: B1
        for junk in ("**", "__", "`"):
            line = line.replace(junk, "")
        line = re.sub(r"^[\s\-–—*•>]+", "", line.strip())  # маркеры списков
        line = line.replace(" :", ":").replace("：", ":")
        return line.strip()

    if raw:
        level_found = False

        for line in raw.split("\n"):
            line = _clean(line)
            if not line:
                continue

            m = re.match(r"([A-Za-z_]+):\s*(\d+)", line)
            if m:
                key = m.group(1).lower()
                value = max(0, min(100, int(m.group(2))))
                if key in language_metrics:
                    language_metrics[key] = value
                elif key in communication_metrics:
                    communication_metrics[key] = value
                elif key in hidden_metrics:
                    hidden_metrics[key] = value
                continue

            upper = line.upper()

            if upper.startswith("GRAMMAR_WEAK"):
                s = line.split(":", 1)[1] if ":" in line else ""
                grammar_weak = [x.strip(" .") for x in re.split(r"[,;]", s) if x.strip()]
            elif upper.startswith("VOCABULARY_WEAK"):
                s = line.split(":", 1)[1] if ":" in line else ""
                vocabulary_weak = [x.strip(" .") for x in re.split(r"[,;]", s) if x.strip()]
            elif upper.startswith("BEHAVIOUR"):
                b = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                b = b.split()[0].strip(" .,;") if b else ""  # "analyst — объясняет" → "analyst"
                if b in ARENA_BEHAVIOURS:
                    behaviour = b
            elif upper.startswith("УРОВЕНЬ"):
                lvl_match = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", upper)
                if lvl_match:
                    estimated_level = lvl_match.group(1)
                    level_found = True
            elif upper.startswith("ИНТЕРЕС"):
                s = line.split(":", 1)[1] if ":" in line else ""
                if s:
                    interests = [x.strip(" .\"'«»") for x in re.split(r"[,;·]", s) if x.strip()]
            elif upper.startswith("ГЛАВНАЯ_ТЕМА") or upper.startswith("ГЛАВНАЯ ТЕМА"):
                s = line.split(":", 1)[1] if ":" in line else ""
                main_topic = s.strip(" .\"'«»")

        # Последний шанс найти уровень, если GPT вывел его вне формата
        if not level_found:
            lvl_match = re.search(r"\b(A1|A2|B1|B2|C1|C2)\b", raw.upper())
            if lvl_match:
                estimated_level = lvl_match.group(1)

    if not interests:
        interests = ["то, о чём ты говорил в Храме"]
    if not main_topic:
        main_topic = interests[0]

    weakest_skill = min(communication_metrics, key=communication_metrics.get)
    strongest_skill = max(communication_metrics, key=communication_metrics.get)
    recommended_personality = SKILL_TO_PERSONALITY.get(
        weakest_skill, random.choice(list(PERSONALITIES.keys()))
    )

    arena_rank = ARENA_RANKS.get(weakest_skill, {
        "rank": "I", "name": "SPEAK", "goal": "state your opinion", "tools": "words",
    })

    return {
        "estimated_level": estimated_level,
        "interests": interests,
        "main_topic": main_topic,

        "language": language_metrics,
        "grammar_weak_areas": grammar_weak,
        "vocabulary_weak_areas": vocabulary_weak,

        "communication": communication_metrics,
        "hidden": hidden_metrics,

        "behaviour": behaviour,

        "weakest_skill": weakest_skill,
        "strongest_skill": strongest_skill,
        "recommended_personality": recommended_personality,
        "arena_rank": arena_rank,

        "strength": strongest_skill,
        "growth": weakest_skill,
    }


def generate_arena_observation(user_responses: list[str], language: str, level: str,
                               strongest_skill: str, weakest_skill: str) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")
    user_text = " ".join(user_responses)[:1200]

    prompt = f"""
    Ты — ARENA, верховный судья. Ты только что выслушал человека (8 реплик).

    Что он говорил: {user_text}
    Его сильная сторона в общении: {strongest_skill}
    Его слабая сторона в общении: {weakest_skill}

    Напиши 4-5 КОРОТКИХ рубленых строк (каждая мысль — своя строка, максимум
    5-7 слов), СТРОГО на языке {lang_name}, сложность речи — уровень {level}
    ({level_desc}).

    Стиль (не копируй дословно, только структуру и длину строк):
    "That was interesting.
    You have a point of view.
    You don't always make it easy to challenge you.
    But I noticed something.
    You have more to say than you initially show."

    Естественно вплети его сильную сторону, без ярлыков и процентов.
    Последняя строка обязательно — короткий переход в духе
    "So I know who you should meet." (переведи эту мысль на {lang_name},
    не называй имя персонажа — оно будет добавлено отдельно).
    Обращайся на "ты"/"you". Никогда не говори "участник"/"пользователь".
    Ответь ТОЛЬКО этими строками, без вступлений и заголовков.
    """
    response = ask_gpt(prompt, temperature=0.8, max_tokens=180)
    if not response:
        return "That was interesting.\nYou have more to say than you show.\nSo I know who you should meet."
    return response.strip()


def generate_character_pitch(personality: str, topic: str, language: str, level: str) -> str:
    person = PERSONALITIES.get(personality, {})
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")

    prompt = f"""
    Персонаж: {person.get('full_name', personality)} — {person.get('desc', '')}
    Тема разговора: {topic}

    Напиши 3-4 КОРОТКИХ рубленых строки (каждая — отдельная мысль, максимум
    5-8 слов), СТРОГО на языке {lang_name}, сложность речи — уровень {level}
    ({level_desc}), объясняющих, почему стоит поговорить именно с этим
    персонажем прямо сейчас.

    Стиль (не копируй дословно, только структуру и длину строк):
    "She's heard every 'great idea' before.
    Bring her something she hasn't heard.
    She controls the budget.
    She's not convinced."

    Ответь ТОЛЬКО этими строками, без вступлений, без имени персонажа в тексте.
    """
    response = ask_gpt(prompt, temperature=0.8, max_tokens=140)
    if not response:
        return "They won't be easily convinced.\nBring your best argument."
    return response.strip()


# ========== АНАЛИЗ БОЯ (для finish_arena) ==========

def analyze_debate(user_responses: list[str], dialogue: list[dict], topic: str, level: str, language: str,
                   personality: str, mission_words: str = "", quest_description: str = "") -> dict:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", "English")
    user_text_full = " ".join(user_responses)

    arg_keywords = ["because", "since", "therefore", "however", "although", "but"]
    arg_count = sum(1 for w in arg_keywords if w in user_text_full.lower())
    argumentation_score = max(30, min(100, 40 + arg_count * 10))

    vocab_prompt = f"Оцени словарный запас пользователя на {lang_name}. Ответы: {user_text_full[:500]}\nФормат: СКОР: [число]"
    vocab_raw = ask_gpt(vocab_prompt, temperature=0.5, max_tokens=50)
    vocab_score = 70
    if vocab_raw:
        nums = re.findall(r"\d+", vocab_raw)
        if nums:
            vocab_score = min(100, int(nums[0]))

    grammar_prompt = f"Оцени грамматику пользователя на {lang_name}. Ответы: {user_text_full[:500]}\nФормат: СКОР: [число]"
    grammar_raw = ask_gpt(grammar_prompt, temperature=0.5, max_tokens=50)
    grammar_score = 70
    if grammar_raw:
        nums = re.findall(r"\d+", grammar_raw)
        if nums:
            grammar_score = min(100, int(nums[0]))

    avg_len = sum(len(r.split()) for r in user_responses) / len(user_responses) if user_responses else 0
    fluency_score = max(30, min(100, round(40 + avg_len * 4)))

    quest_block = f"""
    === КВЕСТ ===
    Проверь, выполнил ли пользователь квест: {quest_description or "нет квеста"}
    КВЕСТ_ВЫПОЛНЕН: [да / нет]
    """ if quest_description else ""

    verdict_prompt = f"""
    Проанализируй ответы пользователя с {person['full_name']} на тему "{topic}".
    Язык: {lang_name}.
    Уровень: {level}.
    Ответы: {user_text_full[:1500]}

    Формат:
    СИЛЬНЫЙ_МОМЕНТ: [1 предложение на русском — что было круто]
    ЗОНА_РОСТА: [1 предложение на русском — что доработать]
    ФРАЗА: [одна фраза на {lang_name} длиной 4-10 слов]

    === УБЕЖДЁННОСТЬ ===
    Оцени, насколько персонаж убеждён аргументами пользователя (0 = полностью убеждён, 100 = не убеждён вообще).
    УБЕЖДЁННОСТЬ: [число 0-100]
    {quest_block}
    """
    verdict_raw = ask_gpt(verdict_prompt, temperature=0.6, max_tokens=350)

    moment_text = ""
    unique_phrase = "Используй больше связок."
    conviction_score = 70
    quest_done = False

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
            elif "УБЕЖДЁННОСТЬ" in line.upper():
                nums = re.findall(r"\d+", line)
                if nums:
                    conviction_score = max(0, min(100, int(nums[0])))
            elif "КВЕСТ_ВЫПОЛНЕН" in line.upper():
                if "да" in line.lower():
                    quest_done = True

    return {
        "scores": {
            "argumentation": argumentation_score,
            "vocabulary": vocab_score,
            "grammar": grammar_score,
            "fluency": fluency_score,
        },
        "unique_phrase": unique_phrase,
        "moment_text": moment_text,
        "conviction": conviction_score,
        "quest_done": quest_done,
    }