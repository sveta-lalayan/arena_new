"""
Игровые данные ARENA: языки, уровни CEFR, персонажи, 10 критериев оценки,
переводы сцен боя на 6 языков, бейджи.
"""

LANGUAGES = {
    "english": {"flag": "🇬🇧", "name": "English"},
    "german": {"flag": "🇩🇪", "name": "Deutsch"},
    "italian": {"flag": "🇮🇹", "name": "Italiano"},
    "spanish": {"flag": "🇪🇸", "name": "Español"},
    "korean": {"flag": "🇰🇷", "name": "한국어"},
    "chinese": {"flag": "🇨🇳", "name": "中文"},
}

# Название языка для промптов GPT (всегда по-английски)
LANG_PROMPT_NAME = {
    "english": "English",
    "german": "German",
    "italian": "Italian",
    "spanish": "Spanish",
    "korean": "Korean",
    "chinese": "Simplified Chinese",
}

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Языконезависимые правила сложности речи персонажей и Арены (для промптов).
LEVEL_PROMPTS = {
    "A1": "Use ONLY very short, simple sentences (max ~8 words), the most common ~500 words, "
          "present tense only. One idea per message. Speak slowly and clearly.",
    "A2": "Use short, simple sentences, basic everyday vocabulary (~1000 words), simple past and "
          "future, basic connectors (and, but, because).",
    "B1": "Use medium-complexity sentences, everyday and some abstract vocabulary (~2000 words), "
          "a variety of common tenses, connectors like 'however', 'although', 'therefore'.",
    "B2": "Use complex sentences, all common tenses, modal verbs, passive voice, intermediate "
          "idioms and a wide vocabulary (~4000 words).",
    "C1": "Use sophisticated structures, precise and academic vocabulary, idioms, abstract "
          "ideas, nuanced argumentation.",
    "C2": "Use native-like, richly nuanced language, advanced idioms and stylistic devices, "
          "subtle rhetoric.",
}
# Старое имя оставлено для совместимости с другими модулями.
LEVEL_DESCRIPTIONS = LEVEL_PROMPTS

GUIDE_PERSONALITY = {
    "name": "Alex",
    "desc": "Твой дружелюбный проводник в мире Arena 2.0. Помогу освоиться и подобрать идеального собеседника!",
}

ROLE_STYLE = {
    "ceo": "спрашивай про стратегию, риски, деньги, лидерство; требуй цифры и структуру",
    "journalist": "задавай провокационные вопросы, ищи противоречия, проси доказательства",
    "professor": "проси объяснять подробнее, исправляй неточности, требуй тезис-аргумент-вывод",
    "hr_manager": "задавай поведенческие вопросы, проси примеры из опыта по STAR-методу",
    "philosopher": "задавай глубокие вопросы, отвечай вопросом на вопрос, уводи к глобальным смыслам",
    "devil_advocate": "всегда смотри на проблему с ДРУГОЙ стороны и спорь; находи слабые места в аргументах",
}

# Описание характера для GPT — по-английски, чтобы не провоцировать русский в ответах.
PERSONA_BRIEFS = {
    "ceo": "Richard, a blunt CEO who built three international companies. Hates fluff and long "
           "intros, demands numbers, structure and a clear benefit. Short, dry sentences. Never gushes.",
    "journalist": "Kate, a sharp investigative journalist. Hunts for contradictions and weak spots, "
                  "asks uncomfortable follow-ups, never accepts the first answer, loves a surprising honest angle.",
    "professor": "Professor Adams, a strict academic. Demands thesis -> argument -> conclusion, "
                 "corrects imprecision, keeps asking to elaborate.",
    "hr_manager": "Sarah, an HR director. Turns any topic into behavioural questions and wants "
                  "concrete personal examples (STAR: situation, task, action, result).",
    "philosopher": "Leo, a sage. Rarely answers directly, replies with deeper 'why' questions, "
                   "dislikes yes/no answers, pulls the talk toward meaning.",
    "devil_advocate": "Victor, a devil's advocate. Always argues the opposite side, even when he "
                      "secretly agrees. Probes weak points, respects people who hold their ground.",
}

