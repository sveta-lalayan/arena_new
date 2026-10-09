"""
ai.py — GPT-слой ARENA.

Правила:
  1. Всё, что «говорят» Арена и персонажи, пишется СТРОГО на learning_language.
  2. Debrief: заголовки — interface_language; содержимое — learning_language.
     Форма (single_insight / focused / full) выбирается LLM.
     arena_file_update, grammar_used, steal_it — тоже из LLM.
  3. Сложность речи подгоняется под CEFR через _lv_hard (жёсткая инструкция).
  4. Discovery Engine: extract_evidence, generate_discovery.
"""
import json
import logging
import random
import re

import httpx
from openai import OpenAI, APIStatusError, APIConnectionError

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL, OPENAI_PROXY, FIRST_ENCOUNTER_MOVES
from game_data import (
    LANG_PROMPT_NAME, LEVELS, LEVEL_PROMPTS, PERSONALITIES, PERSONA_BRIEFS, SPEECH_STYLE,
    MISSION_FORMAT_BY_PERSONALITY, SKILL_TO_PERSONALITY, COMMUNICATION_SKILLS,
    LANGUAGE_CRITERIA, ALL_CRITERIA, BEHAVIOUR_BRIEFS, BEGINNER_LEVELS, ARENA_RANKS,
    ARSENAL_TOOL_KEYS, ARSENAL_TOOL_DEFS, ARENA_SIGNALS,
)

logger = logging.getLogger(__name__)

_client = None
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
BEHAVIOURS = list(BEHAVIOUR_BRIEFS)

DISCOVERY_KINDS = (
    "ARENA_HAS_A_THEORY",
    "NEW_DISCOVERY",
    "ARENA_CHANGED_ITS_MIND",
    "NEW_SIGNAL",
    "YOUR_FILE_CHANGED",
    "INTERESTING_PATTERN",
    "UNSOLVED",
    "NEW_WEAPON",
    "ARENA_QUESTION",
    "CONTRADICTION",
)


def _get_client():
    global _client
    if _client is None and OPENAI_API_KEY:
        kwargs = dict(api_key=OPENAI_API_KEY, timeout=45)
        if OPENAI_BASE_URL:
            kwargs["base_url"] = OPENAI_BASE_URL
        if OPENAI_PROXY:
            kwargs["http_client"] = httpx.Client(proxy=OPENAI_PROXY, timeout=45)
        _client = OpenAI(**kwargs)
    return _client


def _lang(language: str) -> str:
    return LANG_PROMPT_NAME.get(language, LANG_PROMPT_NAME.get(
        {"english": "en", "russian": "ru", "german": "de", "spanish": "es",
         "italian": "it", "korean": "ko", "chinese": "zh"}.get(language, "en"),
        "English"
    ))


def _lv(level: str) -> str:
    return LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["B1"])


def _lv_hard(level: str, language: str) -> str:
    """
    Жёсткая инструкция по уровню, которую нельзя игнорировать.
    Используется в generate_battle_turn, generate_ai_response, generate_freetalk_opening.
    """
    lang = _lang(language)
    return (
        f"=== LANGUAGE LEVEL — HARD RULE ===\n"
        f"The learner's CEFR level is {level}.\n"
        f"{LEVEL_PROMPTS.get(level, LEVEL_PROMPTS['B1'])}\n"
        f"This rule OVERRIDES your character's natural speech habits. "
        f"You stay in character — but the WORDS, GRAMMAR and SENTENCE LENGTH must fit {level}. "
        f"A {level} learner must be able to READ every line you write without a dictionary.\n"
        f"Before you send, mentally check: is every sentence at the level of a {level} speaker "
        f"in {lang}? If a sentence is too complex, simplify it — do not change what you mean."
    )


def _system(language: str, extra: str = "") -> str:
    lang = _lang(language)
    return (
        f"You are part of ARENA, a language-training game where learners debate characters. "
        f"Write ONLY in {lang}. Never write any other language. {extra}".strip()
    )


_TEMPLE_SYSTEM = (
    "You are ARENA — a calm, attentive presence listening to a stranger for the first time. "
    "You are curious, specific, genuinely interested. You do NOT perform insight. You do NOT diagnose. "
    "You ask about what is actually in front of you. As the conversation goes on, you begin to notice "
    "small patterns — and you offer careful, provisional guesses. "
    "You never flatter, never paraphrase, never say 'interesting'. You never ask 'why do you like it' "
    "or 'tell me more'. "
    "SOMETIMES — not often — you are ironic. Not mean, not sarcastic-as-attack. Ironic in the way "
    "a smart friend is: you notice the small absurdity of what the person just said and you name it "
    "with a light touch. "
    "SOMETIMES you have your own opinion and share it briefly. This invites them to answer. "
    "SOMETIMES — when they joke or are self-deprecating — you play along in the same tone. "
    "You are allowed to say something that is NOT a question. A short reaction is often better than "
    "another question. "
    "ALWAYS SPEAK SIMPLY. Short sentences. Same level as the person — never above. Everyday words. "
    "If a thought needs more than two sentences, do not make it. "
    "Never use abstract concepts like 'control', 'identity', 'fear', 'discipline', 'armour', "
    "'vulnerability', 'authenticity'. Never write metaphors. "
    "Write ONLY in {lang}. Never write in any other language."
)


def _temple_system(language: str) -> str:
    return _TEMPLE_SYSTEM.format(lang=_lang(language))


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
        body = None
        try:
            body = e.response.text
        except Exception:
            pass
        logger.error("OpenAI API error: status=%s body=%s", e.status_code, body)
        return None
    except APIConnectionError:
        logger.error("OpenAI connection error — запрос не дошёл до api.openai.com")
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

