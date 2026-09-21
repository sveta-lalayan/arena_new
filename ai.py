"""
ai.py — GPT-слой ARENA.

Правила, которые тут гарантируются:
 1. Всё, что «говорят» Арена и персонажи (реакции, миссии, реплики, обратная связь, пуши),
    пишется СТРОГО на языке пользователя. Если модель проскользнула в кириллицу —
    делаем повторную попытку, а если и она не помогла — возвращаем None (сработает fallback).
 2. Сложность речи подгоняется под CEFR-уровень пользователя.
 3. Если OpenAI недоступен (нет ключа, сеть) — функции возвращают безопасные значения,
    бот не падает.
"""
import json
import logging
import random
import re

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, FIRST_ENCOUNTER_MOVES
from game_data import (
    LANG_PROMPT_NAME, LEVELS, LEVEL_PROMPTS, PERSONALITIES, PERSONA_BRIEFS,
    MISSION_FORMAT_BY_PERSONALITY, SKILL_TO_PERSONALITY, COMMUNICATION_SKILLS,
    LANGUAGE_CRITERIA, ALL_CRITERIA, BEHAVIOUR_BRIEFS, BEGINNER_LEVELS, ARENA_RANKS,
    SKILL_LABELS_RU,
)

logger = logging.getLogger(__name__)

_client = None
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
BEHAVIOURS = list(BEHAVIOUR_BRIEFS)


# ======================= низкоуровневые помощники =======================

def _get_client():
    global _client
    if _client is None and OPENAI_API_KEY:
        _client = OpenAI(api_key=OPENAI_API_KEY, timeout=45)
    return _client


def _lang(language: str) -> str:
    return LANG_PROMPT_NAME.get(language, "English")


def _lv(level: str) -> str:
    return LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["B1"])


def _system(language: str, extra: str = "") -> str:
    lang = _lang(language)
    return (
        f"You are part of ARENA, a language-training game where learners debate characters. "
        f"Write ONLY in {lang}. Never write Russian or any language other than {lang}, even if the "
        f"learner's message or these instructions contain other languages. {extra}".strip()
    )


def _chat(system: str, prompt: str, temperature: float = 0.7, max_tokens: int = 400,
          json_mode: bool = False) -> str | None:
    client = _get_client()
    if client is None:
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
    except Exception:
        logger.exception("OpenAI chat error")
        return None


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip().strip('"“”«»').strip()
    return text or None


def _ask(prompt: str, language: str, temperature: float = 0.7, max_tokens: int = 300) -> str | None:
    """Проза на языке пользователя. Никакой кириллицы: одна повторная попытка, иначе None."""
    system = _system(language)
    text = _chat(system, prompt, temperature, max_tokens)
    if text and _CYRILLIC.search(text):
        text = _chat(
            system + f" Your previous answer contained Russian. Answer again STRICTLY in {_lang(language)} only.",
            prompt, temperature, max_tokens,
        )
        if text and _CYRILLIC.search(text):
            return None
    return _clean(text)


def ask_gpt_in_language(prompt: str, language: str, temperature: float = 0.7, max_tokens: int = 300) -> str | None:
    """Совместимость со старым названием."""
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
    if check_ru and raw and _CYRILLIC.search(raw):
        raw = _chat(system + f" Your previous answer contained Russian. Use ONLY {_lang(language)}.",
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
    return PERSONA_BRIEFS.get(personality, PERSONA_BRIEFS["devil_advocate"])


def format_history(dialogue: list, char_name: str, last: int = 14) -> str:
    """Диалог в текст для GPT. Подписи — по-английски, чтобы не подталкивать модель к русскому."""
    return "\n".join(
        f"{'Learner' if d['speaker'] == 'User' else char_name}: {d['text']}" for d in dialogue[-last:]
    )


# ======================= ХРАМ =======================

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


def _default_analysis() -> dict:
    return _normalize_analysis({})


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
    }


