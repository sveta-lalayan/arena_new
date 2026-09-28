"""
ai.py — GPT-слой ARENA.

Правила:
 1. Всё, что «говорят» Арена и персонажи, пишется СТРОГО на learning_language.
 2. Сложность речи подгоняется под CEFR-уровень.
 3. UI — только через locales/*.json.
 4. Если OpenAI недоступен — функции возвращают безопасные значения, бот не падает.

Battle debrief жёстко следует правилам ARENA:
  • narrative-результат без «performance review»-тона
  • BEST MOVE — чистая похвала, без «но»
  • никаких JSON-ключей в названиях скиллов (question_formation → QUESTIONING)
  • нельзя выводить soft-skill слабость из одной опечатки
  • LANGUAGE UPGRADE — это оружие, не совет по английскому
  • ARENA NOTICED — межбоевое наблюдение про человека, не про абстрактную clarity
  • NEXT BATTLE — создаёт ожидание, не звучит как домашка
"""
import json
import logging
import random
import re

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, FIRST_ENCOUNTER_MOVES
from game_data import (
    LANG_PROMPT_NAME, LEVELS, LEVEL_PROMPTS, PERSONALITIES, PERSONA_BRIEFS, SPEECH_STYLE,
    MISSION_FORMAT_BY_PERSONALITY, SKILL_TO_PERSONALITY, COMMUNICATION_SKILLS,
    LANGUAGE_CRITERIA, ALL_CRITERIA, BEHAVIOUR_BRIEFS, BEGINNER_LEVELS, ARENA_RANKS,
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
        from config import OPENAI_BASE_URL
        _client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=45,
        )
    return _client


def _lang(language: str) -> str:
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
        "Stay strictly in this character's voice and personality at all times."
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
    """
    Реплика Храма. ARENA — верховная наблюдающая сила:
      • НЕ персонаж (нет характера, не спорит, не шутит)
      • НЕ робот (не «понятно», «интересно», без support-agent-фраз)
      • слушает и поддерживает: подхватывает конкретную деталь, копает глубже
      • коротко и по делу, чуть холодно, но с уважением
    """
    prompt = f"""
You are ARENA — a quiet, observant, higher presence that is listening to a newcomer
before deciding who they should meet.

You are NOT a character. You have no personality of your own to perform.
You are NOT a robot. You do NOT say "understood", "interesting", "noted", "I see",
"I'm here to help", or any support-agent phrasing.

You are listening carefully. Your job right now is ONLY to keep them talking:
pick ONE concrete detail they just said, and ask ONE short follow-up that digs
deeper into what they actually care about.

Rules:
- 1-2 SHORT sentences. Max 25 words total.
- Mirror their language level: never write anything more complex than what they wrote.
- No praise, no emojis, no lists, no "What do you think?".
- Do NOT introduce yourself. Do NOT talk about the battle. Do NOT explain anything.
- Never sound cheerful or chatty. Sound like someone who already sees more than they say.

This is their message number {turn} of {FIRST_ENCOUNTER_MOVES}.

Conversation so far:
{history}

They just said: "{user_text}"

Your reply:
"""
    return _ask(prompt, language, temperature=0.85, max_tokens=90)

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
    lang = _lang(language)
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(user_responses))

    prompt = f"""
You are ARENA's analyst. A learner of {lang} wrote these messages (their target language is {lang}):
{numbered}

Assess them. Score every criterion 0-100 RELATIVE to the learner's own CEFR level.

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

Return JSON with EXACTLY these keys:
- "estimated_level": one of {LEVELS}
- "language": {{"grammar": int, "vocabulary": int, "fluency": int, "naturalness": int}}
- "communication": {{"clarity": int, "argumentation": int, "adaptability": int, "persuasion": int, "evidence": int, "control": int}}
- "hidden": {{"resilience": int}}
- "behaviour": one of {BEHAVIOURS}
- "grammar_weak_areas": up to 3 short English strings
- "vocabulary_weak_areas": up to 3 short English strings
- "interests": 3-5 short topic phrases in {lang}, taken from what they ACTUALLY talked about
- "main_topic": the ONE topic they care about most, 2-5 words, in {lang}
- "recommended_personality": one of {list(PERSONALITIES)}
- "pattern": the ONE pattern phrase from the list above, lowercase
- "pattern_evidence": list of 2-4 short VERBATIM quotes
"""
    data = _ask_json(prompt, language, temperature=0.3, max_tokens=800)
    if not data:
        logger.warning("analyze_first_encounter: пустой ответ")
    return _normalize_analysis(data)


