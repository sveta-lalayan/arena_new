"""
game_data.py — данные ARENA: языки, уровни, персонажи, критерии, бейджи,
шаблоны миссий, голоса, вспомогательные мапы, ARENA_SIGNALS, ARSENAL_STATUS.
"""

LANGUAGES = {
    "en": {"flag": "🇬🇧", "name": "English"},
    "ru": {"flag": "🇷🇺", "name": "Русский"},
    "de": {"flag": "🇩🇪", "name": "Deutsch"},
    "es": {"flag": "🇪🇸", "name": "Español"},
    "it": {"flag": "🇮🇹", "name": "Italiano"},
    "ko": {"flag": "🇰🇷", "name": "한국어"},
    "zh": {"flag": "🇨🇳", "name": "中文"},
}

LANG_PROMPT_NAME = {
    "en": "English",
    "ru": "Russian",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "ko": "Korean",
    "zh": "Simplified Chinese",
}

LANG_TO_ISO = {"en": "en", "ru": "ru", "de": "de", "es": "es",
               "it": "it", "ko": "ko", "zh": "zh"}


LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LEVEL_PROMPTS = {
    "A1": "Use ONLY very short, simple sentences (max ~8 words), the most common ~500 words, "
          "present tense only. One idea per message.",
    "A2": "Use short, simple sentences, basic everyday vocabulary (~1000 words), simple past and "
          "future, basic connectors (and, but, because).",
    "B1": "Use medium-complexity sentences, everyday and some abstract vocabulary (~2000 words), "
          "a variety of common tenses, connectors like 'however', 'although', 'therefore'.",
    "B2": "Use complex sentences, all common tenses, modal verbs, passive voice, intermediate "
          "idioms and a wide vocabulary (~4000 words) — but keep it sounding SPOKEN.",
    "C1": "Use sophisticated structures, precise and wide vocabulary, idioms, abstract ideas, "
          "nuanced argumentation — but this is still spoken, natural speech, not an essay.",
    "C2": "Use native-like, richly nuanced language, advanced idioms and stylistic devices, subtle "
          "rhetoric — but stay natural and conversational.",
}
LEVEL_DESCRIPTIONS = LEVEL_PROMPTS
BEGINNER_LEVELS = {"A1", "A2"}


ROLE_STYLE = {
    "ceo": "ask about strategy, risk, money, leadership; demand numbers and structure",
    "journalist": "ask provocative questions, hunt for contradictions, demand evidence",
    "professor": "ask to elaborate, correct imprecision, require thesis → argument → conclusion",
    "hr_manager": "ask behavioural questions, ask for real examples (STAR method)",
    "philosopher": "ask deep questions, answer questions with questions, pull toward meaning",
    "devil_advocate": "always look at the opposite side and argue, find weak spots in arguments",
}

PERSONA_BRIEFS = {
    "ceo": "Richard, a blunt CEO who built three international companies. Hates fluff and long "
           "intros, demands numbers, structure and a clear benefit. Short, dry sentences.",
    "journalist": "Kate, a sharp investigative journalist. Hunts for contradictions and weak spots, "
                  "asks uncomfortable follow-ups, never accepts the first answer.",
    "professor": "Professor Adams, a strict academic. Demands thesis → argument → conclusion, "
                 "corrects imprecision, keeps asking to elaborate.",
    "hr_manager": "Sarah, an HR director. Turns any topic into behavioural questions and wants "
                  "concrete personal examples (STAR: situation, task, action, result).",
    "philosopher": "Leo, a sage. Rarely answers directly, replies with deeper 'why' questions, "
                   "dislikes yes/no answers, pulls the talk toward meaning.",
    "devil_advocate": "Victor, a devil's advocate. Always argues the opposite side, even when he "
                      "secretly agrees. Probes weak points, respects people who hold their ground.",
}