def analyze_first_encounter(user_responses: list[str], language: str) -> dict:
    """Разбор по 10 критериям (4 языковых + 6 коммуникационных) + уровень, стиль, интересы."""
    lang = _lang(language)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(user_responses))
    prompt = f"""
You are ARENA's analyst. A learner of {lang} wrote these messages (their target language is {lang}):
{numbered}

Assess them. Score every criterion 0-100 RELATIVE to the learner's own CEFR level: a learner who performs
cleanly for their level scores 70-90; many errors or very thin answers score below 50.
Return a JSON object with EXACTLY these keys:
- "estimated_level": one of {LEVELS} (CEFR level of their {lang})
- "language": {{"grammar": int, "vocabulary": int, "fluency": int, "naturalness": int}}
- "communication": {{"clarity": int, "argumentation": int, "adaptability": int, "persuasion": int, "evidence": int, "control": int}}
- "hidden": {{"resilience": int}}
- "behaviour": one of {BEHAVIOURS}. Meaning: {json.dumps(BEHAVIOUR_BRIEFS)}
- "grammar_weak_areas": up to 3 short strings in English
- "vocabulary_weak_areas": up to 3 short strings in English
- "interests": 3-5 short topic phrases (1-4 words each) in {lang}, taken from what they actually talked about
- "main_topic": the ONE topic they care about most, 2-5 words, in {lang}
- "recommended_personality": one of {list(PERSONALITIES)}. Pick the character who best fits BOTH their main
  topic AND their weakest communication skill. Characters train: ceo=persuasion (numbers, benefits),
  journalist=clarity, professor=evidence, hr_manager=adaptability (real examples), philosopher=control (depth),
  devil_advocate=argumentation under pressure.
"""
    data = _ask_json(prompt, language, temperature=0.3, max_tokens=700)
    if not data:
        logger.warning("analyze_first_encounter: пустой ответ, использую значения по умолчанию")
    return _normalize_analysis(data)


def analyze_freetalk(user_responses: list[str], language: str) -> dict:
    """Разбор свободного разговора — те же 10 критериев, что и в Храме."""
    return analyze_first_encounter(user_responses, language)


def generate_arena_observation(user_name: str, user_responses: list[str], language: str, level: str,
                               topic: str, personality: str, weakest_skill: str) -> str:
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    said = "\n".join(f"- {t}" for t in user_responses[-8:])
    prompt = f"""
You are ARENA, the supreme voice of a language arena: terse, sharp, a little cold, but you respect effort.
You just listened to {user_name or 'a newcomer'} for several minutes. Their level is {level}: {_lv(level)}
Write it so THEY can read it comfortably.

What they said:
{said}

Write exactly 3 short lines separated by blank lines:
1. ONE punchy, slightly biting "wow" sentence about them (max 12 words), referring to something real they said.
2. One sentence: you noticed they care about "{topic}" — and {person['full_name']} knows that world inside out.
3. One sentence about what they must sharpen ({SKILL_LABELS_RU.get(weakest_skill, weakest_skill)}), no lecturing.
Address them by name ({user_name}) once. No emojis, no lists, no headings.
"""
    return _ask(prompt, language, temperature=0.85, max_tokens=220) or ""


def generate_character_pitch(personality: str, topic: str, language: str, level: str,
                             first_name: str = "", weakest_skill: str = "") -> str:
    """Персонаж представляется и бросает вызов по теме (Храм и ежедневный бой)."""
    focus = f"You will train their weak spot: {weakest_skill}." if weakest_skill else ""
    prompt = f"""
You are {_persona(personality)}
Introduce yourself to a language learner{f' named {first_name}' if first_name else ''} in 2 SHORT sentences,
fully in character: say what you are about to do to them in a battle about "{topic}" and throw down a challenge.
{focus} Their level is {level}: {_lv(level)}
No emojis, no stage directions, no quotation marks.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=140) or ""


# ======================= БОЙ =======================

def generate_mission_task(topic: str, personality: str, user_name: str, language: str, level: str) -> str:
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])
    fmt = MISSION_FORMAT_BY_PERSONALITY.get(personality, "a claim the learner must defend")
    prompt = f"""
Create ONE mission for a language-learning debate game.
Character the learner faces: {_persona(personality)}
Topic: "{topic}". Mission format: {fmt}.
The mission says what the learner must convince/defend/prove to {person['short_name']}. ONE sentence, max 22 words,
addressed to the learner in second person, specific and a bit provocative.
Example of the style (do NOT copy): "Convince Kate that spending $500 on perfume is a great idea."
The learner's level is {level}: {_lv(level)}
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=90) or f"{topic}"


def generate_mission_weapons(topic: str, level: str, personality: str, language: str,
                             weak_areas: dict | None = None, weakest_skill: str | None = None):
    """Возвращает (weapons, tip, win_condition). Всё — на языке пользователя."""
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
- "win_condition": 1-2 short lines: what exactly will convince THIS character (be specific to the topic).
All text in {_lang(language)}.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=350, check_ru=True) or {}
    raw = data.get("weapons") or []
    weapons_list = [w.strip() for w in raw if isinstance(w, str) and w.strip() and not _CYRILLIC.search(w)][:n]
    return " · ".join(weapons_list), _no_ru(data.get("tip")), _no_ru(data.get("win_condition"))


