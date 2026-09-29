"""
game_data.py — данные ARENA: языки, уровни, персонажи, 10 критериев,
бейджи, шаблоны миссий, голоса, вспомогательные мапы.

Ключевое изменение по сравнению со старой версией:
  • Языки теперь адресуются короткими ISO-кодами (en/ru/de/es/it/ko/zh) —
    это те же значения, что в interface_language и learning_language в БД.
  • Внутренний ключ промпта (english/russian/...) доступен через
    config.ISO_TO_LANG_KEY. game_data использует ISO везде, где можно.
"""

# ============================================================
# ЯЗЫКИ
# ============================================================
# Основной словарь для UI: ISO-код → флаг + название на самом себе.
LANGUAGES = {
    "en": {"flag": "🇬🇧", "name": "English"},
    "ru": {"flag": "🇷🇺", "name": "Русский"},
    "de": {"flag": "🇩🇪", "name": "Deutsch"},
    "es": {"flag": "🇪🇸", "name": "Español"},
    "it": {"flag": "🇮🇹", "name": "Italiano"},
    "ko": {"flag": "🇰🇷", "name": "한국어"},
    "zh": {"flag": "🇨🇳", "name": "中文"},
}

# Название языка для промптов GPT — всегда по-английски.
LANG_PROMPT_NAME = {
    "en": "English",
    "ru": "Russian",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "ko": "Korean",
    "zh": "Simplified Chinese",
}

# ISO для подсказки Whisper (совпадает со стандартным ISO-639-1).
LANG_TO_ISO = {
    "en": "en",
    "ru": "ru",
    "de": "de",
    "es": "es",
    "it": "it",
    "ko": "ko",
    "zh": "zh",
}


# ============================================================
# УРОВНИ CEFR
# ============================================================

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LEVEL_PROMPTS = {
    "A1": "Use ONLY very short, simple sentences (max ~8 words), the most common ~500 words, "
          "present tense only. One idea per message.",
    "A2": "Use short, simple sentences, basic everyday vocabulary (~1000 words), simple past and "
          "future, basic connectors (and, but, because).",
    "B1": "Use medium-complexity sentences, everyday and some abstract vocabulary (~2000 words), "
          "a variety of common tenses, connectors like 'however', 'although', 'therefore'.",
    "B2": "Use complex sentences, all common tenses, modal verbs, passive voice, intermediate "
          "idioms and a wide vocabulary (~4000 words) — but keep it sounding SPOKEN, like a real "
          "person talking, not written prose.",
    "C1": "Use sophisticated structures, precise and wide vocabulary, idioms, abstract ideas, "
          "nuanced argumentation — but this is still spoken, natural speech, not an essay. Real "
          "people at this level use contractions, interrupt themselves, throw in casual asides.",
    "C2": "Use native-like, richly nuanced language, advanced idioms and stylistic devices, subtle "
          "rhetoric — but stay natural and conversational, the way a sharp native speaker actually "
          "talks, not a lecture or a written text. More vocabulary does NOT mean more formal.",
}
# Совместимость со старым именем.
LEVEL_DESCRIPTIONS = LEVEL_PROMPTS

BEGINNER_LEVELS = {"A1", "A2"}


# ============================================================
# ПЕРСОНАЖИ
# ============================================================
# character personality ≠ language difficulty.
# Персонаж остаётся собой на любом CEFR-уровне — меняется только сложность речи.

ROLE_STYLE = {
    "ceo": "ask about strategy, risk, money, leadership; demand numbers and structure",
    "journalist": "ask provocative questions, hunt for contradictions, demand evidence",
    "professor": "ask to elaborate, correct imprecision, require thesis → argument → conclusion",
    "hr_manager": "ask behavioural questions, ask for real examples (STAR method)",
    "philosopher": "ask deep questions, answer questions with questions, pull toward meaning",
    "devil_advocate": "always look at the opposite side and argue, find weak spots in arguments",
}