ARENA_MOMENTS = {
    "reflect": (
        "REFLECT — say one small thing you noticed about HOW they talk, in plain everyday words. "
        "Like: 'You keep saying a number every time.' / 'You always answer with a question first.' "
        "Short. Concrete. About a word or a habit, not about their personality."
    ),
    "connect": (
        "CONNECT — link two things they said earlier that are actually the same thing, "
        "in one short line. Like: 'First the coffee, now the gym — same thing, right?' "
        "Do not explain the link. Just name it and stop."
    ),
    "probe": (
        "PROBE — ask ONE small question that tests your guess. Simple, direct, answerable right away. "
        "Like: 'Did you pick it, or did they?' / 'Was that your idea or someone else's?' "
        "Not a deep question. A quick one."
    ),
}

MOMENT_SCHEDULE = {3: "reflect", 5: "connect", 7: "probe"}


def generate_arena_reaction(history: str, user_text: str, language: str, turn: int) -> str | None:
    moment = MOMENT_SCHEDULE.get(turn)

    if turn <= 2:
        task = """
This is an early message (turn 1 or 2). You are a smart, attentive conversationalist.
You are NOT yet offering hypotheses about this person.

Pick ONE of these moves and commit to it — the more natural one for THIS message:

  A) SIMPLE FOLLOW-UP — pick ONE concrete thing they said and ask ONE short question about it.
     "Which one?" / "What part of it?" / "Home or somewhere specific?"

  B) SHARE YOUR VIEW — say ONE short line about what you actually think, then optionally ask.
     "I'd have picked the other one." / "Same here."

  C) PICK UP THE HUMOUR — if they said something with a joke, irony, or self-deprecation,
     play along in the same tone.

  D) GENTLE NEEDLE — a light, friendly jab at something small they just said.
     "That's the humble version." / "Very modest."

HARD BANS:
- No hypotheses about who they are yet.
- No 'interesting', 'great', 'nice', 'cool', 'fascinating'.
- No 'tell me more', 'elaborate', 'why do you think that'.
- No paraphrase of what they said before asking.
- No emojis, no greeting, no lists.

Output is 1 short sentence, or 1 short sentence + 1 short question. Nothing else.
"""
        tokens = 110

    elif moment:
        task = f"""
{ARENA_MOMENTS[moment]}

CRITICAL — the moment must stay EASY and SMALL:
- One short observation about something they ACTUALLY said, in everyday words.
- 1-2 SHORT sentences. Never more.
- A light touch of irony is allowed, but only if it fits naturally.
- Point to a SPECIFIC WORD they actually typed.

HARD BANS:
- No big abstract concepts ('control', 'identity', 'fear', 'discipline or armour').
- No 'interesting', 'tell me more', 'why do you think that'.
- No paraphrase. No emojis. No lists.

Output is 1-2 SHORT sentences. Nothing else.
"""
        tokens = 150

    else:
        task = """
You are now a few messages in. You may or may not see a small pattern yet.

Choose the move that fits THIS message best:

  A) SIMPLE FOLLOW-UP — ask ONE easy, concrete question about the last thing they said.
  B) SHORT OBSERVATION — only if you see an OBVIOUS, SIMPLE pattern.
  C) LIGHT IRONY — a short dry remark. Use SPARINGLY.
  D) SHARE YOUR VIEW — one short line about what you think, without asking a question.

DO NOT:
- force insight. If nothing obvious — use A.
- use abstract words ('control', 'identity', 'fear', 'discipline', 'armour', 'vulnerability').
- write more than 2 short sentences.
- paraphrase their message and then ask about it.
- say 'interesting', 'tell me more', 'elaborate', 'why do you think that'.
- use emojis, greetings, lists.

Output is 1-2 SHORT sentences.
"""
        tokens = 130

    prompt = f"""
The conversation so far:
{history}

They just said: "{user_text}"

This is their message number {turn} of {FIRST_ENCOUNTER_MOVES}.

{task}
"""
    system = _temple_system(language)
    text = _chat(system, prompt, temperature=0.92, max_tokens=tokens)
    if text and _lang(language) != "Russian" and _CYRILLIC.search(text):
        text = _chat(system + f" Answer strictly in {_lang(language)}.",
                     prompt, temperature=0.92, max_tokens=tokens)
        if text and _CYRILLIC.search(text):
            return None
    return _clean(text)


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
    claim = (data.get("claim") or "").strip() if isinstance(data.get("claim"), str) else ""
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
        "claim": claim,
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

Return a JSON object with EXACTLY these keys:
- "estimated_level": one of {LEVELS}
- "language": {{"grammar": int, "vocabulary": int, "fluency": int, "naturalness": int}}
- "communication": {{"clarity": int, "argumentation": int, "adaptability": int, "persuasion": int, "evidence": int, "control": int}}
- "hidden": {{"resilience": int}}
- "behaviour": one of {BEHAVIOURS}. Meaning: {json.dumps(BEHAVIOUR_BRIEFS)}
- "grammar_weak_areas": up to 3 short English strings
- "vocabulary_weak_areas": up to 3 short English strings
- "interests": 3-5 short topic phrases (1-4 words each) in {lang}
- "main_topic": the ONE topic they care about most, 2-5 words, in {lang}
- "recommended_personality": one of {list(PERSONALITIES)}. Pick the character who best fits
  BOTH their main topic AND their weakest communication skill.
  CRITICAL: do NOT default to hr_manager. She is only correct when the learner's weakest
  skill is "adaptability" AND the topic is workplace-related. For most learners, one of
  devil_advocate / journalist / professor / ceo is a better fit. If two characters are
  equally good fits, pick the one that will SURPRISE the learner — the less obvious choice.
