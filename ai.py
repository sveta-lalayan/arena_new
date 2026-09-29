"""
ai.py — GPT-слой ARENA.

Правила:
 1. Всё, что «говорят» Арена и персонажи (реакции, миссии, реплики, дебрифы,
    пуши), пишется СТРОГО на learning_language пользователя. Если модель
    проскользнула в кириллицу на не-русском языке — делаем повторную попытку,
    иначе возвращаем None (сработает fallback).
 2. Сложность речи подгоняется под CEFR-уровень.
 3. UI никогда не проходит через этот файл — только локали в locales/*.json.
 4. Если OpenAI недоступен — функции возвращают безопасные значения, бот не падает.
"""
import json
import logging
import random
import re

from openai import OpenAI, APIStatusError, APIConnectionError

from config import OPENAI_API_KEY, OPENAI_MODEL, FIRST_ENCOUNTER_MOVES
from game_data import (
    LANG_PROMPT_NAME, LEVELS, LEVEL_PROMPTS, PERSONALITIES, PERSONA_BRIEFS, SPEECH_STYLE,
    MISSION_FORMAT_BY_PERSONALITY, SKILL_TO_PERSONALITY, COMMUNICATION_SKILLS,
    LANGUAGE_CRITERIA, ALL_CRITERIA, BEHAVIOUR_BRIEFS, BEGINNER_LEVELS, ARENA_RANKS,
    ARSENAL_TOOL_KEYS, ARSENAL_TOOL_DEFS,
)

logger = logging.getLogger(__name__)

_client = None
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
BEHAVIOURS = list(BEHAVIOUR_BRIEFS)


# ==================================================================
# НИЗКОУРОВНЕВЫЕ ХЕЛПЕРЫ
# ==================================================================

def _get_client():
    global _client
    if _client is None and OPENAI_API_KEY:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=45)
    return _client


def _lang(language: str) -> str:
    """language — ISO-код (en/ru/…) или старый ключ (english)."""
    return LANG_PROMPT_NAME.get(language, LANG_PROMPT_NAME.get(
        {"english": "en", "russian": "ru", "german": "de", "spanish": "es",
         "italian": "it", "korean": "ko", "chinese": "zh"}.get(language, "en"),
        "English"
    ))


def _lv(level: str) -> str:
    return LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["B1"])


def _system(language: str, extra: str = "") -> str:
    lang = _lang(language)
    return (
        f"You are part of ARENA, a language-training game where learners debate characters. "
        f"Write ONLY in {lang}. Never write any other language, even if the learner's message "
        f"or these instructions contain other languages. {extra}".strip()
    )