def analyze_freetalk(user_responses: list[str], language: str) -> dict:
    return analyze_first_encounter(user_responses, language)


def generate_arena_observation(user_name: str, user_responses: list[str], language: str, level: str,
                               topic: str, personality: str, weakest_skill: str,
                               pattern: str = "") -> str:
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
1. ONE punchy, slightly biting "wow" sentence about them (max 12 words).
2. One sentence showing the pattern in their OWN words (paraphrase, no psychology terms).
3. One sentence naming {person['full_name']} naturally.

Address them by name once. No emojis, no lists, no headings.
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
    person = PERSONALITIES.get(personality, PERSONALITIES["hr_manager"])

    prompt = f"""
Write ONE ultra-short mission statement for a game-like battle.
Character the learner faces: {person['short_name']}.
Topic context (do NOT repeat it in the mission): "{topic}".

Rules:
- MAXIMUM 5 words.
- Game-like, outcome-oriented, second person.
- Do NOT mention the topic or the character's name.
- Do NOT use words like "convince", "explain", "argue", "support", "provide", "thesis", "examples".

Good examples (match LENGTH and TONE):
"Change his mind."  /  "Get the budget."  /  "Make her reconsider."

Bad examples (never produce):
"Convince Professor Adams that unpredictable weather is more harmful than helpful."

Answer with ONE line, no quotes.
"""
    raw = _ask(prompt, language, temperature=0.85, max_tokens=40)
    if not raw:
        return "Change his mind."
    words = raw.strip().strip('"“”«»').split()
    return " ".join(words[:5]).rstrip(".!?") + "."


def generate_mission_weapons(topic: str, level: str, personality: str, language: str,
                             weak_areas: dict | None = None, weakest_skill: str | None = None):
    weak_areas = weak_areas or {}
    n = 4 if level in BEGINNER_LEVELS else 5
    kind = ("simple single words" if level in BEGINNER_LEVELS
            else "useful short phrases, connectors and collocations (1-3 words each)")

    prompt = f"""
Prepare the internal "arsenal" for a debate battle (not shown to the learner).
Character: {_persona(personality)}
Topic: "{topic}". Learner level: {level}: {_lv(level)}
Weak spots — grammar: {weak_areas.get('grammar_weak_areas', [])}, vocabulary: {weak_areas.get('vocabulary_weak_areas', [])},
weakest communication skill: {weakest_skill or 'unknown'}.

Return JSON with:
- "weapons": list of exactly {n} items: {kind}.
- "tip": ONE short sentence on how to talk to THIS character.
- "win_condition": 1-2 short lines: what will convince THIS character.
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
    prompt = f"""
You are {_persona(personality)}

A learner just entered a battle with you. Topic: "{topic}". Their mission: {mission}.

Open the battle — 1-2 short sentences:
1. State YOUR concrete position on "{topic}". Be skeptical or contrarian, not neutral.
2. End with ONE direct question that forces them to defend their view.

Rules:
- Do NOT say "What do you think?" and do NOT ask them to introduce themselves.
- Do NOT explain rules, topic, or mission.
- Do NOT correct grammar. Do NOT praise.
- Speak as a real person who already has a position.

Their level is {level}: {_lv(level)}
No emojis, no stage directions, no quotes around your reply.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=120) or \
        PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_battle_turn(personality: str, history: str, last_user: str, level: str, language: str,
                         mission: str, user_name: str, conviction: int) -> dict:
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
1. Reply in character, in {_lang(language)}, 1-3 short sentences. Push back, probe, ask ONE follow-up question.
   Do not hand the learner the answer. Do not correct their grammar.