- "pattern": the ONE pattern phrase (from the list), lowercase, exactly as written
- "pattern_evidence": list of 2-4 short quotes (VERBATIM) that justify the pattern
- "claim": ONE concrete opinion the learner actually stated, short phrase in {lang}, or ""
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
    said = "\n".join(f"- {t}" for t in user_responses[-8:])
    pattern_line = (
        f"An internal hint about them (do NOT mention it as a label): {pattern}."
        if pattern else ""
    )

    prompt = f"""
You are ARENA. You just listened to a stranger across several messages. Now you say
ONE thing about them that they probably have not said to themselves.

What they said:
{said}

{pattern_line}

This is the REVEAL — the moment the person should stop and think: "she's right, I do
that — but I never said it out loud."

Write EXACTLY 2 short paragraphs, separated by a blank line.

=== WHAT MAKES A GREAT REVEAL ===
1. It is about THE PERSON, not about their speech style.
2. It CONNECTS 2-3 separate things they said — things that look unrelated — and shows
   they point at the same thing.
3. It is a GUESS, not a verdict.
4. It NAMES something they have not named themselves.
5. It can be slightly uncomfortable, but never cruel.

=== GOOD SHAPES (do NOT copy — match the level of insight) ===
  "You came into this conversation as if through the side door — coffee, work, small
   things. But every small thing you mentioned had something in it you cared about.
   You just didn't say it out loud. Maybe you don't say it to yourself either."

  "You don't talk about what you want. You talk about what you're good at, and let the
   person figure out the rest. That's a choice — not a habit. I don't know yet why."

  "Every answer you gave had a small test in it — as if you were checking whether
   I'd understand. Not the words. The thing behind the words. I noticed it three times."

  "You keep saying the version of yourself that gets things done. There's another
   version somewhere in what you said — I can almost see it — but you don't bring it
   to the table."

=== WHAT TO AVOID (this is a hard ban) ===
- Do NOT describe their speech: 'short sentences', 'you always add examples',
  'you use numbers', 'you answer with a question', 'you speak directly'.
- Do NOT use formulaic openings: 'you always', 'every time you', 'you never'.
- Do NOT name abstract concepts directly: 'control', 'identity', 'fear', 'vulnerability',
  'authenticity', 'discipline', 'armour'. Talk in plain words.
- Do NOT paraphrase what they said.
- Do NOT praise, diagnose, or advise.
- Do NOT use metaphors or poetic images.
- Do NOT invent facts they never mentioned.
- No emojis, no headings, no character names.

Before you write, ask yourself: could this observation apply to any random person?
If yes, rewrite it. It must contain at least ONE specific word, image or detail
from what they actually said.

Paragraph 1 — the observation. 2-3 sentences. Short. Specific.
Paragraph 2 — one short closing line that keeps the doubt. Max 10 words.

Write ONLY in the target language.
"""
    system = _temple_system(language)
    text = _chat(system, prompt, temperature=0.95, max_tokens=280)
    if text and _lang(language) != "Russian" and _CYRILLIC.search(text):
        text = _chat(system + f" Answer strictly in {_lang(language)}.",
                     prompt, temperature=0.95, max_tokens=280)
        if text and _CYRILLIC.search(text):
            return None
    return _clean(text) or ""


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
- Do NOT mention the topic, do NOT mention the character's name.
- Do NOT use words like "convince", "explain", "argue", "support", "provide", "thesis", "examples".
- Never longer than 5 words. Period.

Good examples (do NOT copy, just match the LENGTH and TONE):
"Change his mind."
"Get the budget."
"Make her reconsider."
"Defend your decision."
"Get him to commit."

Answer with ONE line, no quotes, no punctuation at the end except a period.
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
Prepare the "arsenal" for a debate battle.
Character: {_persona(personality)}
Topic: "{topic}". Learner level: {level}: {_lv(level)}
Learner weak spots — grammar: {weak_areas.get('grammar_weak_areas', [])}, vocabulary: {weak_areas.get('vocabulary_weak_areas', [])},
weakest communication skill: {weakest_skill or 'unknown'}.