def _chat(system: str, prompt: str, temperature: float = 0.7, max_tokens: int = 400,
          json_mode: bool = False) -> str | None:
    client = _get_client()
    if client is None:
        logger.error("OpenAI client не создан — проверь OPENAI_API_KEY в окружении")
        return None
    kwargs = dict(
        model=OPENAI_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except APIStatusError as e:
        # HTTP-ошибка от самого OpenAI (403 = блок по стране/аккаунту, 429 = квота/рейт-лимит,
        # 401 = неверный ключ и т.д.) — тело ответа обычно прямо называет причину.
        body = None
        try:
            body = e.response.text
        except Exception:
            pass
        logger.error("OpenAI API error: status=%s body=%s", e.status_code, body)
        return None
    except APIConnectionError:
        # Запрос не дошёл до OpenAI вообще (сеть/DNS/таймаут/блокировка на уровне сети,
        # а не HTTP-ответ от самого OpenAI).
        logger.error("OpenAI connection error — запрос не дошёл до api.openai.com "
                     "(проверь сеть/файрвол сервера)")
        return None
    except Exception:
        logger.exception("OpenAI chat error (непредвиденное)")
        return None


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip().strip('"“”«»').strip()
    return text or None


def _ask(prompt: str, language: str, temperature: float = 0.7, max_tokens: int = 300) -> str | None:
    """
    Проза на языке пользователя. Кириллицу отсекаем, если язык не русский.
    """
    system = _system(language)
    text = _chat(system, prompt, temperature, max_tokens)
    if text and _lang(language) != "Russian" and _CYRILLIC.search(text):
        text = _chat(
            system + f" Your previous answer contained the wrong language. Answer again STRICTLY in {_lang(language)}.",
            prompt, temperature, max_tokens,
        )
        if text and _CYRILLIC.search(text):
            return None
    return _clean(text)


def ask_gpt_in_language(prompt: str, language: str,
                        temperature: float = 0.7, max_tokens: int = 300) -> str | None:
    return _ask(prompt, language, temperature, max_tokens)


def _parse_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else None
            except ValueError:
                return None
    return None


def _ask_json(prompt: str, language: str, temperature: float = 0.4, max_tokens: int = 800,
              check_ru: bool = False) -> dict | None:
    system = _system(language)
    prompt = prompt + "\n\nReturn ONLY one valid JSON object."
    raw = _chat(system, prompt, temperature, max_tokens, json_mode=True)
    if check_ru and raw and _lang(language) != "Russian" and _CYRILLIC.search(raw):
        raw = _chat(system + f" Your previous answer contained the wrong language. Use ONLY {_lang(language)}.",
                    prompt, temperature, max_tokens, json_mode=True) or raw
    return _parse_json(raw)


def _score(v, default=50) -> int:
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _scores(d, keys) -> dict:
    d = d if isinstance(d, dict) else {}
    return {k: _score(d.get(k)) for k in keys}


def _no_ru(s) -> str:
    s = s.strip() if isinstance(s, str) else ""
    return "" if _CYRILLIC.search(s) else s


def _persona(personality: str) -> str:
    brief = PERSONA_BRIEFS.get(personality, PERSONA_BRIEFS["devil_advocate"])
    style = SPEECH_STYLE.get(personality, "")
    return (
        f"{brief} Concrete speech habits — SHOW these in every reply, not just when there's conflict "
        f"to react to, including plain small talk: {style} "
        "Stay strictly in this character's voice and personality at all times — "
        "never slip into a neutral, generic, friendly-chatbot tone, even in casual chat or under pressure. "
        "IMPORTANT: a higher language level for the learner means richer VOCABULARY and GRAMMAR — it "
        "does NOT mean you become more formal, academic, or lecture-y. Stay exactly as blunt/playful/"
        "provocative/casual as your character naturally is, even when using more advanced words. Real "
        "people don't turn into professors just because they use bigger words — keep short reactions, "
        "interruptions, sarcasm, humor, whatever fits THIS character, at every level."
    )


def format_history(dialogue: list, char_name: str, last: int = 14) -> str:
    return "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else char_name}: {d['text']}"
        for d in dialogue[-last:]
    )


# ==================================================================
# ХРАМ
# ==================================================================

def generate_arena_reaction(history: str, user_text: str, language: str, turn: int) -> str | None:
    prompt = f"""
You are ARENA — a supreme, terse, slightly sharp presence that is listening to a newcomer.
This is their message number {turn} of {FIRST_ENCOUNTER_MOVES}. You do not know their language level yet:
mirror it — keep your sentences NO more complex than theirs.

Conversation so far:
{history}

They just said: "{user_text}"

React in 1-2 SHORT sentences: pick up ONE concrete detail they mentioned, then ask ONE short follow-up
question that digs into what they care about. No praise, no lists, no greeting, no emojis.
"""
    return _ask(prompt, language, temperature=0.8, max_tokens=120)


