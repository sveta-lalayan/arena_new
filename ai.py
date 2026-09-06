import re
import logging
import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import LANGUAGES, PERSONALITIES, LEVEL_DESCRIPTIONS

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


def generate_arena_reaction(dialogue_history: str, last_user_response: str, language: str, move_number: int) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = f"""
    Ты — ARENA. Внимательно слушай человека.
    Ответь естественно, как живой человек.
    Язык: {lang_name}
    История: {dialogue_history}
    Человек: {last_user_response}
    Твой ответ (1-2 предложения):
    """
    response = ask_gpt(prompt, temperature=0.8, max_tokens=150)
    if not response:
        return "Понятно. Расскажи подробнее."
    return response.strip()


def generate_mission_words(topic: str, level: str, language: str) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = f"""
    Generate 5 vocabulary words for debating "{topic}" in {lang_name} for level {level}.
    Format: word1, word2, word3, word4, word5
    """
    return ask_gpt(prompt) or "argue, convince, evidence, logic, debate"


def generate_tips(personality: str) -> str:
    person = PERSONALITIES.get(personality, {})
    prompt = f"""
    Дай 3 коротких совета как общаться с {person.get('name', 'собеседником')}.
    Формат: совет1 · совет2 · совет3
    """
    return ask_gpt(prompt) or "Будь уверен · Приводи примеры · Слушай внимательно"


def generate_opening_statement(personality: str, topic: str, level: str, language: str) -> str:
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")
    prompt = f"""
    Ты — {person_name}. Начни дебаты на тему "{topic}" на языке {lang_name}.
    Уровень собеседника: {level}. {level_desc}
    Скажи 1-2 предложения — жёсткое утверждение, в своём характере.
    """
    return ask_gpt(prompt, temperature=0.8, max_tokens=100) or f"Let's discuss {topic}."


def generate_ai_response(personality: str, dialogue_history: str, last_user_response: str, level: str,
                         language: str, mission: str = None) -> str:
    """
    mission — короткое напоминание о том, чего персонаж добивается от пользователя
    в этом бою (например: "Убедить Sarah, что тема X стоит внимания").
    Подмешивается в промпт на КАЖДОМ ходу, чтобы персонаж не "забывал" миссию
    и не соскальзывал в обычный small talk посреди боя.
    """
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "")

    mission_block = ""
    if mission:
        mission_block = f"""
    ТВОЯ МИССИЯ В ЭТОМ РАЗГОВОРЕ (никогда не забывай её и не отклоняйся от неё):
    {mission}
    Если пользователь уходит от темы — верни его к миссии в своём характере,
    не переключайся на посторонний small talk.
    """

    prompt = f"""
    Ты — {person_name}. Продолжай диалог на {lang_name}.
    {mission_block}
    Уровень собеседника: {level}. {level_desc}
    История: {dialogue_history}
    Последний ответ: {last_user_response}
    Твой ответ (1-2 предложения, в своём характере, не забывай про миссию):
    """
    return ask_gpt(prompt) or "That's interesting. Tell me more."


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
                result["interests"] = [i.strip() for i in line.replace("ИНТЕРЕСЫ:", "").split(",")]
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