Return JSON with:
- "weapons": list of exactly {n} items: {kind}.
- "tip": ONE short sentence.
- "win_condition": 1-2 short lines.
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
                               mission: str = "", claim: str = "") -> str:
    if claim:
        phrase = PERSONALITIES.get(personality, {}).get("phrase", "")
        prompt = f"""
You are {_persona(personality)}

A learner just entered a battle with you. Earlier, in a private talk with ARENA, they said: "{claim}".
Open the battle in 2 SHORT lines, fully in character:
1. A short reaction, then quote their claim back to them ("You said ...").
2. A direct challenge (your trademark phrase is: "{phrase}").

Rules: no intro, no rules, no praise, no grammar correction. No "Let's discuss".
Their level is {level}: {_lv(level)}
No emojis, no stage directions, no quotes around your reply.
"""
        return _ask(prompt, language, temperature=0.9, max_tokens=110) or phrase

    prompt = f"""
You are {_persona(personality)}

A learner just entered a battle with you. Topic: "{topic}". Your mission (for them): {mission}.

Open the battle — 1-2 short sentences:
1. State YOUR concrete position on "{topic}". A bit skeptical or contrarian, not neutral.
2. End with ONE direct question.

Rules: no "What do you think?", no intro, no rules, no "Let's discuss". Speak as a real person.
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

{_lv_hard(level, language)}

Conversation so far:
{history}

The learner's latest message: "{last_user}"
Your current conviction that the learner is right: {conviction} (100 = not convinced at all, 0 = fully convinced).

Do two things:
1. Reply in character, in {_lang(language)}, 1-3 short sentences.
   CRITICAL: BEFORE you react, check — did the learner ask you a DIRECT QUESTION or ask for your
   opinion/experience? If yes, answer it FIRST, in character. Only AFTER answering may you add
   pressure, a counter-argument, or ONE follow-up question.
   If they did NOT ask you anything, push back, probe, or ask ONE follow-up question.
   Do not hand the answer to their mission. Do not correct their grammar.
2. Decide the NEW conviction. Lower by 8-30 ONLY if the message contains a genuinely strong,
   specific argument. Lower by 0-6 for weak answers. RAISE by up to 10 if they dodged.

Return JSON: {{"reply": "<your reply>", "conviction": <integer 0-100>}}
"""
    data = _ask_json(prompt, language, temperature=0.85, max_tokens=280, check_ru=True) or {}
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
Score every criterion 0-100 RELATIVE to what is expected at level {level}.

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
                            unlocked_tools: set | None = None,
                            unsolved_questions: list | None = None,
                            grammar_phrases: list | None = None) -> dict:
    person = PERSONALITIES.get(personality, PERSONALITIES["devil_advocate"])
    user_lines = [d["text"] for d in dialogue if d["speaker"] == "User"]
    char_lines = [d["text"] for d in dialogue if d["speaker"] != "User"]
    user_blob = "\n".join(user_lines)
    char_blob = "\n".join(char_lines)

    result_state = "VICTORY" if won else ("ALMOST" if win_score >= 50 else "DEFEATED")
    if won and win_score >= 85:
        result_state = "OUTPLAYED"

    prev_block = "Not enough previous data — treat this as a first data point."
    if previous_criteria:
        deltas = []
        for k, v in criteria.items():
            prev_v = previous_criteria.get(k)
            if prev_v is not None and abs(v - prev_v) >= 8:
                deltas.append(f"{k}: {prev_v} → {v}")
        prev_block = (
            f"Learner's profile BEFORE: {json.dumps(previous_criteria)}. "
            f"Notable shifts: {'; '.join(deltas) if deltas else 'no single skill moved much'}. "
            "If a previously weak skill improved, say so explicitly as growth."
        )

    unlocked_tools = unlocked_tools or set()
    tools_listing = "\n".join(f'- "{k}": {d}' for k, d in ARSENAL_TOOL_DEFS.items())
    owned_note = (
        f"They already have: {', '.join(sorted(unlocked_tools))}."
        if unlocked_tools else "They haven't unlocked any of these yet."
    )

    signals_listing = "\n".join(f'- "{k}": {v["brief"]}' for k, v in ARENA_SIGNALS.items())
    unsolved_listing = "\n".join(f"- {q}" for q in (unsolved_questions or [])) or "(none)"

    phrases_list = grammar_phrases or []
    if phrases_list:
        phrases_listing = "\n".join(f'- «{p}»' for p in phrases_list[:40])
    else:
        phrases_listing = "(none yet)"

    prompt = f"""
You are ARENA writing the debrief after a debate battle. Voice: terse, sharp, but fair.

=== OUTPUT LANGUAGE ===
EVERY free-text value MUST be in {_lang(language)} — the LEARNER'S TARGET LANGUAGE.
NOT English (unless English IS the target). NOT the UI language. Never mix.
JSON keys stay in English for parsing; values stay in {_lang(language)}.
Match complexity to level {level}: {_lv(level)}.

=== THE CORE IDEA ===
The debrief must reveal the MECHANISM of what happened — NOT list mistakes.
NEVER announce a permanent trait from one battle.

=== DEBRIEF SHAPE ===
Use "debrief_shape":
  • "single_insight" — short battle or only ONE precise thing worth saying.
    Fill ONLY "single_insight"; other fields empty.
  • "focused" — one coherent story. Pick exactly TWO content fields.
  • "full" — material for a rich debrief.

=== CONTEXT ===
Learner: {user_name}. Character: {_persona(personality)} — stay IN CHARACTER for advice.
Topic: "{topic}". Mission: {mission or 'convince the character'}.
Result: win_score = {win_score}/100, character's remaining doubt = {conviction}/100.
Scores: {json.dumps(criteria)}
Observed long-term pattern (from Temple): {pattern or 'not specified'}

MY ARENA (long-term profile before → now):
{prev_block}

The learner's messages (in {_lang(language)}):
{user_blob}

The character's lines:
{char_blob}

CURRENT UNSOLVED QUESTIONS (for reference — if this battle resolves any, list in
arena_file_update.unsolved_resolve; otherwise []):
{unsolved_listing}

=== GRAMMAR PHRASES FROM THEIR ARSENAL ===
{phrases_listing}

If the learner actually used one of these phrases (or a close paraphrase), return it
VERBATIM in "grammar_used". Otherwise null.

=== CRITICAL RULES ===
- Quote REAL words from the learner. Paraphrasing kills the value.
- Every critique and every praise must be tied to a specific sentence they wrote.
- NEVER invent facts about the learner.
- Do NOT invent grammar mistakes that aren't in the transcript.

=== JSON KEYS (ALL VALUES in {_lang(language)}) ===
- "debrief_shape": "single_insight" | "focused" | "full".
- "headline": SHORT label. 1-2 words + period.
- "single_insight": if shape=="single_insight", ONE short line. Otherwise "".
- "notification_line": ONE short sentence — same insight as single_insight. "" for "full".
- "result_state_label": SHORT label of the outcome (1-2 words).
- "result_state": "VICTORY"|"ALMOST"|"DEFEATED"|"OUTPLAYED".
- "result_line": 1-2 sentences. "" for single_insight.
- "the_moment": Object {{"quote_user", "quote_opponent", "why_it_mattered"}} or null.
- "the_mechanism": 3-4 sentences (good + held back).
- "steal_it": ONE concrete thing the learner could steal from this battle and use next time.
    Object:
      "said": VERBATIM — what the learner actually wrote (a real line from the dialogue,
              or a fragment of one, that contains a fixable issue or a moment that could
              be said better),
      "better": the improved version in {_lang(language)} — same idea, sharper words,
                better construction, or natural phrasing. This is a LANGUAGE / EXPRESSION
                upgrade, not a rewrite of the argument.
      "why": ONE short sentence in {_lang(language)} — why the better version lands
             harder / sounds more native / is clearer.
      "grammar_note": ONE short sentence in {_lang(language)} — the grammar point behind
                      the improvement (e.g. "the article is needed because you're naming
                      a specific noun", "past simple because the action is finished").
                      Return "" if there is no grammar point (purely vocabulary / phrasing).
    Return null if the battle contained no clear line worth upgrading.
- "escape_route": Object {{"trap", "rule", "example"}} or null.
- "tool_used": one of these 8 keys, or null:
{tools_listing}
    Ground it in something they ACTUALLY did. {owned_note}
- "grammar_used": VERBATIM one phrase from the list, or null.
- "arena_read": Object {{"skill_now", "test_next"}} or null.
- "opponent_advice": 1-2 sentences IN CHARACTER. Or "".
- "deeper_content": Object {{"topic", "why"}} or null.

=== ARENA FILE UPDATE ===
- "arena_file_update": Object with:
    "current_read": ONE sentence — HYPOTHESIS in ARENA's voice. "" if unchanged.
    "current_read_changed": true if materially different.
    "under_pressure": short trajectory "push back → explain → defend → reframe".
    "unsolved_add": up to 2 SHORT questions this battle raised. [].
    "unsolved_resolve": list of EXISTING questions (verbatim) that this battle answered. [].
    "signals_hint": up to 2 signal ids visible in this battle. [].
        Available: {signals_listing}

Keep everything SHORT.
"""
    data = _ask_json(prompt, language, temperature=0.7, max_tokens=2200, check_ru=True) or {}

    shape = str(data.get("debrief_shape") or "full").strip().lower()
    if shape not in ("single_insight", "focused", "full"):
        shape = "full"

    headline = _no_ru(str(data.get("headline") or "").strip())[:60]
    single_insight = _no_ru(str(data.get("single_insight") or "").strip())[:400]
    notification_line = _no_ru(str(data.get("notification_line") or "").strip())[:300]
    result_state_label = _no_ru(str(data.get("result_state_label") or "").strip())[:40]

    the_moment = None
    mq = data.get("the_moment")
    if isinstance(mq, dict):
        qu = str(mq.get("quote_user", "")).strip()
        qo = str(mq.get("quote_opponent", "")).strip()
        why = str(mq.get("why_it_mattered", "")).strip()
        if qu and why and _in_text(qu, user_blob):
            the_moment = {"quote_user": qu[:250], "quote_opponent": qo[:250],
                          "why_it_mattered": _no_ru(why)[:400]}

    the_mechanism = _no_ru(str(data.get("the_mechanism") or "").strip())[:600]

    # --- STEAL IT (объединяет the_shift + language_upgrade + grammar_focus) ---
    steal_it = None
    si = data.get("steal_it")
    if isinstance(si, dict):
        said = str(si.get("said", "")).strip()
        better = str(si.get("better", "")).strip()
        why = str(si.get("why", "")).strip()
        gram = str(si.get("grammar_note", "")).strip()
        if said and better and why and said.lower() != better.lower() and _in_text(said, user_blob):
            steal_it = {
                "said": said[:220],
                "better": better[:220],
                "why": _no_ru(why)[:240],
                "grammar_note": _no_ru(gram)[:200],
            }

    escape_route = None
    er = data.get("escape_route")
    if isinstance(er, dict):
        trap = str(er.get("trap", "")).strip()
        rule = str(er.get("rule", "")).strip()
        example = str(er.get("example", "")).strip()
        if rule:
            escape_route = {"trap": _no_ru(trap)[:120], "rule": _no_ru(rule)[:260],
                            "example": example[:260]}

    tool_used = str(data.get("tool_used") or "").strip().lower()
    if tool_used not in ARSENAL_TOOL_KEYS:
        tool_used = None

    grammar_used = None
    gu = data.get("grammar_used")
    if isinstance(gu, str) and gu.strip() and phrases_list:
        gu_clean = gu.strip()
        for p in phrases_list:
            pl = p.lower().strip()
            gul = gu_clean.lower().strip()
            if pl and (pl in gul or gul in pl):
                if _in_text(p, user_blob) or _in_text(gu_clean, user_blob):
                    grammar_used = p[:300]
                    break

    arena_read = None
    ar = data.get("arena_read")
    if isinstance(ar, dict):
        sn = str(ar.get("skill_now", "")).strip()
        tn = str(ar.get("test_next", "")).strip()
        if sn or tn:
            arena_read = {"skill_now": _no_ru(sn)[:400], "test_next": _no_ru(tn)[:200]}

    mistakes = []
    for m in (data.get("mistakes") or [])[:3]:
        if isinstance(m, dict):
            wrong = str(m.get("wrong", "")).strip()
            correct = str(m.get("correct", "")).strip()
            if wrong and correct and wrong.lower() != correct.lower() and _in_text(wrong, user_blob):
                mistakes.append({"wrong": wrong, "correct": correct})

    deeper_content = None
    deeper = data.get("deeper_content")
    if isinstance(deeper, dict):
        dt = str(deeper.get("topic", "")).strip()
        dw = str(deeper.get("why", "")).strip()
        if dt and dw:
            deeper_content = {"topic": dt[:60], "why": _no_ru(dw)[:200]}

    next_target = str(data.get("next_target", "")).strip().lower()
    if next_target not in COMMUNICATION_SKILLS:
        criteria_sorted = sorted(criteria.items(), key=lambda kv: kv[1])
        for k, _ in criteria_sorted:
            if k in COMMUNICATION_SKILLS:
                next_target = k
                break
    if next_target not in COMMUNICATION_SKILLS:
        next_target = ""

    next_target_label = _no_ru(str(data.get("next_target_label") or "").strip())[:80]

    arena_file_update = None
    afu = data.get("arena_file_update")
    if isinstance(afu, dict):
        unsolved_add = [str(q).strip()[:200] for q in (afu.get("unsolved_add") or [])
                        if isinstance(q, str) and q.strip()][:2]
        unsolved_resolve = [str(q).strip()[:200] for q in (afu.get("unsolved_resolve") or [])
                            if isinstance(q, str) and q.strip()][:5]
        signals_hint = [str(s).strip().lower() for s in (afu.get("signals_hint") or [])
                        if isinstance(s, str) and s.strip() and s.strip().lower() in ARENA_SIGNALS][:2]
        arena_file_update = {
            "current_read": _no_ru(str(afu.get("current_read") or "").strip())[:300],
            "current_read_changed": bool(afu.get("current_read_changed")),
            "under_pressure": _no_ru(str(afu.get("under_pressure") or "").strip())[:200],
            "unsolved_add": unsolved_add,
            "unsolved_resolve": unsolved_resolve,
            "signals_hint": signals_hint,
        }

    return {
        "debrief_shape": shape,
        "headline": headline,
        "single_insight": single_insight,
        "notification_line": notification_line,
        "result_state": result_state,
        "result_state_label": result_state_label,
        "result_line": _no_ru(data.get("result_line")),
        "the_moment": the_moment,
        "the_mechanism": the_mechanism,
        "steal_it": steal_it,
        "escape_route": escape_route,
        "tool_used": tool_used,
        "grammar_used": grammar_used,
        "arena_read": arena_read,
        "opponent_advice": _no_ru(data.get("opponent_advice")),
        "deeper_content": deeper_content,
        "mistakes": mistakes,
        "next_target": next_target,
        "next_target_label": next_target_label,
        "arena_file_update": arena_file_update,
        "character": person["short_name"],
        # для обратной совместимости — больше не используются в рендере
        "the_shift": None,
        "language_upgrade": None,
        "grammar_focus": None,
        "grammar_for_goal": None,
    }