def _normalize_analysis(data: dict | None) -> dict:
    data = data or {}
    comm = _scores(data.get("communication"), COMMUNICATION_SKILLS)
    lang = _scores(data.get("language"), LANGUAGE_CRITERIA)
    weakest = min(comm, key=comm.get)
    strongest = max(comm, key=comm.get)
    level = data.get("estimated_level")
    behaviour = data.get("behaviour")
    personality = data.get("recommended_personality")

    interests = [t.strip() for t in (data.get("interests") or []) if isinstance(t, str) and t.strip()][:5]
    main_topic = (data.get("main_topic") or "").strip() if isinstance(data.get("main_topic"), str) else ""
    if not main_topic and interests:
        main_topic = interests[0]
    if main_topic and main_topic not in interests:
        interests.insert(0, main_topic)

    def _list(key):
        return [s for s in (data.get(key) or []) if isinstance(s, str)][:3]

    pattern = (data.get("pattern") or "").strip() if isinstance(data.get("pattern"), str) else ""
    pattern_evidence = [e for e in (data.get("pattern_evidence") or []) if isinstance(e, (str, int))][:5]

    return {
        "estimated_level": level if level in LEVELS else "B1",
        "language": lang,
        "communication": comm,
        "hidden": {"resilience": _score((data.get("hidden") or {}).get("resilience"))},
        "behaviour": behaviour if behaviour in BEHAVIOURS else "explorer",
        "grammar_weak_areas": _list("grammar_weak_areas"),
        "vocabulary_weak_areas": _list("vocabulary_weak_areas"),
        "interests": interests,
        "main_topic": main_topic,
        "strongest_skill": strongest,
        "weakest_skill": weakest,
        "arena_rank": ARENA_RANKS[weakest],
        "recommended_personality": personality if personality in PERSONALITIES else SKILL_TO_PERSONALITY[weakest],
        "pattern": pattern,
        "pattern_evidence": pattern_evidence,
    }


def analyze_first_encounter(user_responses: list[str], language: str) -> dict:
    """
    Разбор Храма по 10 критериям + определение ОДНОГО коммуникационного паттерна,
    который реально видно в диалоге, с явной ссылкой на реплики-доказательства.
    """
    lang = _lang(language)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(user_responses))

    prompt = f"""
You are ARENA's analyst. A learner of {lang} wrote these messages (their target language is {lang}):
{numbered}

Assess them. Score every criterion 0-100 RELATIVE to the learner's own CEFR level: a learner who performs
cleanly for their level scores 70-90; many errors or very thin answers score below 50.

Additionally: identify ONE concrete communication pattern visible in the way they speak. Pick from these
patterns (do not invent new ones):
- states opinions but does not support them
- gives reasons but weak evidence
- repeats the same point under pressure
- struggles to adapt to another person's priorities
- explains too much instead of answering directly
- avoids disagreement
- becomes vague when challenged
- strong vocabulary but weak conversational control
- persuades through information rather than relevance
- gives examples but does not connect them to the argument
- answers the question but does not control the direction of the conversation

Return a JSON object with EXACTLY these keys:
- "estimated_level": one of {LEVELS}
- "language": {{"grammar": int, "vocabulary": int, "fluency": int, "naturalness": int}}
- "communication": {{"clarity": int, "argumentation": int, "adaptability": int, "persuasion": int, "evidence": int, "control": int}}
- "hidden": {{"resilience": int}}
- "behaviour": one of {BEHAVIOURS}. Meaning: {json.dumps(BEHAVIOUR_BRIEFS)}
- "grammar_weak_areas": up to 3 short English strings
- "vocabulary_weak_areas": up to 3 short English strings
- "interests": 3-5 short topic phrases (1-4 words each) in {lang}, taken from what they ACTUALLY talked about
- "main_topic": the ONE topic they care about most, 2-5 words, in {lang}
- "recommended_personality": one of {list(PERSONALITIES)}. Pick the character who best fits BOTH their main
  topic AND their weakest communication skill.
- "pattern": the ONE pattern phrase (from the list above), lowercase, exactly as written
- "pattern_evidence": list of 2-4 short quotes (VERBATIM from their messages) that justify the pattern
"""
    data = _ask_json(prompt, language, temperature=0.3, max_tokens=800)
    if not data:
        logger.warning("analyze_first_encounter: пустой ответ, значения по умолчанию")
    return _normalize_analysis(data)


def analyze_freetalk(user_responses: list[str], language: str) -> dict:
    return analyze_first_encounter(user_responses, language)


def generate_arena_observation(user_name: str, user_responses: list[str], language: str, level: str,
                               topic: str, personality: str, weakest_skill: str,
                               pattern: str = "") -> str:
    """
    Наблюдение после Храма. Если pattern известен — обязательно связать его
    с реальными словами пользователя, а не с общими фразами.
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    said = "\n".join(f"- {t}" for t in user_responses[-8:])
    pattern_line = (
        f"The pattern you spotted in them (use plain words, do NOT name it as a label): {pattern}."
        if pattern else ""
    )

    prompt = f"""
You are ARENA, the supreme voice of a language arena: terse, sharp, a little cold, but you respect effort.
You just listened to {user_name or 'a newcomer'} for several minutes. Their level is {level}: {_lv(level)}
Write it so THEY can read it comfortably.