SPEECH_STYLE = {
    "ceo": "Clipped, transactional sentences, rarely more than 8-10 words. Gets visibly impatient "
           "with small talk and redirects it toward outcomes, time, or money within a line or two.",
    "journalist": "Turns statements into questions back at the person. Repeats a suspicious word "
                  "before pressing on it. Drops in a quick 'Really?' or 'Says who?'.",
    "professor": "Formal, precise vocabulary, occasional dry academic humor. Asks for definitions "
                 "of casual words. Mild condescension.",
    "hr_manager": "Warm surface tone but structured underneath. Reflexively asks for a concrete "
                  "example of anything mentioned.",
    "philosopher": "Answers questions with questions more often than with answers. Slows the pace "
                   "down, sometimes trails off mid-thought.",
    "devil_advocate": "Reflexively takes the contrarian position on nearly anything, including "
                      "trivial opinions — playful, not hostile, but relentless.",
}

PERSONALITIES = {
    "ceo": {
        "name": "👑 Richard the CEO",
        "full_name": "Richard — CEO",
        "short_name": "Richard",
        "role": "CEO",
        "desc": "Built three international companies. Hates fluff, long intros, no numbers.",
        "style": "Short answers, no emotion, pure logic.",
        "phrase": "Convince me.",
        "photo": "assets/characters/ceo_richard.jpg",
        "psychology": "👑 Richard weighs three things: FACTS, BENEFIT, STRUCTURE.",
    },
    "journalist": {
        "name": "📰 Kate the Journalist",
        "full_name": "Kate — Journalist",
        "short_name": "Kate",
        "role": "JOURNALIST",
        "desc": "Looks for weak spots. Asks uncomfortable questions. Never accepts the first answer.",
        "style": "Loves surprising answers, hates vague words.",
        "phrase": "Are you sure?",
        "photo": "assets/characters/journalist_kate.jpg",
        "psychology": "📰 Kate weighs three things: SURPRISE, PROVOCATION, HONESTY.",
    },
    "professor": {
        "name": "🎓 Professor Adams",
        "full_name": "Professor Adams",
        "short_name": "Professor Adams",
        "role": "PROFESSOR",
        "desc": "Academic. Demands precision and evidence. Corrects imprecision.",
        "style": "Structure and arguments. Hates inexactness.",
        "phrase": "Can you elaborate?",
        "photo": "assets/characters/professor_adams.jpg",
        "psychology": "🎓 The Professor weighs: THESIS, ARGUMENT, CONCLUSION.",
    },
    "hr_manager": {
        "name": "💼 Sarah the HR Director",
        "full_name": "Sarah — HR Director",
        "short_name": "Sarah",
        "role": "HR DIRECTOR",
        "desc": "Runs interviews. Turns any topic into questions about work, experience, skills.",
        "style": "Real examples. Stories. STAR method.",
        "phrase": "Tell me about a time when…",
        "photo": "assets/characters/hr_sarah.jpg",
        "psychology": "💼 Sarah weighs: SPECIFICS, OWNERSHIP, RESULT.",
    },
    "philosopher": {
        "name": "🧙 Leo the Sage",
        "full_name": "Leo — The Sage",
        "short_name": "Leo",
        "role": "THE SAGE",
        "desc": "Almost never answers directly. Answers with a question. Makes you think.",
        "style": "Philosophy. No yes/no answers.",
        "phrase": "What makes a good life?",
        "photo": "assets/characters/philosopher_leo.jpg",
        "psychology": "🧙 Leo weighs: DEPTH, HONESTY, LINK TO LIFE.",
    },
    "devil_advocate": {
        "name": "😈 Victor the Advocate",
        "full_name": "Victor — Devil's Advocate",
        "short_name": "Victor",
        "role": "DEVIL'S ADVOCATE",
        "desc": "Always argues. Even when he agrees. Teaches you to defend your position.",
        "style": "Provocation and arguments. Hates easy agreement.",
        "phrase": "What if you're wrong?",
        "photo": "assets/characters/devil_victor.jpg",
        "psychology": "😈 Victor weighs: CONFIDENCE, COUNTER-ARGUMENTS, WILL.",
    },
}