PERSONALITIES = {
    "ceo": {
        "name": "👑 Richard the CEO",
        "full_name": "Richard — CEO",
        "short_name": "Richard",
        "role": "CEO",
        "desc": "Построил три международные компании. Ненавидит воду, длинные "
                "вступления и отсутствие цифр. Любит факты, уверенность и структуру.",
        "style": "Любит короткие ответы. Не любит эмоции. Лучше работает логика.",
        "phrase": "Convince me.",
        "photo": "assets/characters/ceo_richard.jpg",
        "psychology": "👑 Ричард оценивает три вещи: ФАКТЫ, ВЫГОДУ и СТРУКТУРУ.",
    },
    "journalist": {
        "name": "📰 Kate the Journalist",
        "full_name": "Kate — Journalist",
        "short_name": "Kate",
        "role": "JOURNALIST",
        "desc": "Ищет слабые места. Любит задавать неудобные вопросы. Никогда не "
                "принимает ответ сразу.",
        "style": "Любит неожиданные ответы. Не любит общие слова.",
        "phrase": "Are you sure?",
        "photo": "assets/characters/journalist_kate.jpg",
        "psychology": "📰 Кейт оценивает три вещи: НЕОЖИДАННОСТЬ, ПРОВОКАЦИЮ и ЧЕСТНОСТЬ.",
    },
    "professor": {
        "name": "🎓 Professor Adams",
        "full_name": "Professor Adams",
        "short_name": "Professor Adams",
        "role": "PROFESSOR",
        "desc": "Академик. Требует точности и доказательств. Исправляет ошибки.",
        "style": "Любит структуру и аргументы. Не любит неточности.",
        "phrase": "Can you elaborate?",
        "photo": "assets/characters/professor_adams.jpg",
        "psychology": "🎓 Профессор оценивает: ТЕЗИС, АРГУМЕНТ, ВЫВОД.",
    },
    "hr_manager": {
        "name": "💼 Sarah the HR Director",
        "full_name": "Sarah — HR Director",
        "short_name": "Sarah",
        "role": "HR DIRECTOR",
        "desc": "Проводит собеседования. Любую тему переводит в вопросы о работе, "
                "опыте, навыках.",
        "style": "Любит реальные примеры. Истории. STAR-метод.",
        "phrase": "Tell me about a time when...",
        "photo": "assets/characters/hr_sarah.jpg",
        "psychology": "💼 Сара оценивает: КОНКРЕТИКУ, ОТВЕТСТВЕННОСТЬ, РЕЗУЛЬТАТ.",
    },
    "philosopher": {
        "name": "🧙 Leo the Sage",
        "full_name": "Leo — The Sage",
        "short_name": "Leo",
        "role": "THE SAGE",
        "desc": "Почти никогда не говорит прямо. Отвечает вопросом. Заставляет думать.",
        "style": "Любит философию. Не любит ответы да/нет.",
        "phrase": "What makes a good life?",
        "photo": "assets/characters/philosopher_leo.jpg",
        "psychology": "🧙 Лео оценивает: ГЛУБИНУ, ЧЕСТНОСТЬ, СВЯЗЬ С ЖИЗНЬЮ.",
    },
    "devil_advocate": {
        "name": "😈 Victor the Advocate",
        "full_name": "Victor — Devil's Advocate",
        "short_name": "Victor",
        "role": "DEVIL'S ADVOCATE",
        "desc": "Всегда спорит. Даже если согласен. Учит защищать свою позицию.",
        "style": "Любит провокации и споры. Не любит уступчивость.",
        "phrase": "What if you're wrong?",
        "photo": "assets/characters/devil_victor.jpg",
        "psychology": "😈 Виктор оценивает: УВЕРЕННОСТЬ, КОНТРАРГУМЕНТЫ, СИЛУ ВОЛИ.",
    },
}

# ========== 10 КРИТЕРИЕВ ОЦЕНКИ ==========
# 4 языковых + 6 коммуникационных = 10. По ним считается победа в бою
# и рисуется шкала в «Моей арене».

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

ALL_CRITERIA = LANGUAGE_CRITERIA + COMMUNICATION_SKILLS  # ровно 10

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

# Какой персонаж прокачивает какой communication-скилл
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