What they said:
{said}

{pattern_line}

Write exactly 3 short lines separated by blank lines:
1. ONE punchy, slightly biting "wow" sentence about them (max 12 words), referring to something real they said.
2. One sentence showing the pattern in their OWN words (paraphrase what they did, no psychology terms).
3. One sentence: because of this, you're bringing someone who will push on exactly that — and name
   {person['full_name']} naturally.

Address them by name ({user_name}) once. No emojis, no lists, no headings.
"""
    return _ask(prompt, language, temperature=0.85, max_tokens=240) or ""


def generate_character_pitch(personality: str, topic: str, language: str, level: str,
                             first_name: str = "", weakest_skill: str = "") -> str:
    focus = f"You will train their weak spot: {weakest_skill}." if weakest_skill else ""
    prompt = f"""
You are {_persona(personality)}
Introduce yourself to a language learner{f' named {first_name}' if first_name else ''} in 2 SHORT sentences,
fully in character: say what you are about to do to them in a battle about "{topic}" and throw down a challenge.
{focus} Their level is {level}: {_lv(level)}
No emojis, no stage directions, no quotation marks.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=140) or ""


# ==================================================================
# БОЙ
# ==================================================================

def generate_mission_task(topic: str, personality: str, user_name: str, language: str,
                          level: str, pattern: str = "") -> str:
    """
    Короткая (максимум 8 слов), game-like миссия — без «convince X that Y»,
    без «take seriously», без академической структуры.

    Хорошо:
      "Change his mind."
      "Get the budget."
      "Make her reconsider."
      "Defend your decision."
      "Get him to commit."

    Плохо:
      "Convince Professor Adams that unpredictable weather is more harmful than helpful."
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    prompt = f"""
Write ONE ultra-short mission statement for a game-like battle.
Character the learner faces: {person['short_name']}.
Topic context (do NOT repeat it in the mission): "{topic}".

Rules:
- MAXIMUM 5 words.
- Game-like, outcome-oriented, second person.
- Do NOT mention the topic, do NOT mention the character's name.
- Do NOT use words like "convince", "explain", "argue", "support", "provide", "thesis", "examples".
- Never longer than 5 words. Period.

Good examples (do NOT copy, just match the LENGTH and TONE):
"Change his mind."
"Get the budget."
"Make her reconsider."
"Defend your decision."
"Get him to commit."

Bad examples (never produce anything like these):
"Convince Professor Adams that unpredictable weather is more harmful than helpful."
"Provide a clear thesis and support it with examples."
"Take a clear position and defend it with evidence."

Answer with ONE line, no quotes, no punctuation at the end except a period.
"""
    raw = _ask(prompt, language, temperature=0.85, max_tokens=40)
    if not raw:
        return "Change his mind."
    # страховка: жёстко обрезаем до 5 слов
    words = raw.strip().strip('"“”«»').split()
    return " ".join(words[:5]).rstrip(".!?") + "."


def generate_mission_weapons(topic: str, level: str, personality: str, language: str,
                             weak_areas: dict | None = None, weakest_skill: str | None = None):
    weak_areas = weak_areas or {}
    n = 4 if level in BEGINNER_LEVELS else 5
    kind = ("simple single words" if level in BEGINNER_LEVELS
            else "useful short phrases, connectors and collocations (1-3 words each)")

    prompt = f"""
Prepare the "arsenal" for a debate battle.
Character: {_persona(personality)}
Topic: "{topic}". Learner level: {level}: {_lv(level)}
Learner weak spots — grammar: {weak_areas.get('grammar_weak_areas', [])}, vocabulary: {weak_areas.get('vocabulary_weak_areas', [])},
weakest communication skill: {weakest_skill or 'unknown'}.

Return JSON with:
- "weapons": list of exactly {n} items: {kind}. Each must be short enough that the learner can type it verbatim
  in an argument about this topic, and fit their level.