def generate_opening_statement(personality: str, topic: str, level: str, language: str, mission: str = "") -> str:
    prompt = f"""
You are {_persona(personality)}
A language learner just entered a debate battle with you.
Topic: "{topic}". The learner's mission: {mission or 'to convince you'}.
Open the battle in character in 1-2 SHORT sentences: take a skeptical stance on the mission and end with ONE
direct question that forces the learner to speak. Level: {level}: {_lv(level)}
No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=110) or PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_battle_turn(personality: str, history: str, last_user: str, level: str, language: str,
                         mission: str, user_name: str, conviction: int) -> dict:
    """
    Реплика персонажа + новое значение «убеждённости» (100 = не убеждён, 0 = полностью убеждён).
    Модель решает, насколько сдвинуть — но не больше -30/+10 за ход (см. clamp).
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
   learner dodged, contradicted themselves or went off-topic. Stay stubborn — a truly convincing performance is
   needed to get below 20. If they are clearly winning, let your reply show grudging respect.

Return JSON: {{"reply": "<your reply>", "conviction": <integer 0-100>}}
"""
    data = _ask_json(prompt, language, temperature=0.85, max_tokens=250, check_ru=True) or {}
    reply = _no_ru(data.get("reply"))
    new_conv = _score(data.get("conviction"), default=max(0, conviction - 5))
    new_conv = max(conviction - 30, min(conviction + 10, new_conv))
    return {"reply": reply, "conviction": max(0, min(100, new_conv)), "speaker": person["short_name"]}


def analyze_debate(user_responses: list[str], dialogue_text: str, topic: str, level: str, language: str,
                   personality: str, weapons: str, quest_desc: str = "") -> dict:
    """Оценка боя по 10 критериям + итоговая убеждённость + выполнен ли квест (для типа 'behaviour')."""
    prompt = f"""
Evaluate a language learner's performance in a debate battle against a character.
Target language: {_lang(language)}. Learner level: {level}: {_lv(level)}
Topic: "{topic}". Character: {_persona(personality)}
Score every criterion 0-100 RELATIVE to what is expected at level {level}: flawless for {level} = 85-95,
typical solid performance = 60-75, many errors or thin answers = below 50. Be fair but honest; a truly
excellent performance must be able to score 90+.

Criteria:
- language: grammar (accuracy), vocabulary (range/precision), fluency (flow, length, connected ideas),
  naturalness (idiomatic, native-like phrasing)