import re as _re
_DUP_EMOJI_PREFIX_RE = _re.compile(r"^(\S+)(\s+\1)+(\s+)")


def _dedupe_leading_emoji(text: str) -> str:
    m = _DUP_EMOJI_PREFIX_RE.match(text or "")
    if m:
        return m.group(1) + m.group(3) + text[m.end():]
    return text


for _p in PERSONALITIES.values():
    for _field in ("name", "full_name"):
        if _p.get(_field):
            _p[_field] = _dedupe_leading_emoji(_p[_field])
del _p, _field


LANGUAGE_CRITERIA = ["grammar", "vocabulary", "fluency", "naturalness"]

COMMUNICATION_SKILLS = [
    "clarity", "argumentation", "adaptability", "persuasion", "evidence", "control",
]
HIDDEN_SKILLS = ["resilience"]

ALL_CRITERIA = LANGUAGE_CRITERIA + COMMUNICATION_SKILLS


# ============================================================
# ARSENAL: 8 фиксированных приёмов
# ============================================================

ARSENAL_TOOLS = [
    {"key": "premise_flip", "emoji": "⚔️"},
    {"key": "clarifying_question", "emoji": "🎯"},
    {"key": "emotional_anchor", "emoji": "🛡️"},
    {"key": "fact_check", "emoji": "🔍"},
    {"key": "counterexample", "emoji": "🪤"},
    {"key": "steelman", "emoji": "🗣️"},
    {"key": "short_thesis", "emoji": "⚡"},
    {"key": "reframe", "emoji": "♟️"},
]
ARSENAL_TOOL_KEYS = [t["key"] for t in ARSENAL_TOOLS]
ARSENAL_TOOL_EMOJI = {t["key"]: t["emoji"] for t in ARSENAL_TOOLS}

ARSENAL_TOOL_DEFS = {
    "premise_flip": "Challenging the underlying assumption a claim rests on, instead of arguing "
                    "on the opponent's terms (e.g. 'why does it have to work that way at all?').",
    "clarifying_question": "Asking a precise question that exposes vagueness and forces the other "
                            "side to commit to specifics before the exchange continues.",
    "emotional_anchor": "Staying visibly calm and naming the emotional weight of the moment instead "
                        "of getting swept up in it or ignoring it.",
    "fact_check": "Explicitly questioning or checking a factual claim instead of accepting it at "
                  "face value (asking for a source, a number, evidence).",
    "counterexample": "Using one concrete counterexample that breaks the opponent's generalization.",
    "steelman": "Restating the opponent's position in its strongest, most charitable form before "
                "countering it.",
    "short_thesis": "Compressing the position into one short, decisive line instead of over-explaining.",
    "reframe": "Changing the criteria the whole argument is judged by, shifting the ground to "
               "terms that favor the learner's position.",
}


# ============================================================
# ARSENAL STATUS LEVELS — жизненный цикл приёма
# ============================================================
ARSENAL_STATUS_ORDER = ["discovered", "practising", "acquired", "strong", "mastered"]

ARSENAL_STATUS_EMOJI = {
    "discovered": "🔍",
    "practising": "🎯",
    "acquired": "✅",
    "strong": "💪",
    "mastered": "🏆",
}

ARSENAL_STATUS_THRESHOLDS = {
    "discovered": 1,
    "practising": 2,
    "acquired": 4,
    "strong": 7,
    "mastered": 12,
}


def arsenal_status_for_count(uses: int) -> str:
    """Статус приёма по числу успешных применений (или появлений) в боях."""
    status = "discovered"
    for key in ARSENAL_STATUS_ORDER:
        if uses >= ARSENAL_STATUS_THRESHOLDS[key]:
            status = key
    return status