- "tip": ONE short sentence: how to talk to THIS character to win.
- "win_condition": 1-2 short lines: what exactly will convince THIS character (specific to the topic).
All text in {_lang(language)}.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=350, check_ru=True) or {}
    raw = data.get("weapons") or []
    weapons_list = [
        w.strip() for w in raw
        if isinstance(w, str) and w.strip()
        and (_lang(language) == "Russian" or not _CYRILLIC.search(w))
    ][:n]
    return " · ".join(weapons_list), _no_ru(data.get("tip")), _no_ru(data.get("win_condition"))


def generate_opening_statement(personality: str, topic: str, level: str, language: str,
                               mission: str = "") -> str:
    """
    Первая реплика персонажа. Не «What do you think?», а конкретная
    оппозиция + один вызов, который заставляет отвечать.
    """
    prompt = f"""
You are {_persona(personality)}

A learner just entered a battle with you. Topic: "{topic}". Your mission (for them): {mission}.

Open the battle — 1-2 short sentences:
1. State YOUR concrete position on "{topic}". Be a bit skeptical or contrarian, not neutral.
2. End with ONE direct question that forces them to defend their view.

Rules:
- Do NOT say "What do you think?" and do NOT ask them to introduce themselves.
- Do NOT explain the rules, the topic, or the mission.
- Do NOT use phrases like "Let's discuss", "Tell me", "Let's begin".
- Do NOT correct grammar. Do NOT praise.
- Speak as a real person who already has a position, not as a host.

Their level is {level}: {_lv(level)}
No emojis, no stage directions, no quotes around your reply.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=120) or \
        PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_battle_turn(personality: str, history: str, last_user: str, level: str, language: str,
                         mission: str, user_name: str, conviction: int) -> dict:
    """
    Реплика персонажа + новое значение «убеждённости» (100 = не убеждён, 0 = полностью убеждён).
    Модель решает, насколько сдвинуть, но с жёстким клампом:
      - не больше -30 за ход;
      - не больше +10 за ход.
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    prompt = f"""
You are role-playing a character in a debate game with a language learner{f' named {user_name}' if user_name else ''}.
CHARACTER: {_persona(personality)}
The learner's MISSION: {mission}
The learner's level: {level}: {_lv(level)}

Conversation so far:
{history}

The learner's latest message: "{last_user}"
Your current conviction that the learner is right: {conviction} (100 = not convinced at all, 0 = fully convinced).

Do two things:
1. Reply in character, in {_lang(language)}, 1-3 short sentences. Push back, probe, or ask ONE follow-up question.
   Do not hand the learner the answer. Do not correct their grammar (that happens later).
2. Decide the NEW conviction. Lower it by 8-30 ONLY if the latest message contains a genuinely strong, specific
   and relevant argument for the mission; lower it by 0-6 for weak or generic answers; RAISE it by up to 10 if the
   learner dodged, contradicted themselves or went off-topic. Stay stubborn.

Return JSON: {{"reply": "<your reply>", "conviction": <integer 0-100>}}
"""
    data = _ask_json(prompt, language, temperature=0.85, max_tokens=250, check_ru=True) or {}
    reply = _no_ru(data.get("reply"))
    new_conv = _score(data.get("conviction"), default=max(0, conviction - 5))
    new_conv = max(conviction - 30, min(conviction + 10, new_conv))
    return {"reply": reply, "conviction": max(0, min(100, new_conv)), "speaker": person["short_name"]}


def analyze_debate(user_responses: list[str], dialogue_text: str, topic: str, level: str, language: str,
                   personality: str, weapons: str, mission: str = "") -> dict:
    prompt = f"""
Evaluate a language learner's performance in a debate battle against a character.
Target language: {_lang(language)}. Learner level: {level}: {_lv(level)}
Topic: "{topic}". Character: {_persona(personality)}
The learner's mission: {mission or 'convince the character'}
Score every criterion 0-100 RELATIVE to what is expected at level {level}: flawless for {level} = 85-95,
typical solid performance = 60-75, many errors or thin answers = below 50. Be fair but honest.

Criteria:
- language: grammar, vocabulary, fluency, naturalness
- communication: clarity, argumentation, adaptability, persuasion, evidence, control
- conviction: how convinced the character is at the END, 0-100

Conversation:
{dialogue_text}

Return JSON: {{"language": {{...4 keys...}}, "communication": {{...6 keys...}}, "conviction": int}}
"""
    data = _ask_json(prompt, language, temperature=0.2, max_tokens=400) or {}
    criteria = {**_scores(data.get("language"), LANGUAGE_CRITERIA),
                **_scores(data.get("communication"), COMMUNICATION_SKILLS)}
    return {
        "criteria": criteria,
        "conviction": _score(data.get("conviction"), default=70),
    }