- communication: clarity, argumentation (logic and structure), adaptability (reacting to the character's pushback),
  persuasion (did they actually move the character), evidence (examples, facts, reasons),
  control (led the conversation and stayed on the mission)
- conviction: how convinced the character is at the END, 0-100 (100 = not convinced at all, 0 = fully convinced)
- quest_done: true/false — did the learner fulfil this quest: {quest_desc or 'none'}

Conversation:
{dialogue_text}

Return JSON: {{"language": {{...4 keys...}}, "communication": {{...6 keys...}}, "conviction": int, "quest_done": bool}}
"""
    data = _ask_json(prompt, language, temperature=0.2, max_tokens=400) or {}
    criteria = {**_scores(data.get("language"), LANGUAGE_CRITERIA),
                **_scores(data.get("communication"), COMMUNICATION_SKILLS)}
    return {
        "criteria": criteria,
        "conviction": _score(data.get("conviction"), default=70),
        "quest_done": bool(data.get("quest_done", False)),
    }


def _in_text(phrase: str, text: str) -> bool:
    p = phrase.lower().strip(" .,!?;:\"'«»…")
    return bool(p) and p in text.lower()


def generate_arena_feedback(user_name: str, language: str, level: str, personality: str, topic: str,
                            mission: str, won: bool, conviction: int, criteria: dict,
                            dialogue: list) -> dict:
    """
    Обратная связь от Арены на языке пользователя: колкая вау-фраза, что сработало, почему победа/поражение,
    языковые ошибки, удачные фразы, фразы для «кражи» у персонажа и реплика самого персонажа.
    Все цитаты проверяются по реальному тексту диалога (никаких выдуманных «ошибок»).
    """
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    user_lines = [d["text"] for d in dialogue if d["speaker"] == "User"]
    char_lines = [d["text"] for d in dialogue if d["speaker"] != "User"]
    user_blob, char_blob = "\n".join(user_lines), "\n".join(char_lines)
    outcome = "the learner WON" if won else "the learner LOST"

    prompt = f"""
You are ARENA writing the verdict after a debate battle. ARENA's voice: terse, sharp, a little biting but fair,
short sentences, never gushing. Learner: {user_name}. Level {level}: {_lv(level)} — write so THEY can read it easily.
Character: {_persona(personality)}
Topic: "{topic}". Mission: {mission or 'convince the character'}.
Result: {outcome}. The character's remaining doubt: {conviction}/100. Scores: {json.dumps(criteria)}

The learner's messages:
{user_blob}

The character's lines:
{char_blob}

Return JSON with these keys:
- "wow": ONE punchy sentence (max 10 words) that addresses {user_name} by name — a sting or a salute.
- "worked": ONE short sentence — what was genuinely strong; refer to something concrete they said.
- "why": 1-2 short sentences — why they {'won' if won else 'lost'}; specific to this debate, not generic.
- "mistakes": up to 3 objects {{"wrong": <phrase copied VERBATIM from the learner's messages>, "correct": <corrected version>}}
  — only real grammar/vocabulary errors. Empty list if there are none.
- "great_phrases": up to 2 strong phrases copied VERBATIM from the learner's messages.
- "steal": up to 3 short useful phrases (2-7 words) copied VERBATIM from the CHARACTER's lines that the learner should reuse.
- "character_line": 1-2 sentences spoken by the character to the learner, in character.
  {'The learner lost: say exactly what to change next time.' if not won else 'The learner won: give a grudging, in-character reaction.'}
All text in {_lang(language)} (copied phrases stay as they are). Keep everything SHORT.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=700, check_ru=True) or {}

    mistakes = []
    for m in (data.get("mistakes") or [])[:3]:
        if isinstance(m, dict):
            wrong, correct = str(m.get("wrong", "")).strip(), str(m.get("correct", "")).strip()
            if wrong and correct and wrong.lower() != correct.lower() and _in_text(wrong, user_blob):
                mistakes.append({"wrong": wrong, "correct": correct})

    def _phrases(key, source, limit):
        out = []
        for p in (data.get(key) or [])[:limit]:
            if isinstance(p, str) and _in_text(p, source):
                out.append(p.strip())
        return out

    return {
        "wow": _no_ru(data.get("wow")),
        "worked": _no_ru(data.get("worked")),
        "why": _no_ru(data.get("why")),
        "mistakes": mistakes,
        "great_phrases": _phrases("great_phrases", user_blob, 2),
        "steal": _phrases("steal", char_blob, 3),
        "character_line": _no_ru(data.get("character_line")),
        "character": person["short_name"],
    }


# ======================= СВОБОДНЫЙ РАЗГОВОР =======================

def _memory_block(memory: dict | None) -> str:
    if not memory:
        return ""
    parts = []
    if memory.get("interests"):
        parts.append(f"topics they care about: {', '.join(memory['interests'][:5])}")
    if memory.get("recent_topics"):
        parts.append(f"recent topics: {', '.join(memory['recent_topics'][:4])}")
    if memory.get("last_said"):
        parts.append("things they said last time: " + " | ".join(memory["last_said"]))
    return ("What you remember about them (use it lightly, never recite it): " + "; ".join(parts)) if parts else ""


def generate_freetalk_opening(personality: str, memory: dict | None, language: str, level: str,
                              user_name: str = "") -> str:
    prompt = f"""
You are {_persona(personality)}
You start a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
{_memory_block(memory)}
Open in character in 1-2 SHORT sentences: bring up something from what you remember about them (or a topic
you would naturally raise) and ask ONE engaging question. Their level is {level}: {_lv(level)}
No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=110) or PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_ai_response(personality: str, history: str, last_user: str, level: str, language: str,
                         mission=None, user_name: str = "", memory: dict | None = None) -> str | None:
    """Реплика персонажа в свободном разговоре."""
    prompt = f"""
You are {_persona(personality)}
This is a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
Their level is {level}: {_lv(level)}
{_memory_block(memory)}

Conversation so far:
{history}

The learner just said: "{last_user}"

Reply in character in 1-3 short sentences. React to what they actually said, keep your personality, ask at most ONE
follow-up question. Do not correct their grammar. No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=150)


# ======================= ПУШИ =======================

def generate_daily_push(personality: str, topics: list, first_name: str, language: str,
                        topic: str | None = None, level: str = "B1") -> str:
    """Ежедневный пуш от персонажа: коротко, колко, с зацепкой по интересам человека."""
    person = PERSONALITIES.get(personality, {})
    topic = topic or (random.choice(topics) if topics else "the thing you keep avoiding")
    prompt = f"""
You are {_persona(personality)}
Write ONE short provocative message (2-3 short lines) to {first_name or 'the learner'} to pull them back into the arena.
The topic that really hooked them: "{topic}". Their level is {level}: {_lv(level)}
Rules: throw down a challenge — one uncomfortable question OR one tiny mission for today; no greeting, no
signature, never sound like customer support, address them directly ("you"), no emojis.
"""
    text = _ask(prompt, language, temperature=0.95, max_tokens=120)
    return text or f"{person.get('phrase', 'Your move.')} — {topic}"