# ============================================================
# ARENA SIGNALS
# ============================================================
ARENA_SIGNALS = {
    "explainer": {"kind": "pattern", "category": "clarity",
                  "brief": "Rarely leaves an idea unexplained."},
    "reframer": {"kind": "strength", "category": "argumentation",
                 "brief": "When challenged, changes the angle instead of abandoning the position."},
    "pushback_response": {"kind": "growth", "category": "adaptability",
                          "brief": "Explains before changing strategy when disagreed with."},
    "closer": {"kind": "strength", "category": "control",
               "brief": "Knows how to finish the point once the direction is clear."},
    "precision_under_pressure": {"kind": "strength", "category": "clarity",
                                 "brief": "Becomes more precise when the stakes rise."},
    "retreats_from_frames": {"kind": "growth", "category": "adaptability",
                             "brief": "Loses momentum when the other person refuses the initial frame."},
    "evidence_first": {"kind": "strength", "category": "evidence",
                       "brief": "Reaches for a concrete fact before arguing."},
    "story_driven": {"kind": "strength", "category": "fluency",
                     "brief": "Moves the argument forward through examples and stories."},
    "hedges_too_early": {"kind": "growth", "category": "persuasion",
                         "brief": "Softens the claim before giving it a chance to land."},
    "controls_direction": {"kind": "strength", "category": "control",
                           "brief": "Steers the conversation toward the point they want to make."},
}


# ============================================================
# ОБЩИЕ МАПЫ
# ============================================================

CRITERIA_LABELS_RU = {
    "grammar": "Грамматика", "vocabulary": "Словарный запас",
    "fluency": "Беглость", "naturalness": "Естественность",
    "clarity": "Ясность", "argumentation": "Аргументация",
    "adaptability": "Гибкость", "persuasion": "Убедительность",
    "evidence": "Доказательность", "control": "Контроль разговора",
}

SKILL_TO_PERSONALITY = {
    "clarity": "journalist",
    "argumentation": "devil_advocate",
    "adaptability": "hr_manager",
    "persuasion": "ceo",
    "evidence": "professor",
    "control": "philosopher",
}
PERSONALITY_TO_SKILL = {person: skill for skill, person in SKILL_TO_PERSONALITY.items()}
SKILL_TO_PERSONALITY_REVERSE = SKILL_TO_PERSONALITY


ARENA_RANKS = {
    "clarity": {"rank": "I", "name": "SPEAK", "goal": "state your opinion", "tools": "words"},
    "argumentation": {"rank": "II", "name": "BUILD", "goal": "explain your position",
                      "tools": "phrases + connectors"},
    "evidence": {"rank": "III", "name": "DEFEND", "goal": "answer objections",
                 "tools": "collocations + argument structures"},
    "persuasion": {"rank": "IV", "name": "PERSUADE", "goal": "change their mind",
                   "tools": "persuasive language + natural expressions"},
    "adaptability": {"rank": "V", "name": "ADAPT", "goal": "respond when your first approach fails",
                     "tools": "nuanced language + reframing"},
    "control": {"rank": "VI", "name": "CONTROL",
                "goal": "lead the conversation toward an outcome",
                "tools": "register + rhetoric + precision"},
}

ARENA_BEHAVIOURS = {
    "analyst": "🧠 The Analyst — explains a lot, loves logic, can be dry.",
    "challenger": "🔥 The Challenger — argues immediately, confident, sometimes doesn't listen.",
    "explorer": "🌊 The Explorer — keeps conversation flowing, asks questions, may lack a firm position.",
    "precise": "🎯 The Precise One — brief and exact, but doesn't develop the thought enough.",
    "defender": "🛡️ The Defender — defends well, weak at opening with their own strategy.",
}

BEHAVIOUR_BRIEFS = {
    "analyst": "explains a lot, loves logic, can be dry",
    "challenger": "argues immediately, confident, sometimes doesn't listen",
    "explorer": "keeps conversation flowing and asks questions but may lack a firm position",
    "precise": "brief and exact but doesn't develop the thought enough",
    "defender": "defends well but is weak at opening with their own strategy",
}