2. Decide the NEW conviction. Lower it by 8-30 ONLY for a genuinely strong argument;
   0-6 for weak answers; RAISE it by up to 10 if the learner dodged or contradicted themselves.

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
Evaluate a language learner's performance in a debate battle.
Target language: {_lang(language)}. Learner level: {level}: {_lv(level)}
Topic: "{topic}". Character: {_persona(personality)}
The learner's mission: {mission or 'convince the character'}
Score each criterion 0-100 RELATIVE to level {level}.

Conversation:
{dialogue_text}

Return JSON: {{"language": {{grammar,vocabulary,fluency,naturalness}}, "communication": {{clarity,argumentation,adaptability,persuasion,evidence,control}}, "conviction": int}}
"""
    data = _ask_json(prompt, language, temperature=0.2, max_tokens=400) or {}
    criteria = {**_scores(data.get("language"), LANGUAGE_CRITERIA),
                **_scores(data.get("communication"), COMMUNICATION_SKILLS)}
    return {
        "criteria": criteria,
        "conviction": _score(data.get("conviction"), default=70),
    }


# ==================================================================
# BATTLE DEBRIEF — ARENA-стиль, без "performance review"
# ==================================================================

def _in_text(phrase: str, text: str) -> bool:
    p = phrase.lower().strip(" .,!?;:\"'«»…")
    return bool(p) and p in text.lower()


def generate_battle_debrief(user_name: str, language: str, level: str, personality: str,
                            topic: str, mission: str, won: bool, win_score: int,
                            conviction: int, criteria: dict, dialogue: list,
                            pattern: str = "", previous_criteria: dict | None = None,
                            weapon_tiers: dict | None = None) -> dict:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    user_lines = [d["text"] for d in dialogue if d["speaker"] == "User"]
    char_lines = [d["text"] for d in dialogue if d["speaker"] != "User"]
    user_blob, char_blob = "\n".join(user_lines), "\n".join(char_lines)

    prev_block = "Not enough previous data — treat this as a first real data point."
    if previous_criteria:
        deltas = []
        for k, v in criteria.items():
            prev_v = previous_criteria.get(k)
            if prev_v is not None and abs(v - prev_v) >= 8:
                direction = "up" if v > prev_v else "down"
                deltas.append(f"{k}: {prev_v} → {v} ({direction})")
        prev_block = (
            f"Profile BEFORE this battle: {json.dumps(previous_criteria)}. "
            f"Shifts: {'; '.join(deltas) if deltas else 'no single skill moved much'}."
        )

    weapon_tiers = weapon_tiers or {}
    if weapon_tiers:
        owned = "; ".join(f"{skill} (tier {tier})" for skill, tier in weapon_tiers.items())
        weapon_block = (
            f"Already owned: {owned}. If today's weapon fits the SAME skill area, "
            "make it a clearly more advanced tier, not a duplicate."
        )
    else:
        weapon_block = "They own no weapons yet."

    prompt = f"""
You are ARENA writing the BATTLE DEBRIEF after a debate. Voice: terse, sharp, biting but fair,
never corporate, never "performance review". Address the learner directly.

Learner: {user_name}. Level {level}: {_lv(level)}.
Character: {_persona(personality)}
Topic: "{topic}". Mission: {mission or 'convince the character'}.
Result: win_score = {win_score}/100, remaining doubt = {conviction}/100.
Scores: {json.dumps(criteria)}
Pattern (from the Temple): {pattern or 'not specified'}

Long-term profile (compare before → now, do NOT re-score from scratch):
{prev_block}

Weapons already owned:
{weapon_block}

The learner's messages:
{user_blob}

The character's lines:
{char_blob}

CRITICAL RULES — violating any of these ruins the product:

A. NARRATIVE RESULT, NOT A REPORT.
   "result_line" must describe WHAT HAPPENED IN THE ROOM, not an abstract communication problem.
   BAD: "The conversation drifted into vagueness, leaving key points unaddressed."
   GOOD: "You had ideas worth exploring — but the room couldn't follow you."
   BAD: "The lack of clarity hindered meaningful communication."
   GOOD: "Your ideas were stronger than your delivery."

B. BEST MOVE IS PURE PRAISE — NO "BUT".
   "best_move.why" must NOT explain why it also failed.
   BAD: "This approach aimed to uncover meaning, but it often led to confusion."
   GOOD: "Instead of the obvious answer, you questioned what communication actually means."