PERSONA_TIP_FALLBACK = {
    "ceo": "Start with a number or a concrete result — no intro.",
    "journalist": "Give her something unexpected in your first sentence.",
    "professor": "Structure: thesis -> argument -> conclusion.",
    "hr_manager": "Give one concrete example from your own experience.",
    "philosopher": "Explain WHY you think so before you answer.",
    "devil_advocate": "Prepare a counter-argument in advance.",
}

ARENA_RANKS = {
    "clarity": {"rank": "I", "name": "SPEAK", "goal": "state your opinion", "tools": "words"},
    "argumentation": {"rank": "II", "name": "BUILD", "goal": "explain your position",
                      "tools": "basic phrases + connectors"},
    "evidence": {"rank": "III", "name": "DEFEND", "goal": "answer objections",
                 "tools": "collocations + argument structures"},
    "persuasion": {"rank": "IV", "name": "PERSUADE", "goal": "change their mind",
                   "tools": "persuasive language + natural expressions"},
    "adaptability": {"rank": "V", "name": "ADAPT", "goal": "respond when your first approach fails",
                     "tools": "nuanced language + reframing"},
    "control": {"rank": "VI", "name": "CONTROL", "goal": "lead the conversation toward an outcome",
                "tools": "register + rhetoric + precision"},
}

ARENA_BEHAVIOURS = {
    "analyst": "🧠 The Analyst — много объясняет, любит логику, может быть сухим.",
    "challenger": "🔥 The Challenger — сразу спорит, уверенный, иногда не слушает.",
    "explorer": "🌊 The Explorer — легко поддерживает разговор, задаёт вопросы, но может не иметь чёткой позиции.",
    "precise": "🎯 The Precise One — краткий и точный, но недостаточно развивает мысль.",
    "defender": "🛡️ The Defender — хорошо защищается, но плохо начинает собственную стратегию.",
}
# То же для GPT (по-английски)
BEHAVIOUR_BRIEFS = {
    "analyst": "explains a lot, loves logic, can be dry",
    "challenger": "argues immediately, confident, sometimes doesn't listen",
    "explorer": "keeps conversation flowing and asks questions but may lack a firm position",
    "precise": "brief and exact but doesn't develop the thought enough",
    "defender": "defends well but is weak at opening with their own strategy",
}

# ========== СЦЕНЫ АРЕНЫ НА 6 ЯЗЫКАХ ==========
# Всё, что «говорят» Арена и персонажи в сцене боя, — на языке пользователя.
# Порядок переводов: en, de, it, es, ko, zh.
_LANG_ORDER = ["english", "german", "italian", "spanish", "korean", "chinese"]