# ==================================================================
# BATTLE DEBRIEF
# ==================================================================

def _in_text(phrase: str, text: str) -> bool:
    p = phrase.lower().strip(" .,!?;:\"'«»…")
    return bool(p) and p in text.lower()


def generate_battle_debrief(user_name: str, language: str, level: str, personality: str,
                            topic: str, mission: str, won: bool, win_score: int,
                            conviction: int, criteria: dict, dialogue: list,
                            pattern: str = "", previous_criteria: dict | None = None,
                            unlocked_tools: set | None = None) -> dict:
    """
    Финальный дебриф после боя.

    Три отдельных слоя (см. Battle Debrief Engine):
      1. BATTLE DEBRIEF — что произошло именно в этом бою (result_line/worked/cost/tool_used/advice/mistakes).
      2. MY ARENA        — growth: как это соотносится с предыдущим профилем (было → стало),
                            а не изолированная разовая оценка.
      3. MY ARSENAL      — next_target + tool_used: какой из 8 ФИКСИРОВАННЫХ приёмов
                            (см. game_data.ARSENAL_TOOLS) реально продемонстрирован в этом бою.

    Ключи:
      result_state  — VICTORY | ALMOST | DEFEATED | OUTPLAYED
      result_line   — 1 предложение о том, что реально произошло
      worked        — 1 конкретное, что сработало
      cost          — 1 конкретное, что помешало
      tool_used     — str | None: ключ из game_data.ARSENAL_TOOL_KEYS, если игрок реально
                       продемонстрировал один из 8 приёмов; иначе None
      advice        — 1-2 предложения от самого персонажа (в характере)
      next_target   — один communication-скилл для следующего боя
      mistakes      — список ошибок языка
      growth        — 1 предложение: сравнение с прошлым профилем (пусто, если сравнивать не с чем)
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    user_lines = [d["text"] for d in dialogue if d["speaker"] == "User"]
    char_lines = [d["text"] for d in dialogue if d["speaker"] != "User"]
    user_blob, char_blob = "\n".join(user_lines), "\n".join(char_lines)

    result_state = "VICTORY" if won else ("ALMOST" if win_score >= 50 else "DEFEATED")
    if won and win_score >= 85:
        result_state = "OUTPLAYED"

    # --- "было → стало": прошлый профиль критериев, чтобы не оценивать бой изолированно ---
    prev_block = "Not enough previous data — treat this as a first real data point, don't claim a pattern yet."
    if previous_criteria:
        deltas = []
        for k, v in criteria.items():
            prev_v = previous_criteria.get(k)
            if prev_v is not None and abs(v - prev_v) >= 8:
                direction = "up" if v > prev_v else "down"
                deltas.append(f"{k}: {prev_v} → {v} ({direction})")
        prev_block = (
            f"Learner's profile BEFORE this battle: {json.dumps(previous_criteria)}. "
            f"Notable shifts this battle: {'; '.join(deltas) if deltas else 'no single skill moved much'}. "
            "If a previously weak skill clearly improved, say so explicitly as growth — don't just repeat "
            "that it's still their weak point."
        )

    # --- каталог из 8 фиксированных приёмов для классификации ---
    unlocked_tools = unlocked_tools or set()
    tools_listing = "\n".join(f'- "{k}": {d}' for k, d in ARSENAL_TOOL_DEFS.items())
    owned_note = (
        f"They already have: {', '.join(sorted(unlocked_tools))}. You can still pick one of these again "
        "if they genuinely demonstrated it — repetition just won't unlock anything new, that's handled "
        "elsewhere, so answer honestly regardless."
        if unlocked_tools else "They haven't unlocked any of these yet."
    )

    prompt = f"""