# Описание характера для GPT — по-английски, чтобы модель не уходила в другой язык.
PERSONA_BRIEFS = {
    "ceo": "Richard, a blunt CEO who built three international companies. Hates fluff and long "
           "intros, demands numbers, structure and a clear benefit. Short, dry sentences. Never gushes.",
    "journalist": "Kate, a sharp investigative journalist. Hunts for contradictions and weak spots, "
                  "asks uncomfortable follow-ups, never accepts the first answer, loves a surprising honest angle.",
    "professor": "Professor Adams, a strict academic. Demands thesis → argument → conclusion, "
                 "corrects imprecision, keeps asking to elaborate.",
    "hr_manager": "Sarah, an HR director. Turns any topic into behavioural questions and wants "
                  "concrete personal examples (STAR: situation, task, action, result).",
    "philosopher": "Leo, a sage. Rarely answers directly, replies with deeper 'why' questions, "
                   "dislikes yes/no answers, pulls the talk toward meaning.",
    "devil_advocate": "Victor, a devil's advocate. Always argues the opposite side, even when he "
                      "secretly agrees. Probes weak points, respects people who hold their ground.",
}

# Конкретные речевые привычки — без них персонаж звучит generic-дружелюбно даже
# в свободном разговоре, когда нет явного конфликта, за который можно зацепиться.
# Это должно работать в МЕЛОЧАХ (small talk), а не только в спорных моментах.
SPEECH_STYLE = {
    "ceo": "Clipped, transactional sentences, rarely more than 8-10 words. Often opens a reply with "
           "'Bottom line —' or 'So, the number is?' or 'Fine, but —'. Gets visibly impatient with small "
           "talk and redirects it toward outcomes, time, or money within a line or two, even when the "
           "topic is something casual like food or weekend plans. Almost never asks how someone feels.",
    "journalist": "Turns statements into questions back at the person ('You liked it? Or you're just "
                  "being polite?'). Repeats a suspicious word before pressing on it. Drops in a quick "
                  "'Really?' or 'Says who?' even about trivial claims. Curious about specifics — names, "
                  "numbers, exact moments — and calls out vagueness immediately.",
    "professor": "Formal, precise vocabulary, occasional dry academic humor. Asks for definitions of "
                 "casual words ('what do you mean by \"good\", exactly?'). Mild condescension — corrects "
                 "loose reasoning even in idle chat, then softens it with a small compliment.",
    "hr_manager": "Warm surface tone but structured underneath. Reflexively asks for a concrete example "
                  "of anything mentioned ('walk me through that', 'give me a specific moment'). Uses "
                  "workplace-adjacent framing even for unrelated topics (calls a hobby a 'strength', a "
                  "trip a 'growth experience').",
    "philosopher": "Answers questions with questions more often than with answers. Slows the pace down, "
                   "sometimes trails off mid-thought ('...though maybe that's not quite it'). Redirects "
                   "small talk toward meaning or purpose without being asked to.",
    "devil_advocate": "Reflexively takes the contrarian position on nearly anything, including trivial "
                      "opinions like favorite food or a movie — playful, not hostile, but relentless. "
                      "Often opens with 'I'd actually disagree' or 'See, that's exactly the problem' "
                      "even when he privately agrees.",
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

# Защита от задвоенного emoji-префикса в имени персонажа (например, если где-то
# в данных случайно оказалось "👑 👑 Richard the CEO" вместо "👑 Richard the CEO") —
# нормализуем один раз здесь, а не там, где имя выводится.
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


# ============================================================
# 10 КРИТЕРИЕВ ОЦЕНКИ
# ============================================================
# 4 языковых + 6 коммуникационных = 10.

LANGUAGE_CRITERIA = ["grammar", "vocabulary", "fluency", "naturalness"]

COMMUNICATION_SKILLS = [
    "clarity",
    "argumentation",
    "adaptability",
    "persuasion",
    "evidence",
    "control",
]
HIDDEN_SKILLS = ["resilience"]

ALL_CRITERIA = LANGUAGE_CRITERIA + COMMUNICATION_SKILLS


# ============================================================
# АРСЕНАЛ: фиксированный набор из 8 приёмов
# ============================================================
# Это не свободная генерация оружия — это закрытый список конкретных техник.
# Витрина (имя/описание/пример на языке интерфейса) живёт в locales/*.json → TOOLS.
# Здесь — только порядок, эмодзи и внутреннее (английское) определение для промпта
# классификации в ai.py: "какой из этих 8 приёмов реально продемонстрировал игрок".

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

# Только для промпта классификации (ai.py) — не показывается пользователю.
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


CRITERIA_LABELS_RU = {
    "grammar": "Грамматика",
    "vocabulary": "Словарный запас",
    "fluency": "Беглость",
    "naturalness": "Естественность",
    "clarity": "Ясность",
    "argumentation": "Аргументация",
    "adaptability": "Гибкость",
    "persuasion": "Убедительность",
    "evidence": "Доказательность",
    "control": "Контроль разговора",
}

# Какой персонаж прокачивает какой communication-скилл.
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


# ============================================================
# ARENA RANKS / BEHAVIOURS
# ============================================================

ARENA_RANKS = {
    "clarity": {"rank": "I", "name": "SPEAK",
                "goal": "state your opinion", "tools": "words"},
    "argumentation": {"rank": "II", "name": "BUILD",
                      "goal": "explain your position", "tools": "phrases + connectors"},
    "evidence": {"rank": "III", "name": "DEFEND",
                 "goal": "answer objections", "tools": "collocations + argument structures"},
    "persuasion": {"rank": "IV", "name": "PERSUADE",
                   "goal": "change their mind", "tools": "persuasive language + natural expressions"},
    "adaptability": {"rank": "V", "name": "ADAPT",
                     "goal": "respond when your first approach fails",
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


# ============================================================
# ПЕРСОНАЛЬНЫЕ ПОДСКАЗКИ
# ============================================================

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


# ============================================================
# БЕЙДЖИ
# ============================================================

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


# ============================================================
# UI-СТРОКИ
# ============================================================
# Всё, что видит пользователь как интерфейс, теперь живёт в locales/*.json.
# Здесь — только те строки, которые нужны AI-слою (названия фаз и т.п.).

ARENA_UI_STRINGS = {
    "en": {"heard_enough": "I'VE HEARD ENOUGH.", "enter_battle": "⚔️ ENTER BATTLE →"},
    "ru": {"heard_enough": "Я УСЛЫШАЛА ДОСТАТОЧНО.", "enter_battle": "⚔️ ВОЙТИ В БОЙ →"},
}


# ============================================================
# VOICE (TTS)
# ============================================================
# У каждого персонажа свой голос. Храм говорит своим.
VOICE_BY_PERSONALITY = {
    "ceo": "onyx",
    "journalist": "nova",
    "professor": "echo",
    "hr_manager": "shimmer",
    "philosopher": "fable",
    "devil_advocate": "alloy",
    "_temple": "onyx",
}
TEMPLE_VOICE = "onyx"


# ============================================================
# ДИСКУССИОННЫЕ ПРАВИЛА ПО УРОВНЮ
# ============================================================

DISCUSSION_RULES = {
    "A1": "Speak in short sentences, but always add WHY you think so.",
    "A2": "Add a reason and one example to every statement.",
    "B1": "Structure your reply: statement → reason → example.",
    "B2": "Don't agree immediately — challenge first, then concede a little.",
    "C1": "Drive the conversation: reframe objections, concede selectively.",
    "C2": "Hold the initiative and adjust your register to your opponent.",
}


# ============================================================
# НЕМЕЗИДА
# ============================================================

NEMESIS_MAP = {
    "analyst": "philosopher",
    "challenger": "philosopher",
    "explorer": "devil_advocate",
    "precise": "hr_manager",
    "defender": "ceo",
}

# ============================================================
# СОВМЕСТИМОСТЬ: словари, которые ждёт gamification.py
# ============================================================

# Русские названия коммуникационных скиллов — для внутренних подписей.
SKILL_LABELS_RU = {
    "clarity": "ясность речи",
    "argumentation": "аргументацию",
    "evidence": "доказательность",
    "persuasion": "убедительность",
    "adaptability": "гибкость в споре",
    "control": "контроль разговора",
}

# Английские названия — на будущее (gamification может использовать
# их для не-русского интерфейса, но пока он берёт только русские).
SKILL_LABELS_EN = {
    "clarity": "clarity",
    "argumentation": "argumentation",
    "evidence": "evidence",
    "persuasion": "persuasion",
    "adaptability": "adaptability",
    "control": "conversation control",
}

# Комментарии персонажей (используются в дебрифе для советов "в характере").
# Оставляем на английском — это не UI, а внутренний текст, который сейчас
# нигде активно не показывается.
PERSONALITY_COMMENTS = {
    "ceo": "You came with facts — good. Next time add concrete numbers.",
    "journalist": "Interesting, but I'm still waiting for that unexpected angle.",
    "professor": "The idea is there. Next time: thesis → argument → conclusion.",
    "hr_manager": "Good talk. Add more concrete examples and it'll be excellent.",
    "philosopher": "You gave an answer. Next time try giving a question — more interesting.",
    "devil_advocate": "You held up. Keep defending your position under pressure.",
}