C. NO RAW JSON KEYS IN SKILL NAMES.
   Never output "question_formation", "sentence_structure", "clarity_of_thought".
   "best_move.skill" must be a short, human label, e.g. "QUESTIONING", "REFRAMING",
   "CAUSE → EFFECT", "CONCESSION → COUNTER". All caps, 1-3 words.

D. NEVER INFER A SOFT-SKILL WEAKNESS FROM A SINGLE TYPO OR GRAMMAR ERROR.
   A misspelling ("nothoign" instead of "nothing") is a LANGUAGE ERROR, not "lack of engagement".
   If a typo made meaning unclear, say so — but say it as a LANGUAGE consequence, not a
   personality conclusion. BAD: "it signaled a lack of engagement".
   GOOD: "The typo made your meaning unclear. Instead of repairing the sentence, the
          conversation moved on."

E. LANGUAGE UPGRADE MUST BE A WEAPON, NOT AN ENGLISH TIP.
   "language_upgrade" should say: what to do in the MOMENT of pressure, and give a concrete
   phrase to reuse. BAD: "Use clearer phrases."
   GOOD: "When you lose the thread, don't guess. Stop and clarify:
          'I don't understand what you're asking. Could you rephrase that?'"

F. NEW WEAPON — the ONE technique to walk away with. Tied to something that ACTUALLY
   happened in THIS battle. Concrete, reusable tomorrow, not vague advice.

G. ARENA NOTICED — the deepest, cross-battle observation. Must feel like "ARENA knows me".
   BAD: "Emphasizing clarity is essential when discussing complex topics."
   GOOD: "You often reach for deeper ideas before making the basic point clear."
   GOOD: "You don't lack ideas. The harder part is making the other person see the idea
          you're already holding."

H. NEXT BATTLE — create anticipation, not homework.
   BAD: "Focus on expressing your thoughts clearly and directly."
   GOOD: "Tomorrow, I'll give you less room to hide behind vague answers."

I. Do NOT repeat the same point in multiple sections.
J. Do NOT use phrases like "be more confident", "give more examples", "work on your grammar".
K. Every observation must reference something that actually happened.
L. Total length must fit one Telegram message.

Return STRICT JSON with these keys:

- "result_state": one of ["YOU HAD THE ADVANTAGE","CLOSE ONE","YOU LOST THE ROOM",
                          "YOU TURNED IT AROUND","CLEAN WIN","YOU SURPRISED ME"]
- "result_line": 1-2 sentences about what happened in the room. Concrete, not abstract.
- "best_move": {{"what": "<what they actually did>",
                 "why":  "<why it worked — pure praise, no 'but'>",
                 "skill": "<SHORT HUMAN LABEL, e.g. QUESTIONING, REFRAMING>"}}
- "lost_ground": {{"what": "<the specific moment or pattern>",
                   "why":  "<why it weakened the position — link to language if the cause was language>"}}
- "new_weapon": null OR {{
      "kind": "phrase|move|strategy",
      "label": "<short label with emoji, e.g. '⚔️ CLARIFY THE QUESTION'>",
      "description": "<what the user did or faced, 1 sentence>",
      "language_upgrade": "<concrete phrase in {_lang(language)}, in quotes>",
      "why_it_matters": "<1 sentence: how this puts them back in control>",
      "soft_skill": "<emoji + short soft skill name>"
  }}
- "language_upgrade": null OR {{
      "area": "<free-text short area, e.g. 'clarifying under pressure'>",
      "what": "<the concrete phrase or structure, in {_lang(language)}>",
      "why":  "<why this improves the communication, in {_lang(language)}>"
  }} — only when language genuinely affected the outcome.
- "opponent_advice": "<1-2 sentences IN CHARACTER, referring to the battle, never teacher-tone>"
- "arena_noticed": "<ONE sentence — cross-battle insight, do NOT repeat other sections>"
- "next_battle": {{"target": "<clarity|argumentation|evidence|persuasion|adaptability|control>",
                   "hint": "<short, anticipation-building sentence>"}}