You are ARENA writing the debrief after a debate battle. ARENA's voice: terse, sharp, a little biting
but fair, short sentences, never gushing. Learner: {user_name}. Level {level}: {_lv(level)} — write so
THEY can read it easily, in language appropriate for THIS level (simpler words/shorter sentences for
A1-A2, more nuance allowed for C1-C2).
Character: {_persona(personality)}. Stay strictly true to this character's personality in "advice" —
never write generic teacher-voice, always their voice.
Topic: "{topic}". Mission: {mission or 'convince the character'}.
Result: win_score = {win_score}/100, character's remaining doubt = {conviction}/100. Scores: {json.dumps(criteria)}
Learner's observed pattern (from the Temple): {pattern or 'not specified'}

MY ARENA (long-term profile, compare before → now, don't re-score from scratch):
{prev_block}

The learner's messages:
{user_blob}

The character's lines:
{char_blob}

Don't treat this as flat win/lose. A learner can win the argument but still lose on a specific
communication skill, or lose the argument but clearly grow on something. Look at the SCORES above —
if one or two criteria are notably weaker than the rest even in a win (or notably strong even in a
loss), say so explicitly instead of just reporting win/lose.

Return JSON with these keys:
- "result_line": ONE or TWO sentences on what actually happened — NOT a score recap, and NOT flat
    win/lose. If it fits, name the split explicitly, e.g. "You won the argument. But you lost on X."
    Only claim a split if the scores actually support it — don't invent one.
- "worked": ONE short sentence — the one concrete thing that worked, quoting or referencing what they said.
- "win_move": ONE short sentence — the specific move/tactic that actually secured the result (how they
    got the character to budge, or — if they lost — the one thing that was closest to working). This is
    about the MECHANISM of the outcome, distinct from "worked" (just what was good) and "cost" (what held
    them back).
- "cost": ONE short sentence — the ONE behavior that held them back or prevented a stronger result,
    even if they won overall.
- "growth": ONE short sentence comparing this battle to their previous profile — name a skill that is
    clearly improving OR clearly still stuck. If there isn't enough previous data, return an empty string.
    Never invent a trend that the numbers don't support.
- "tool_used": which ONE of these 8 fixed techniques the learner ACTUALLY demonstrated in this battle,
    or null if genuinely none of them applies. Pick the exact key string, nothing else:
{tools_listing}
    Rules: it must be grounded in something they ACTUALLY did — quote or reference it in your own
    reasoning, don't guess. {owned_note} Most real battles contain at least one of these — look
    carefully before returning null; only return null for a genuinely too-short/degenerate exchange.
- "advice": 1-2 sentences spoken IN CHARACTER, not like a teacher.
    If the learner lost: what to change. If the learner won: a grudging, in-character reaction.
- "next_target": one of {COMMUNICATION_SKILLS} — the communication criterion to train next.
- "arena_note": 1-2 sentences in ARENA's OWN voice (not the character's) — a forward-looking meta
    observation, as if ARENA is quietly tracking them across battles. Reference "next_target" naturally
    (e.g. "I noticed something else — tomorrow, let's test how you hold up under pressure"). This is
    NOT a repeat of "growth" above — it should feel like ARENA teasing what's coming, not scoring what
    already happened.
- "mistakes": up to 3 objects {{"wrong": <copied VERBATIM from learner>, "correct": <fixed>}}.

All non-quoted text in {_lang(language)}. Keep everything SHORT.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=950, check_ru=True) or {}

    mistakes = []
    for m in (data.get("mistakes") or [])[:3]:
        if isinstance(m, dict):
            wrong, correct = str(m.get("wrong", "")).strip(), str(m.get("correct", "")).strip()
            if wrong and correct and wrong.lower() != correct.lower() and _in_text(wrong, user_blob):
                mistakes.append({"wrong": wrong, "correct": correct})

    tool_used = str(data.get("tool_used") or "").strip().lower()
    if tool_used not in ARSENAL_TOOL_KEYS:
        tool_used = None

    next_target = str(data.get("next_target", "")).strip().lower()
    if next_target not in COMMUNICATION_SKILLS:
        next_target = ""

    return {
        "result_state": result_state,
        "result_line": _no_ru(data.get("result_line")),
        "worked": _no_ru(data.get("worked")),
        "win_move": _no_ru(data.get("win_move")),
        "cost": _no_ru(data.get("cost")),
        "growth": _no_ru(data.get("growth")),
        "tool_used": tool_used,
        "advice": _no_ru(data.get("advice")),
        "next_target": next_target,
        "arena_note": _no_ru(data.get("arena_note")),
        "mistakes": mistakes,
        "character": person["short_name"],
    }