def _memory_block(memory: dict | None) -> str:
    memory = memory or {}
    favorites = [t for t in (memory.get("favorite_topics") or []) if t]
    interests = [t for t in (memory.get("interests") or []) if t]
    recent = [t for t in (memory.get("recent_topics") or []) if t]
    said = [s for s in (memory.get("last_said") or []) if s]

    lines = []
    if favorites:
        lines.append(f"Topics they keep coming back to — favorites: {', '.join(favorites[:5])}.")
    other_recent = [t for t in (recent or interests) if t.lower() not in {f.lower() for f in favorites}]
    if other_recent:
        lines.append(f"Other things they've mentioned: {', '.join(other_recent[:4])}.")
    if said:
        quoted = " / ".join(f'"{s}"' for s in said[:3])
        lines.append(f"The last few things they said to you: {quoted}")

    if not lines:
        return "You don't know this learner yet — this is effectively your first conversation."
    return (
        "What ARENA remembers about this learner:\n"
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

{_lv_hard(level, language)}

=== HARD RULES ===
- Output is ONE opening message, 1-2 SHORT sentences.
- It contains EXACTLY ONE question at the end. Not two. Not three.
- Do NOT ask about two different topics.
- Do NOT greet the learner twice.
- Do NOT write "How are you? And also ...".
- Just ONE thing: one observation, one question.

Bring up something from what you remember about them (or a topic you would naturally raise),
filtered through YOUR personality, and ask ONE engaging question.
No stage directions, no emojis, no line breaks inside the reply.
"""
    text = _ask(prompt, language, temperature=0.9, max_tokens=110)
    if not text:
        return PERSONALITIES.get(personality, {}).get("phrase", "")
    if text.count("?") > 1:
        idx = text.find("?")
        text = text[:idx + 1].strip()
    text = " ".join(text.split())
    return text


# ==================================================================
# ПУШИ
# ==================================================================

def generate_daily_push(personality: str, topics: list, first_name: str, language: str,
                        topic: str | None = None, level: str = "B1") -> str:
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


# ==================================================================
# PERSONALIZATION MEMORY: извлечение сигналов
# ==================================================================

def extract_signals(user_lines: list[str], language: str, source: str,
                    taxonomy: list[str], catalog: dict) -> dict:
    lines = [l[:300] for l in user_lines[-12:]]
    blob = "\n".join(f"- {l}" for l in lines)
    topics_listing = ", ".join(f'"{t}"' for t in taxonomy)
    patterns_listing = "\n".join(f'- "{pid}": {m["brief"]}' for pid, m in catalog.items())

    prompt = f"""
You are ARENA's silent analyst. Below are messages a language learner wrote in a {source.replace('_', ' ')} conversation.
Extract signals for long-term memory. Be conservative: an empty list is a good answer.

Learner's messages:
{blob}

Return JSON with:
- "topics": up to 3 objects {{"cluster": <EXACTLY one of: {topics_listing}>, "example": <1-4 words>}}.
- "patterns": up to 2 objects {{"id": <EXACTLY one id from the list>, "example": <quote COPIED VERBATIM,
    max 15 words>}}. A single message is weak evidence — if you are not sure, return [].
- "professional_context": a SHORT phrase (2-6 words, in {_lang(language)}) if EXPLICITLY stated. Else "".
- "goals": up to 2 SHORT phrases (max 8 words each, in {_lang(language)}) if EXPLICITLY stated. Else [].
- "avoids": up to 1 SHORT phrase (max 6 words) if they CLEARLY stepped away from a topic. Else [].

NEVER invent — if not explicitly stated, return empty.
Pattern ids:
{patterns_listing}
"""
    data = _ask_json(prompt, language, temperature=0.2, max_tokens=600) or {}
    text = "\n".join(user_lines)
    by_lower = {t.lower(): t for t in taxonomy}

    topics, seen_c = [], set()
    for t in (data.get("topics") or [])[:3]:
        if not isinstance(t, dict):
            continue
        cluster = by_lower.get(str(t.get("cluster", "")).strip().lower())
        if cluster and cluster not in seen_c:
            seen_c.add(cluster)
            topics.append({"cluster": cluster, "example": str(t.get("example", "")).strip()[:60]})

    patterns, seen_p = [], set()
    for p in (data.get("patterns") or [])[:2]:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id", "")).strip()
        ex = str(p.get("example", "")).strip()
        if pid in catalog and pid not in seen_p and ex and _in_text(ex, text):
            seen_p.add(pid)
            patterns.append({"id": pid, "example": ex[:160]})

    prof = str(data.get("professional_context", "")).strip()[:60]
    goals = [str(g).strip()[:80] for g in (data.get("goals") or []) if isinstance(g, str) and g.strip()][:2]
    avoids = [str(a).strip()[:60] for a in (data.get("avoids") or []) if isinstance(a, str) and a.strip()][:1]

    return {"topics": topics, "patterns": patterns,
            "professional_context": prof, "goals": goals, "avoids": avoids}


# ==================================================================
# ПЕРСОНАЛИЗИРОВАННОЕ ЕЖЕДНЕВНОЕ НАПОМИНАНИЕ
# ==================================================================

_GENERIC_REMINDER_PHRASES = (
    "ready for your daily battle", "improve your english", "time to practice",
    "your daily challenge is waiting", "daily challenge", "daily battle",
)

_REMINDER_INSTRUCTIONS = {
    "interest_hook": "Pull them back through a topic they keep returning to. Ask one sharp question.",
    "continuation": "Continue the recent conversation: pick up the specific thing and push further.",
    "arsenal_hook": "Remind them of a move they already own and challenge them to use it today.",
    "debrief_hook": "Refer to what held them back last time (no scolding) and set today's small target.",
    "challenge_hook": "Name what they are working on and promise to test exactly that today.",
    "provocative_question": "Ask ONE provocative question tied to this interest that forces a side.",
    "battle_invitation": "Invite them to a battle against that specific opponent on that specific topic.",
    "language_hook": "Give a specific micro-challenge: use the sharper phrasing today.",
    "goal_hook": "Remind them of the goal they themselves stated, turn it into today's micro-challenge.",
    "context_hook": "Connect their professional context to a topic they care about — one sharp question.",
}


def generate_personalized_reminder(selection: dict, first_name: str, language: str,
                                   level: str = "B1") -> str | None:
    facts = "\n".join(f"- {f}" for f in selection["facts"])
    prompt = f"""
You are ARENA — a calm voice that remembers the learner.
Write ONE short notification (2-3 short lines, at most 45 words) to {first_name or 'the learner'}.
Their level is {level}: {_lv(level)}

Notification type: {selection['type']}. {_REMINDER_INSTRUCTIONS[selection['type']]}

Facts you may use (ONLY these — never invent):
{facts}

Rules:
- They should think "wait — ARENA remembers that?" — refer to the specific fact above.
- Time words only if consistent with "days ago".
- Never "ready for your daily battle", "improve your English today", "time to practice".
- No greeting, no signature, no emojis. Address them as "you".
- End with a sharp question or a one-line challenge.
- Write in {_lang(language)} — the learner's target language, matching level {level}.
"""
    text = _ask(prompt, language, temperature=0.9, max_tokens=140)
    if not text:
        return None
    low = text.lower()
    if any(p in low for p in _GENERIC_REMINDER_PHRASES) or len(text) > 420:
        return None
    return text


# ==================================================================
# DISCOVERY ENGINE
# ==================================================================

def extract_evidence(user_lines: list[str], source: str, language: str,
                     known_signals: list[str], known_patterns: list[str],
                     user_name: str = "") -> list[dict]:
    lines = [l[:300] for l in user_lines[-10:]]
    if not lines:
        return []
    blob = "\n".join(f"- {l}" for l in lines)
    signals_line = ", ".join(known_signals) if known_signals else "(none yet)"
    patterns_line = ", ".join(known_patterns) if known_patterns else "(none yet)"

    prompt = f"""
You are ARENA's silent evidence-collector. Below are messages a language learner wrote in a
{source.replace('_', ' ')} conversation. Extract up to 3 small pieces of evidence about HOW
this person communicates — moments that could later become part of a longer-term picture.

Learner's messages:
{blob}

Context ARENA already has about them:
- Signals seen before: {signals_line}
- Behavioural patterns seen before: {patterns_line}

Return JSON with exactly one key "evidence": a list of up to 3 objects:
  {{
    "text_excerpt": a quote COPIED VERBATIM from their messages (max 15 words),
    "detected": ONE short sentence in {_lang(language)} — what you actually observed in this quote,
    "interpretation": ONE short sentence in {_lang(language)} — how that connects to what ARENA
                      already knows (or, if new, name the shape of what it might become),
    "confidence": a number 0-1
  }}

Rules:
- Be conservative: if nothing stands out, return an empty list.
- Every "text_excerpt" must be a real quote, not a paraphrase.
- Do NOT invent details.
- Do NOT use: 'interesting', 'great', 'cool'.
- Do NOT mention language levels, grammar, vocabulary.
"""
    data = _ask_json(prompt, language, temperature=0.4, max_tokens=500) or {}
    raw = data.get("evidence") or []
    user_blob = "\n".join(user_lines)
    out = []
    for item in raw[:3]:
        if not isinstance(item, dict):
            continue
        excerpt = str(item.get("text_excerpt") or "").strip()
        if not excerpt or not _in_text(excerpt, user_blob):
            continue
        detected = _no_ru(str(item.get("detected") or "").strip())[:300]
        if not detected:
            continue
        try:
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        out.append({
            "text_excerpt": excerpt[:400],
            "detected": detected,
            "interpretation": _no_ru(str(item.get("interpretation") or "").strip())[:400],
            "confidence": max(0.0, min(1.0, conf)),
        })
    return out


def generate_discovery(recent_evidence: list[dict], patterns: list[dict],
                       current_read: str, unsolved: list[str],
                       interests: list[str], last_kinds: list[str],
                       language: str, level: str) -> dict | None:
    if not recent_evidence:
        return None

    ev_listing = "\n".join(
        f"[{e['id']}] ({e['confidence']:.2f}) {e['text_excerpt']!r} — {e['detected']}"
        + (f" | {e['interpretation']}" if e.get('interpretation') else "")
        for e in recent_evidence[-20:]
    )

    patterns_line = "\n".join(
        f"- {p['pattern_id']} ({p['status']}, {p['evidence_count']} obs)"
        for p in patterns[:10]
    ) or "(none)"

    unsolved_line = "\n".join(f"- {q}" for q in unsolved[:5]) or "(none)"
    interests_line = ", ".join(interests[:8]) or "(none)"
    recent_kinds_line = ", ".join(last_kinds) or "(none)"
    kinds_listing = "\n".join(f'- "{k}"' for k in DISCOVERY_KINDS)

    prompt = f"""
You are ARENA — a quiet, sharp intelligence that is slowly building a picture of one person.
You look at evidence collected over recent conversations and decide: is there anything NEW
and INTERESTING to say to them today?

Recent evidence (chronologically, latest last):
{ev_listing}

What ARENA already knows (patterns):
{patterns_line}

Current long-term read on this person:
{current_read or '(not set yet)'}

Unsolved questions ARENA is investigating:
{unsolved_line}

Their interests: {interests_line}

Recent discovery kinds already sent (so you don't repeat):
{recent_kinds_line}

=== WHAT MAKES A GOOD DISCOVERY ===
1. It is evidence-based. Do NOT invent a clever insight and then look for support.
2. It NAMES something the learner probably has not named themselves.
3. It changes the picture — a new observation, a contradiction with what ARENA thought,
   or a signal that just crossed into "confirmed".
4. It is phrased simply, in {_lang(language)}, at their level {level}.
5. It can be slightly uncomfortable. Never cruel.

=== WHEN TO RETURN NOTHING ===
- If the evidence is only confirming what ARENA already said recently.
- If the insight is generic ('you communicate well', 'you're getting better').
- If the evidence is one data point away from forming a real pattern — wait.
- If the only available type would repeat the last kinds sent.

Return JSON with exactly this shape:
{{
  "decision": "publish" | "skip",
  "kind": one of the kind names, or "" if skip,
  "headline": SHORT label in {_lang(language)}, 1-3 words + period,
  "body": 2-4 SHORT sentences in {_lang(language)} — the actual insight.
  "evidence_ids": list of evidence ids used (verbatim ints from the list above),
  "confidence": number 0-1
}}

Available kinds:
{kinds_listing}

Rules:
- If decision == "skip", body/headline/kind/evidence_ids can be "".
- NEVER mention "evidence", "patterns", "memory", "ARENA's model".
- NEVER start the body with "ARENA" — the headline already does that.
- No emojis, no lists, no quotes around the body.
"""
    data = _ask_json(prompt, language, temperature=0.6, max_tokens=500, check_ru=True)
    if not data or data.get("decision") != "publish":
        return None
    kind = str(data.get("kind") or "").strip().upper()
    if kind not in DISCOVERY_KINDS:
        return None
    headline = _no_ru(str(data.get("headline") or "").strip())[:80]
    body = _no_ru(str(data.get("body") or "").strip())[:600]
    if not headline or not body:
        return None
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    if conf < 0.55:
        return None
    evidence_ids = []
    for x in (data.get("evidence_ids") or [])[:5]:
        try:
            evidence_ids.append(int(x))
        except (TypeError, ValueError):
            pass
    return {
        "kind": kind,
        "headline": headline,
        "body": body,
        "evidence_ids": evidence_ids,
        "confidence": max(0.0, min(1.0, conf)),
    }