"""
AI-логика арены: обращение к GPT, реплики персонажей, финальный анализ.

Промпты для реплик персонажей и логика финального разбора перенесены
"один в один" из старого bot.py (start_debate_arena, handle_debate_response,
finish_debate_arena) — только обёрнуты в чистые функции без привязки к
telegram, чтобы было легко переиспользовать и в веб-версии.
"""
import re
import logging

import requests

from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from game_data import (
    LEVEL_DESCRIPTIONS, PERSONALITIES, LANGUAGES, ROLE_STYLE,
    COMMON_GRAMMAR_ERRORS, FALLBACK_LINKING_PHRASES,
)

logger = logging.getLogger(__name__)

GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def ask_gpt(prompt: str, temperature: float = 0.7, max_tokens: int = 500) -> str | None:
    """Синхронный вызов GPT. Вызывай из хендлеров через asyncio.to_thread,
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
        logger.error("GPT error %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("GPT request failed")
    return None


# ---------- Реплики персонажа (оригинальные промпты) ----------

def generate_mission_words(topic: str, level: str, language: str) -> str:
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    prompt = f"""
    Generate 3 advanced vocabulary words for a debate on "{topic}" in {lang_name} for level {level}.
    The words should be appropriate for this level and topic.
    Format: word1, word2, word3
    Just the words, separated by commas.
    """
    return ask_gpt(prompt) or "sustainable, stakeholder, compromise"


def generate_opening_statement(personality: str, topic: str, level: str, language: str) -> str:
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")

    prompt = f"""
    Ты — {person_name}. Ты ведёшь дебаты на тему "{topic}" на языке {lang_name}.

    Уровень собеседника: {level}.

    СТРОГО соблюдай этот уровень:
    {level_desc}

    НЕ используй лексику и конструкции выше этого уровня.

    Сформулируй 1-2 предложения УТВЕРЖДЕНИЕ по теме "{topic}", с которым собеседник может согласиться или не согласиться.
    Это должно быть провокационное, но не агрессивное утверждение в стиле своей роли.

    Ответь ТОЛЬКО утверждением, без лишних слов.

    Примеры:
    - "Remote work destroys corporate culture and should be banned."
    - "Artificial intelligence will replace 80% of jobs within 5 years."
    """
    return ask_gpt(prompt) or f"Let's discuss {topic}. What do you think?"


def generate_ai_response(personality: str, dialogue_history: str, last_user_response: str,
                          level: str, language: str) -> str:
    person_name = PERSONALITIES.get(personality, {}).get("full_name", personality)
    lang_name = LANGUAGES.get(language, {}).get("name", language)
    level_desc = LEVEL_DESCRIPTIONS.get(level, "используй среднюю сложность")
    role_style_text = ROLE_STYLE.get(personality, "продолжай диалог в своей роли")

    prompt = f"""
    Ты — {person_name}. Твоя задача — продолжать дебаты на языке {lang_name}.

    Уровень собеседника: {level}.

    СТРОГО соблюдай этот уровень:
    {level_desc}

    НЕ используй лексику и конструкции выше уровня {level}.

    ТВОЙ СТИЛЬ: {role_style_text}

    История диалога:
    {dialogue_history}

    Последний ответ собеседника:
    {last_user_response}

    ВНИМАНИЕ: Твой ответ ДОЛЖЕН быть связан с последним ответом собеседника.
    Вычлени главную мысль из его ответа и ответь на неё в соответствии со своей ролью.

    ВАЖНО: Не упоминай номера раундов. Просто продолжай диалог естественно.

    Ответь 1-2 предложениями.
    """
    return ask_gpt(prompt) or "That's interesting. Tell me more."


# ---------- Финальный анализ (оригинальная логика finish_debate_arena) ----------

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
    """Полный финальный разбор — аргументация, словарь, грамматика, беглость,
    определение реального уровня, "укради фразу", "момент, который стоил
    победы", связки по уровню и утрированный комментарий персонажа.
    Логика 1:1 перенесена из finish_debate_arena старого бота."""

    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    criteria = person.get("criteria", {})
    lang_name = LANGUAGES.get(language, {}).get("name", "English")

    user_text_full = " ".join(user_responses)
    total_words = len(user_text_full.split())
    questions = sum(1 for r in user_responses if "?" in r)

    # 1. Аргументация — эвристика по маркерам-связкам
    arg_keywords = ["because", "since", "therefore", "thus", "consequently",
                     "for example", "for instance", "however", "although"]
    arg_count = sum(1 for w in arg_keywords if w in user_text_full.lower())
    argumentation_score = max(30, min(100, 40 + arg_count * 8))

    # 2. Словарный запас — через GPT
    vocab_prompt = f"""
    Проанализируй словарный запас пользователя в дебатах на тему "{topic}" на языке {lang_name}.

    Ответы пользователя:
    {user_text_full[:500]}

    Уровень пользователя: {level}

    Задача:
    1. Оцени словарный запас от 1 до 100
    2. Напиши 1-2 предложения с анализом НА РУССКОМ ЯЗЫКЕ
    3. Если есть слова из миссии, отметь их

    Формат ответа:
    СКОР: [число]
    АНАЛИЗ: [текст на русском языке]
    """
    vocab_score, vocab_text = _parse_scored_response(
        ask_gpt(vocab_prompt), "СКОР:", "АНАЛИЗ:",
        default_score=70, default_text="Хороший словарный запас для твоего уровня.",
    )

    # 3. Грамматика — прямой поиск частых ошибок + совет от GPT
    grammar_issues = []
    for error, correction in COMMON_GRAMMAR_ERRORS.items():
        if error in user_text_full.lower():
            grammar_issues.append(f"'{error}' → '{correction}'")

    grammar_score = 100 - len(grammar_issues) * 10
    if level in ("A1", "A2"):
        grammar_score = min(100, grammar_score + 10)
    elif level in ("C1", "C2"):
        grammar_score -= 5
    grammar_score = max(35, grammar_score)

    grammar_prompt = f"""
    Проанализируй грамматику пользователя в дебатах на тему "{topic}" на языке {lang_name}.

    Ответы пользователя:
    {user_text_full[:500]}

    Уровень пользователя: {level}

    Задача:
    1. Оцени грамматику от 1 до 100
    2. Напиши 1-2 предложения с СОВЕТОМ НА РУССКОМ ЯЗЫКЕ

    Формат ответа:
    СКОР: [число]
    СОВЕТ: [текст на русском языке]
    """
    grammar_score, grammar_advice_text = _parse_scored_response(
        ask_gpt(grammar_prompt), "СКОР:", "СОВЕТ:",
        default_score=grammar_score, default_text="Продолжай практиковаться, и грамматика станет лучше!",
    )
    grammar_score = max(35, grammar_score)

    # 4. Беглость — по средней длине ответа
    avg_len = sum(len(r.split()) for r in user_responses) / len(user_responses) if user_responses else 0
    fluency_score = max(30, min(100, round(40 + avg_len * 4)))

    # 5. Определяем реальный уровень по средней длине ответа
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

    # 6. "Укради эту фразу" — сильная идея пользователя, усиленная GPT
    steal_prompt = f"""
    Проанализируй ответы пользователя в дебатах на тему "{topic}" на языке {lang_name}.

    Ответы пользователя:
    {user_text_full[:500]}

    Уровень пользователя: {level}

    Задача:
    1. Найди в ответах пользователя одну сильную или интересную мысль/идею.
    2. Подбери к этой идее КРУТУЮ ФРАЗУ, ИДИОМУ или КОЛЛОКАЦИЮ на языке {lang_name}, которая:
       - соответствует уровню {level}
       - усиливает эту идею
       - звучит естественно и мощно

    Формат ответа (строго соблюдай):

    ИДЕЯ ПОЛЬЗОВАТЕЛЯ: [одна фраза пользователя на языке диалога, до 30 слов]

    УСИЛЕННАЯ ФРАЗА: [твоя фраза/идиома на языке диалога]

    ПЕРЕВОД: [перевод на русский]

    ПОЧЕМУ ЭТО МОЩНО: [1 предложение на русском]
    """
    unique_phrase = ask_gpt(steal_prompt)
    if not unique_phrase or len(unique_phrase) < 20:
        unique_phrase = (
            "ИДЕЯ ПОЛЬЗОВАТЕЛЯ: Ты выразил чёткую позицию по теме.\n\n"
            "УСИЛЕННАЯ ФРАЗА: \"The point is that...\"\n"
            "ПЕРЕВОД: \"Суть в том, что...\"\n\n"
            "ПОЧЕМУ ЭТО МОЩНО: Эта фраза сразу переводит разговор в конструктивное русло."
        )

    # 7. "Момент, который стоил победы" — улучшение самого слабого ответа
    moment_text = ""
    if user_responses:
        weak_response = min(user_responses, key=lambda x: len(x.split()))
        if weak_response and len(weak_response) > 2:
            improve_prompt = f"""
            Дана фраза пользователя в дебатах на тему "{topic}" на языке {lang_name}.

            Фраза пользователя:
            {weak_response}

            Уровень пользователя: {level}

            Задача:
            1. Напиши ЭТУ ЖЕ МЫСЛЬ, но УСИЛЕННУЮ на языке {lang_name}:
               - добавь объяснение (because, since)
               - добавь связку (however, therefore)
               - используй более сильную лексику
            2. ВАЖНЫЕ слова выдели КАПСОМ

            Формат ответа (строго соблюдай, БЕЗ СКОБОК):
            БЫЛО: оригинальная фраза на языке {lang_name}
            ЛУЧШЕ: улучшенная фраза на языке {lang_name} с ВАЖНЫМИ СЛОВАМИ КАПСОМ
            ПОЧЕМУ? 1 предложение на русском
            """
            improved = ask_gpt(improve_prompt)
            if improved and len(improved) > 20:
                lines = []
                for line in improved.split("\n"):
                    if line.startswith("БЫЛО:"):
                        lines.append(f"❌ {line}")
                    elif line.startswith("ЛУЧШЕ:"):
                        lines.append(f"✅ {line}")
                    elif line.startswith("ПОЧЕМУ?"):
                        lines.append(f"❓ {line}")
                    else:
                        lines.append(line)
                moment_text = "📍 МОМЕНТ, КОТОРЫЙ СТОИЛ ПОБЕДЫ\n\n" + "\n".join(lines)
            else:
                trimmed = weak_response[:50] + ("..." if len(weak_response) > 50 else "")
                moment_text = (
                    "📍 МОМЕНТ, КОТОРЫЙ СТОИЛ ПОБЕДЫ\n\n"
                    f"❌ БЫЛО: {trimmed}\n"
                    f"✅ ЛУЧШЕ: {weak_response[:30]} because it directly affects the outcome\n"
                    "❓ ПОЧЕМУ? Нужно объяснять причину, а не просто констатировать факт."
                )

    # 8. Связки по уровню — через GPT, с резервным вариантом
    linking_prompt = f"""
    Дай 3-4 связующие фразы (linking words) для уровня {level} на языке {lang_name}.

    Для каждой фразы дай:
    1. Саму фразу на языке {lang_name}
    2. Перевод на русский
    3. Когда использовать (1-2 слова на русском)

    Формат ответа (каждая фраза с новой строки):
    • фраза — перевод — когда использовать
    """
    linking_phrases = ask_gpt(linking_prompt)
    if not linking_phrases or len(linking_phrases) < 20:
        phrases = FALLBACK_LINKING_PHRASES.get(level, FALLBACK_LINKING_PHRASES["B1"])
        phrases_display = "\n".join(f"   • {p}" for p in phrases)
    else:
        phrases_display = "\n".join(f"   • {p}" for p in linking_phrases.split("\n") if p.strip())

    # 9. Грамматический отчёт
    if grammar_issues:
        grammar_report = "\n".join(f"   ❌ {issue}" for issue in grammar_issues[:5])
        if len(grammar_issues) > 5:
            grammar_report += f"\n   ... и ещё {len(grammar_issues) - 5} замечаний"
        grammar_report += f"\n\n   💡 {grammar_advice_text}"
    else:
        grammar_report = f"   ✅ Грамматика на уровне! Отлично справляешься.\n\n   💡 {grammar_advice_text}"

    # 10. Миссия — проверка использованных слов
    mission_display = ""
    if mission_words:
        words_list = [w.strip() for w in mission_words.split(",")]
        mission_lines = ["📋 МИССИЯ"]
        for word in words_list:
            mark = "✅" if word.lower() in user_text_full.lower() else "❌"
            mission_lines.append(f"   {mark} {word}")
        mission_display = "\n".join(mission_lines)

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
        "unique_phrase": unique_phrase,
        "moment_text": moment_text,
        "linking_phrases_display": phrases_display,
        "mission_display": mission_display,
        "psychology_text": person.get("psychology", ""),
        "arg_desc": criteria.get("argumentation", "аргументы есть"),
        "vocab_desc": vocab_text,
    }