_T = {
    "listening": ("ARENA IS LISTENING.", "ARENA HÖRT ZU.", "ARENA TI ASCOLTA.", "ARENA ESTÁ ESCUCHANDO.",
                  "ARENA가 듣고 있어.", "ARENA 正在倾听。"),
    "your_move": ("Your move.", "Du bist dran.", "Tocca a te.", "Tu turno.", "네 차례야.", "轮到你了。"),
    "listen_hint": ("what I do · what I love · what I think · anything",
                    "was ich tue · was ich liebe · was ich denke · irgendwas",
                    "cosa faccio · cosa amo · cosa penso · qualsiasi cosa",
                    "lo que hago · lo que amo · lo que pienso · lo que sea",
                    "내가 하는 일 · 내가 좋아하는 것 · 내 생각 · 뭐든지",
                    "我做什么 · 我爱什么 · 我怎么想 · 随便什么"),
    "heard_enough": ("I'VE HEARD ENOUGH.", "ICH HABE GENUG GEHÖRT.", "HO SENTITO ABBASTANZA.",
                     "YA HE OÍDO SUFICIENTE.", "충분히 들었어.", "我听够了。"),
    "enter_battle": ("ENTER BATTLE", "KAMPF BEGINNEN", "INIZIA LA SFIDA", "ENTRAR EN BATALLA",
                     "전투 시작", "开始对战"),
    "thinking": ("ARENA is thinking…", "ARENA denkt nach …", "ARENA sta pensando…", "ARENA está pensando…",
                 "ARENA가 생각 중이야…", "ARENA 正在思考……"),
    "go_on": ("Go on.", "Weiter.", "Continua.", "Sigue.", "계속해.", "继续。"),
    "arena_returns": ("The Arena is watching again.", "Die Arena beobachtet dich wieder.",
                      "L'Arena ti osserva di nuovo.", "La Arena vuelve a observarte.",
                      "아레나가 다시 지켜보고 있어.", "竞技场再次注视着你。"),
    "battle_begins": ("THE BATTLE BEGINS!", "DER KAMPF BEGINNT!", "LA SFIDA INIZIA!", "¡COMIENZA LA BATALLA!",
                      "전투 시작!", "战斗开始！"),
    "mission": ("Mission", "Mission", "Missione", "Misión", "미션", "任务"),
    "how_to_win": ("How to win", "So gewinnst du", "Come vincere", "Cómo ganar", "이기는 방법", "获胜条件"),
    "weapons": ("Arsenal", "Arsenal", "Arsenale", "Arsenal", "무기", "武器"),
    "weapons_easy": ("Your weapons (words)", "Deine Waffen (Wörter)", "Le tue armi (parole)",
                     "Tus armas (palabras)", "네 무기(단어)", "你的武器（词语）"),
    "tip": ("Tip", "Tipp", "Consiglio", "Consejo", "팁", "提示"),
    "write_reply": ("Write your reply!", "Schreib deine Antwort!", "Scrivi la tua risposta!",
                    "¡Escribe tu respuesta!", "답장을 써 봐!", "写下你的回答！"),
    "time_limit": ("You have {n} min.", "Du hast {n} Min.", "Hai {n} min.", "Tienes {n} min.",
                   "{n}분 있어.", "你有 {n} 分钟。"),
    "persuaded": ("Persuaded", "Überzeugt", "Convinto", "Convencido", "설득도", "说服度"),
    "reply_or_stop": ("Your move — or /stop to finish.", "Du bist dran — oder /stop zum Beenden.",
                      "Tocca a te — oppure /stop per finire.", "Tu turno — o /stop para terminar.",
                      "네 차례야 — 끝내려면 /stop", "轮到你了——或用 /stop 结束。"),
    "time_up": ("Time's up.", "Die Zeit ist um.", "Tempo scaduto.", "Se acabó el tiempo.", "시간 끝.", "时间到。"),
    "early_win": ("You broke them early. Victory!", "Du hast ihn früh geknackt. Sieg!",
                  "L'hai convinto in anticipo. Vittoria!", "Lo convenciste antes de tiempo. ¡Victoria!",
                  "일찍 설득했어. 승리!", "你提前说服了对方。胜利！"),
    "judging": ("ARENA is judging…", "ARENA urteilt …", "ARENA sta giudicando…", "ARENA está juzgando…",
                "ARENA가 판단 중이야…", "ARENA 正在评判……"),
    "victory": ("VICTORY", "SIEG", "VITTORIA", "VICTORIA", "승리", "胜利"),
    "defeat": ("DEFEAT", "NIEDERLAGE", "SCONFITTA", "DERROTA", "패배", "失败"),
    "worked": ("What worked", "Was funktioniert hat", "Cosa ha funzionato", "Lo que funcionó",
               "잘한 점", "做得好的地方"),
    "why_won": ("Why you won", "Warum du gewonnen hast", "Perché hai vinto", "Por qué ganaste",
                "이긴 이유", "获胜原因"),
    "why_lost": ("Why you lost", "Warum du verloren hast", "Perché hai perso", "Por qué perdiste",
                 "진 이유", "失败原因"),
    "language_check": ("Language check", "Sprach-Check", "Controllo linguistico", "Revisión del idioma",
                       "언어 점검", "语言检查"),
    "steal": ("Steal from {name}", "Klau von {name}", "Ruba da {name}", "Róbale a {name}",
              "{name}에게서 훔칠 표현", "向{name}偷师"),
    "ft_start": ("Free talk with {name}. No timer, no grade. /stop to finish.",
                 "Freies Gespräch mit {name}. Kein Timer, keine Note. /stop zum Beenden.",
                 "Chiacchierata libera con {name}. Niente timer, niente voto. /stop per finire.",
                 "Charla libre con {name}. Sin temporizador ni nota. /stop para terminar.",
                 "{name}와 자유 대화. 타이머도 평가도 없어. 끝내려면 /stop",
                 "与{name}自由交谈。没有计时，没有评分。用 /stop 结束。"),
    "ft_done": ("Conversation over, {name}. ARENA remembers.", "Gespräch beendet, {name}. ARENA merkt sich alles.",
                "Conversazione finita, {name}. ARENA ricorda.", "Conversación terminada, {name}. ARENA lo recuerda.",
                "대화 끝, {name}. ARENA가 기억할게.", "对话结束，{name}。ARENA 会记住。"),
}