- "mistakes": [{{"wrong": "<verbatim from learner>", "correct": "<fixed>"}}]
    Up to 3, only real errors that affect meaning.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=1200, check_ru=True) or {}

    def _obj(d):
        return d if isinstance(d, dict) else None

    mistakes = []
    for m in (data.get("mistakes") or [])[:3]:
        if isinstance(m, dict):
            wrong = str(m.get("wrong", "")).strip()
            correct = str(m.get("correct", "")).strip()
            if wrong and correct and wrong.lower() != correct.lower() and _in_text(wrong, user_blob):
                mistakes.append({"wrong": wrong, "correct": correct})

    result_state = str(data.get("result_state") or "").strip().upper()
    allowed = ("YOU HAD THE ADVANTAGE", "CLOSE ONE", "YOU LOST THE ROOM",
               "YOU TURNED IT AROUND", "CLEAN WIN", "YOU SURPRISED ME")
    if result_state not in allowed:
        result_state = "CLEAN WIN" if won and win_score >= 80 else \
                       "YOU HAD THE ADVANTAGE" if won else "YOU LOST THE ROOM"

    return {
        "result_state": result_state,
        "result_line": _no_ru(data.get("result_line")),
        "best_move": _obj(data.get("best_move")) or {},
        "lost_ground": _obj(data.get("lost_ground")) or {},
        "new_weapon": _obj(data.get("new_weapon")),
        "language_upgrade": _obj(data.get("language_upgrade")),
        "opponent_advice": _no_ru(data.get("opponent_advice")),
        "arena_noticed": _no_ru(data.get("arena_noticed")),
        "next_battle": _obj(data.get("next_battle")) or {},
        "mistakes": mistakes,
        "character": person["short_name"],
    }


# ==================================================================
# DAILY LANGUAGE PROFILE UPDATE
# ==================================================================

def update_language_profile_from_sessions(user_id: int, language: str,
                                          battles: list[dict],
                                          freetalks: list[dict]) -> dict:
    blob_battles = "\n\n".join(
        f"--- BATTLE vs {b.get('personality', '?')} ({b.get('result_state', '')})\n"
        f"USER: " + "\nUSER: ".join(b.get("user_lines", []))
        for b in (battles or [])
    )
    blob_ft = "\n\n".join(
        f"--- FREE TALK with {f.get('personality', '?')}\n"
        f"USER: " + "\nUSER: ".join(f.get("user_lines", []))
        for f in (freetalks or [])
    )
    material = (blob_battles + "\n\n" + blob_ft)[:4000] or "No interactions in the last 24 hours."

    prompt = f"""
You are ARENA's language analyst. A learner of {_lang(language)} produced this material over the last 24 hours.

MATERIAL:
{material}

Update the learner's internal language profile.

Return STRICT JSON:
- "language": object with exactly these keys, each value one of
  ["strong","developing","emerging","improving","needs_attention","inconsistent"]:
  {{ "accuracy": ..., "range": ..., "clarity": ..., "precision": ...,
     "complexity": ..., "fluency": ..., "naturalness": ..., "nuance": ... }}
- "communication": object with exactly these keys, same value set:
  {{ "persuasion": ..., "confidence": ..., "critical_thinking": ..., "empathy": ...,
     "assertiveness": ..., "negotiation": ..., "storytelling": ..., "emotional_control": ...,
     "adaptability": ..., "listening": ..., "questioning": ..., "clarity_of_thought": ... }}
- "summary": one sentence in {_lang(language)}: what changed today.
- "insight": one sentence in {_lang(language)}: a surprising relationship between language and a soft skill.

Rules:
- Judge based on REPEATED patterns, not single mistakes.
- Prefer qualitative labels. Do NOT claim numeric percentages.
"""
    data = _ask_json(prompt, language, temperature=0.3, max_tokens=1000, check_ru=True) or {}
    return {
        "language": data.get("language") or {},
        "communication": data.get("communication") or {},
        "summary": _no_ru(data.get("summary")),
        "insight": _no_ru(data.get("insight")),
    }


# ==================================================================
# ARENA NOTICED
# ==================================================================