def _memory_block(memory: dict | None) -> str:
    """
    Форматирует то, что ARENA помнит об ученике, для промптов Free Talk.
    favorite_topics — темы, к которым он возвращался НЕСКОЛЬКО раз (частотный учёт),
    отличаются от recent_topics (просто последние темы, включая разовые).
    """
    memory = memory or {}
    favorites = [t for t in (memory.get("favorite_topics") or []) if t]
    interests = [t for t in (memory.get("interests") or []) if t]
    recent = [t for t in (memory.get("recent_topics") or []) if t]
    said = [s for s in (memory.get("last_said") or []) if s]

    lines = []
    if favorites:
        lines.append(f"Topics they keep coming back to — their real favorites: {', '.join(favorites[:5])}.")
    other_recent = [t for t in (recent or interests) if t.lower() not in {f.lower() for f in favorites}]
    if other_recent:
        lines.append(f"Other things they've mentioned before: {', '.join(other_recent[:4])}.")
    if said:
        quoted = " / ".join(f'"{s}"' for s in said[:3])
        lines.append(f"The last few things they said to you: {quoted}")

    if not lines:
        return "You don't know this learner yet — this is effectively your first real conversation with them."
    return (
        "What ARENA remembers about this learner (use it naturally, don't recite it as a list):\n"
        + "\n".join(f"- {l}" for l in lines)
        + "\nPrefer bringing up a favorite topic if it fits naturally."
    )


def generate_freetalk_opening(personality: str, memory: dict | None, language: str,
                              level: str, user_name: str = "") -> str:
    prompt = f"""
You are {_persona(personality)}
You start a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
"Relaxed" means no grading and no conflict is required — it does NOT mean you become a generic warm
chatbot. Your personality and speech habits above must be just as strong here as in a heated debate.
{_memory_block(memory)}
Open in character in 1-2 SHORT sentences: bring up something from what you remember about them (or a topic
you would naturally raise) and ask ONE engaging question, filtered through YOUR specific personality
(e.g. the CEO makes it about outcomes, the journalist makes it a probing question, the philosopher makes
it about meaning). Their level is {level}: {_lv(level)}
No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=110) or \
        PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_ai_response(personality: str, history: str, last_user: str, level: str, language: str,
                         mission=None, user_name: str = "", memory: dict | None = None) -> str | None:
    prompt = f"""
You are {_persona(personality)}
This is a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
"Relaxed" means no grading and no conflict is required — it does NOT mean you become a generic warm
chatbot. Even on plain small talk (food, weekend, weather, hobbies) your specific mannerisms and
attitude must show through, exactly as described above.
Their level is {level}: {_lv(level)}
{_memory_block(memory)}

Conversation so far:
{history}

The learner just said: "{last_user}"

Reply in character in 1-3 short sentences. React to what they actually said, keep your personality and
speech habits, ask at most ONE follow-up question. Do not just agree and validate — react the way THIS
character specifically would. Do not correct their grammar. No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=150)


# ==================================================================
# ПУШИ
# ==================================================================

def generate_daily_push(personality: str, topics: list, first_name: str, language: str,
                        topic: str | None = None, level: str = "B1") -> str:
    """
    Ежедневный пуш от персонажа. Помнит прошлый разговор, бросает вызов,
    даёт микро-миссию на сегодня.
    """
    person = PERSONALITIES.get(personality, {})
    topic = topic or (random.choice(topics) if topics else "the thing you keep avoiding")
    prompt = f"""
You are {_persona(personality)}
Write ONE short provocative message (2-3 short lines) to {first_name or 'the learner'} to pull them back into the arena.
The topic that really hooked them: "{topic}". Their level is {level}: {_lv(level)}
Rules:
- Refer to something they said last time, or to a specific angle of "{topic}".
- Throw down a challenge — one uncomfortable question OR one tiny mission for today.
- No greeting, no signature, never sound like customer support.
- Address them directly ("you"). No emojis.
"""
    text = _ask(prompt, language, temperature=0.95, max_tokens=140)
    return text or f"{person.get('phrase', 'Your move.')} — {topic}"