"""
AI-логика арены: обращение к Yandex GPT, реплики персонажей, анализ ответов.
Чистые функции без привязки к telegram — их удобно тестировать и переиспользовать.
"""
import re
import logging

import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import LEVEL_DESCRIPTIONS, PERSONALITIES, LANGUAGES

logger = logging.getLogger(__name__)

GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def ask_gpt(prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str | None:
    """Синхронный вызов Yandex GPT. Вызывай из хендлеров через asyncio.to_thread,
    чтобы не блокировать event loop."""
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
        logger.error("Yandex GPT error %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Yandex GPT request failed")
    return None


def generate_mission_words(topic: str, level: str, language: str) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = (
        f'Generate 3 advanced vocabulary words for a debate on "{topic}" '
        f"in {lang_name} for level {level}. "
        "Format: word1, word2, word3. Just the words, separated by commas."
    )
    return ask_gpt(prompt) or "sustainable, stakeholder, compromise"


def generate_opening_statement(personality: str, topic: str, level: str, language: str) -> str:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")

    prompt = f"""
    Ты — {person['full_name']}. Ты ведёшь дебаты на тему "{topic}" на языке {lang_name}.
    Уровень собеседника: {level}. СТРОГО соблюдай: {level_desc}.
    НЕ используй лексику и конструкции выше этого уровня.

    Сформулируй 1-2 предложения-УТВЕРЖДЕНИЕ по теме "{topic}", провокационное, но не агрессивное,
    в стиле своей роли. Ответь ТОЛЬКО утверждением, без лишних слов.
    """
    return ask_gpt(prompt) or f"Let's discuss {topic}. What do you think?"


def generate_ai_response(personality: str, dialogue_history: str, last_user_response: str,
                          level: str, language: str) -> str:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")

    prompt = f"""
    Ты — {person['full_name']}. Продолжай дебаты на языке {lang_name}.
    Уровень собеседника: {level}. СТРОГО соблюдай: {level_desc}.
    ТВОЙ СТИЛЬ: {person['style']}.

    История диалога:
    {dialogue_history}

    Последний ответ собеседника:
    {last_user_response}

    Ответ должен быть связан с последней репликой собеседника — вычлени главную мысль
    и отреагируй на неё в своей роли. Не упоминай номера раундов. Ответь 1-2 предложениями.
    """
    return ask_gpt(prompt) or "That's interesting. Tell me more."


def analyze_debate(user_responses: list[str], topic: str, level: str, language: str) -> dict:
    """Анализирует ответы пользователя и возвращает баллы + краткий текстовый фидбэк."""
    user_text_full = " ".join(user_responses)
    lang_name = LANGUAGES.get(language, {}).get("name", language)

    # Аргументация — эвристика по маркерам-связкам
    arg_keywords = ["because", "since", "therefore", "thus", "consequently",
                     "for example", "for instance", "however", "although"]
    arg_count = sum(1 for w in arg_keywords if w in user_text_full.lower())
    argumentation_score = max(30, min(100, 40 + arg_count * 8))

    # Словарный запас — через GPT, с эвристическим фолбэком
    vocab_prompt = f"""
    Проанализируй словарный запас пользователя в дебатах на тему "{topic}" на языке {lang_name}.
    Ответы: {user_text_full[:500]}
    Уровень пользователя: {level}
    Оцени от 1 до 100 и напиши 1-2 предложения анализа на русском.
    Формат:
    СКОР: [число]
    АНАЛИЗ: [текст]
    """
    vocab_score, vocab_text = _parse_scored_response(
        ask_gpt(vocab_prompt), "СКОР:", "АНАЛИЗ:",
        default_score=70, default_text="Хороший словарный запас для твоего уровня.",
    )

    # Грамматика — через GPT, с эвристическим фолбэком
    grammar_prompt = f"""
    Проанализируй грамматику пользователя в дебатах на тему "{topic}" на языке {lang_name}.
    Ответы: {user_text_full[:500]}
    Уровень пользователя: {level}
    Оцени от 1 до 100 и напиши 1-2 предложения совета на русском.
    Формат:
    СКОР: [число]
    СОВЕТ: [текст]
    """
    grammar_score, grammar_text = _parse_scored_response(
        ask_gpt(grammar_prompt), "СКОР:", "СОВЕТ:",
        default_score=75, default_text="Продолжай практиковаться, и грамматика станет лучше!",
    )

    # Беглость — по средней длине ответа
    avg_len = sum(len(r.split()) for r in user_responses) / len(user_responses) if user_responses else 0
    fluency_score = max(30, min(100, round(40 + avg_len * 4)))

    return {
        "scores": {
            "argumentation": argumentation_score,
            "vocabulary": vocab_score,
            "grammar": grammar_score,
            "fluency": fluency_score,
        },
        "vocab_text": vocab_text,
        "grammar_text": grammar_text,
    }


def _parse_scored_response(raw: str | None, score_marker: str, text_marker: str,
                            default_score: int, default_text: str) -> tuple[int, str]:
    score, text = default_score, default_text
    if raw and len(raw) > 10:
        for line in raw.split("\n"):
            if score_marker in line:
                nums = re.findall(r"\d+", line)
                if nums:
                    score = max(30, min(100, int(nums[0])))
            if text_marker in line:
                text = line.split(text_marker, 1)[1].strip()
    return score, text