def generate_arena_noticed(user_name: str, language: str, level: str,
                           history: str, current_debrief: dict) -> str:
    prompt = f"""
You are ARENA. You have been watching {user_name} over several battles.
Do NOT repeat anything that was already said in the current debrief.

Recent history of the learner across battles:
{history[:2500]}

Current debrief observations (do NOT repeat these):
- best move: {current_debrief.get('best_move', {})}
- lost ground: {current_debrief.get('lost_ground', {})}
- arena noticed (already said): {current_debrief.get('arena_noticed', '')}

Write ONE sentence in {_lang(language)} (level {level}) that connects behavior ACROSS battles —
something deeper than a single-battle observation.

Good examples:
- "You don't struggle to find an opinion. You struggle to make people feel why it's true."
- "Your confidence is ahead of your language precision."

Bad examples (never produce):
- "You need to improve your examples."  /  "Work on your grammar."

Return ONLY the sentence, no quotes, no headings.
"""
    return _no_ru(_ask(prompt, language, temperature=0.85, max_tokens=140)) or ""


# ==================================================================
# FREE TALK
# ==================================================================

def _memory_block(memory: dict | None) -> str:
    memory = memory or {}
    favorites = [t for t in (memory.get("favorite_topics") or []) if t]
    interests = [t for t in (memory.get("interests") or []) if t]
    recent = [t for t in (memory.get("recent_topics") or []) if t]
    said = [s for s in (memory.get("last_said") or []) if s]

    lines = []
    if favorites:
        lines.append(f"Topics they keep coming back to: {', '.join(favorites[:5])}.")
    other = [t for t in (recent or interests) if t.lower() not in {f.lower() for f in favorites}]
    if other:
        lines.append(f"Other things they've mentioned: {', '.join(other[:4])}.")
    if said:
        quoted = " / ".join(f'"{s}"' for s in said[:3])
        lines.append(f"The last few things they said to you: {quoted}")

    if not lines:
        return "You don't know this learner yet."
    return "What ARENA remembers:\n" + "\n".join(f"- {l}" for l in lines)


def generate_freetalk_opening(personality: str, memory: dict | None, language: str,
                              level: str, user_name: str = "") -> str:
    prompt = f"""
You are {_persona(personality)}
You start a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
"Relaxed" means no grading, but your personality and speech habits must remain strong.
{_memory_block(memory)}
Open in character in 1-2 SHORT sentences. Ask ONE engaging question through YOUR personality.
Level: {level}: {_lv(level)}
No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=110) or \
        PERSONALITIES.get(personality, {}).get("phrase", "")


def generate_ai_response(personality: str, history: str, last_user: str, level: str, language: str,
                         mission=None, user_name: str = "", memory: dict | None = None) -> str | None:
    prompt = f"""
You are {_persona(personality)}
This is a relaxed free conversation (no grading) with a language learner{f' named {user_name}' if user_name else ''}.
Even on small talk, your personality must show through.
Level: {level}: {_lv(level)}
{_memory_block(memory)}

Conversation so far:
{history}

The learner just said: "{last_user}"

Reply in character in 1-3 short sentences. React to what they actually said, keep your personality,
ask at most ONE follow-up question. Do not just agree and validate. Do not correct their grammar.
No stage directions, no emojis.
"""
    return _ask(prompt, language, temperature=0.9, max_tokens=150)


# ==================================================================
# ПУШИ
# ==================================================================

def generate_daily_push(personality: str, topics: list, first_name: str, language: str,
                        topic: str | None = None, level: str = "B1") -> str:
    person = PERSONALITIES.get(personality, {})
    topic = topic or (random.choice(topics) if topics else "the thing you keep avoiding")
    prompt = f"""
You are {_persona(personality)}
Write ONE short provocative message (2-3 short lines) to {first_name or 'the learner'}.
The topic that really hooked them: "{topic}". Their level is {level}: {_lv(level)}
Rules:
- Refer to something they said last time, or to a specific angle of "{topic}".
- Throw down a challenge — one uncomfortable question OR one tiny mission for today.
- No greeting, no signature. Address them directly ("you"). No emojis.
"""
    text = _ask(prompt, language, temperature=0.95, max_tokens=140)
    return text or f"{person.get('phrase', 'Your move.')} — {topic}"