ARENA_UI_STRINGS = {
    lang: {key: values[i] for key, values in _T.items()}
    for i, lang in enumerate(_LANG_ORDER)
}

PERSONALITY_COMMENTS = {
    "ceo": "Ты пришла с фактами — уже плюс. В следующий раз добавь конкретные цифры.",
    "journalist": "Было интересно, но я всё ещё жду того самого неожиданного поворота.",
    "professor": "Мысль есть. В следующий раз выстрой её в цепочку: тезис → аргумент → вывод.",
    "hr_manager": "Хороший разговор. Добавь больше конкретных примеров из жизни — и будет отлично.",
    "philosopher": "Ты дал ответ. В следующий раз попробуй дать вопрос — это интереснее.",
    "devil_advocate": "Ты держался неплохо. Продолжай защищать позицию даже под давлением.",
}

BADGES = {
    "first_debate": {"name": "🏆 Первый бой", "description": "Завершил первый бой с персонажем"},
    "first_victory": {"name": "🥇 Первая победа", "description": "Выиграл свой первый бой"},
    "grammar_master": {"name": "📚 Грамматический мастер", "description": "Грамматика выше 90"},
    "wordsmith": {"name": "🗣️ Мастер слова", "description": "Словарный запас выше 90"},
    "marathoner": {"name": "🏃 Марафонец", "description": "10+ ответов за один бой"},
    "all_characters": {"name": "🎭 Коллекционер", "description": "Сыграл со всеми персонажами"},
    "high_scorer": {"name": "🔥 На вершине", "description": "Средний балл за бой выше 85"},
    "quest_master": {"name": "🎯 Охотник за квестами", "description": "Выполнил еженедельный квест"},
    "nemesis_slayer": {"name": "⚡ Победитель немезиды", "description": "Победил своего персонажа-немезиду"},
    "full_convince": {"name": "💯 Полное убеждение", "description": "Полностью переубедил персонажа за один бой"},
}

BEGINNER_LEVELS = {"A1", "A2"}

SKILL_LABELS_RU = {
    "clarity": "ясность речи",
    "argumentation": "аргументацию",
    "evidence": "доказательность",
    "persuasion": "убедительность",
    "adaptability": "гибкость в споре",
    "control": "контроль разговора",
}

DISCUSSION_RULES = {
    "A1": "Говори короткими фразами, но всегда добавляй ПОЧЕМУ ты так думаешь.",
    "A2": "К любому заявлению добавляй причину и один пример.",
    "B1": "Строй ответ по схеме: заявление → причина → пример.",
    "B2": "Не соглашайся сразу — сначала оспорь, потом уступай по чуть-чуть.",
    "C1": "Управляй разговором: переформулируй возражения, уступай выборочно.",
    "C2": "Держи инициативу и подстраивай регистр речи под собеседника.",
}

MISSION_FORMAT_BY_PERSONALITY = {
    "ceo": "a claim with a concrete benefit/number that the learner must defend",
    "journalist": "a provocative situation the learner must talk their way out of",
    "professor": "a case the learner must analyse as thesis -> argument -> conclusion",
    "hr_manager": "a practical case from experience (STAR style) the learner must unpack",
    "philosopher": "a deep question that needs a personal, non-trivial answer",
    "devil_advocate": "a provocative statement the learner must defend under pressure",
}

# --- Голосовая поддержка (OpenAI TTS) ---
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

LANG_TO_ISO = {
    "english": "en",
    "german": "de",
    "italian": "it",
    "spanish": "es",
    "korean": "ko",
    "chinese": "zh",
}