PERSONA_TIP_FALLBACK = {
    "ceo": "Start with a number or a concrete result — no intro.",
    "journalist": "Give her something unexpected in your first sentence.",
    "professor": "Structure: thesis → argument → conclusion.",
    "hr_manager": "Give one concrete example from your own experience.",
    "philosopher": "Explain WHY you think so before you answer.",
    "devil_advocate": "Prepare a counter-argument in advance.",
}

MISSION_FORMAT_BY_PERSONALITY = {
    "ceo": "a claim with a concrete benefit/number that the learner must defend",
    "journalist": "a provocative situation the learner must talk their way out of",
    "professor": "a case the learner must analyse as thesis → argument → conclusion",
    "hr_manager": "a practical case from experience (STAR style) the learner must unpack",
    "philosopher": "a deep question that needs a personal, non-trivial answer",
    "devil_advocate": "a provocative statement the learner must defend under pressure",
}


BADGES = {
    "first_debate": {"name": "🏆 First battle", "description": "Completed your first battle"},
    "first_victory": {"name": "🥇 First victory", "description": "Won your first battle"},
    "grammar_master": {"name": "📚 Grammar Master", "description": "Grammar above 90"},
    "wordsmith": {"name": "🗣️ Wordsmith", "description": "Vocabulary above 90"},
    "marathoner": {"name": "🏃 Marathoner", "description": "10+ turns in a single battle"},
    "all_characters": {"name": "🎭 Collector", "description": "Met every character"},
    "high_scorer": {"name": "🔥 Top of the Arena", "description": "Average battle score above 85"},
    "nemesis_slayer": {"name": "⚡ Nemesis Slayer", "description": "Defeated your nemesis"},
    "full_convince": {"name": "💯 Full Conviction", "description": "Fully convinced a character in one battle"},
}


ARENA_UI_STRINGS = {
    "en": {"heard_enough": "I'VE HEARD ENOUGH.", "enter_battle": "⚔️ ENTER BATTLE →"},
    "ru": {"heard_enough": "Я УСЛЫШАЛА ДОСТАТОЧНО.", "enter_battle": "⚔️ ВОЙТИ В БОЙ →"},
}


VOICE_BY_PERSONALITY = {
    "ceo": "onyx", "journalist": "nova", "professor": "echo",
    "hr_manager": "shimmer", "philosopher": "fable",
    "devil_advocate": "alloy", "_temple": "onyx",
}
TEMPLE_VOICE = "onyx"


DISCUSSION_RULES = {
    "A1": "Speak in short sentences, but always add WHY you think so.",
    "A2": "Add a reason and one example to every statement.",
    "B1": "Structure your reply: statement → reason → example.",
    "B2": "Don't agree immediately — challenge first, then concede a little.",
    "C1": "Drive the conversation: reframe objections, concede selectively.",
    "C2": "Hold the initiative and adjust your register to your opponent.",
}


NEMESIS_MAP = {
    "analyst": "philosopher", "challenger": "philosopher",
    "explorer": "devil_advocate", "precise": "hr_manager", "defender": "ceo",
}


SKILL_LABELS_RU = {
    "clarity": "ясность речи", "argumentation": "аргументацию",
    "evidence": "доказательность", "persuasion": "убедительность",
    "adaptability": "гибкость в споре", "control": "контроль разговора",
}

SKILL_LABELS_EN = {
    "clarity": "clarity", "argumentation": "argumentation",
    "evidence": "evidence", "persuasion": "persuasion",
    "adaptability": "adaptability", "control": "conversation control",
}

PERSONALITY_COMMENTS = {
    "ceo": "You came with facts — good. Next time add concrete numbers.",
    "journalist": "Interesting, but I'm still waiting for that unexpected angle.",
    "professor": "The idea is there. Next time: thesis → argument → conclusion.",
    "hr_manager": "Good talk. Add more concrete examples and it'll be excellent.",
    "philosopher": "You gave an answer. Next time try giving a question — more interesting.",
    "devil_advocate": "You held up. Keep defending your position under pressure.",
}