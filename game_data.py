"""
Игровые данные: языки, уровни CEFR, персонажи, психология персонажей,
финальные комментарии, бейджи, 3 слоя анализа ARENA.
"""

LANGUAGES = {
    "english": {"flag": "🇬🇧", "name": "English"},
    "german": {"flag": "🇩🇪", "name": "Deutsch"},
    "italian": {"flag": "🇮🇹", "name": "Italiano"},
    "spanish": {"flag": "🇪🇸", "name": "Español"},
    "korean": {"flag": "🇰🇷", "name": "한국어"},
    "chinese": {"flag": "🇨🇳", "name": "中文"},
}

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LEVEL_DESCRIPTIONS = {
    "A1": "используй ТОЛЬКО простые предложения (Subject + Verb + Object), "
          "базовую лексику (до 500 слов), настоящие времена (Present Simple), "
          "говори медленно и четко",
    "A2": "используй простые предложения, базовые конструкции (Past Simple, "
          "Future Simple), лексика до 1000 слов, короткие связки (and, but, because)",
    "B1": "используй среднюю сложность предложений, разнообразные времена "
          "(Present Perfect, Past Continuous), лексика до 2000 слов, связки "
          "(however, although, therefore)",
    "B2": "используй сложные предложения, все времена, модальные глаголы, "
          "пассивный залог, лексика до 4000 слов, идиомы среднего уровня",
    "C1": "используй сложные грамматические конструкции, инверсию, сложные "
          "времена, академическую лексику, идиомы, абстрактные понятия",
    "C2": "используй академическую лексику, сложные синтаксические конструкции, "
          "нюансированные аргументы, продвинутые идиомы, стилистические приёмы",
}

GUIDE_PERSONALITY = {
    "name": "Alex",
    "desc": "Твой дружелюбный проводник в мире Arena 2.0. Помогу освоиться и подобрать идеального собеседника!",
}

# Стиль поведения персонажа в диалоге — используется в ai.py, чтобы персонаж
# не был "удобным собеседником", а вёл себя согласно своему характеру.
ROLE_STYLE = {
    "ceo": "спрашивай про стратегию, риски, деньги, лидерство; требуй цифры и структуру",
    "journalist": "задавай провокационные вопросы, создавай провокационные ситуации, ищи противоречия, проси доказательства",
    "professor": "проси объяснять подробнее, исправляй неточности, требуй тезис-аргумент-вывод",
    "hr_manager": "задавай поведенческие вопросы, проси примеры из опыта по STAR-методу",
    "philosopher": "задавай глубокие философские вопросы, отвечай вопросом на вопрос, уводи разговор в сторону глобальных смыслов",
    "devil_advocate": "всегда старайся посмотреть на проблему с ДРУГОЙ стороны и спорь, даже если внутренне согласен; находи слабые места в аргументах",
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
        "psychology": """👑 КАК ДУМАЕТ РИЧАРД?

Ричард не слушает эмоции.
Он оценивает три вещи:

✅ ФАКТЫ — есть ли у тебя цифры?
✅ ВЫГОДА — принесёт ли это деньги?
✅ СТРУКТУРА — чётко ли ты излагаешь?

Без этого твои слова — просто шум.""",
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
        "psychology": """📰 КАК ДУМАЕТ КЕЙТ?

Кейт ищет историю.
Она оценивает три вещи:

✅ НЕОЖИДАННОСТЬ — есть ли в твоих словах поворот?
✅ ПРОВОКАЦИЯ — можешь ли ты удивить?
✅ ЧЕСТНОСТЬ — говоришь ли ты правду?

Она ждёт сенсации. Не разочаруй её.""",
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
        "psychology": """🎓 КАК ДУМАЕТ ПРОФЕССОР АДАМС?

Профессор живёт в мире доказательств.
Он оценивает три вещи:

✅ ТЕЗИС — что ты утверждаешь?
✅ АРГУМЕНТ — чем ты это подтверждаешь?
✅ ВЫВОД — к чему ты пришёл?

Без цепочки «тезис → аргумент → вывод» ты просто говоришь.""",
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
        "psychology": """💼 КАК ДУМАЕТ САРА?

Сара проводит сотни собеседований.
Она оценивает три вещи:

✅ КОНКРЕТИКА — есть ли у тебя примеры?
✅ ОТВЕТСТВЕННОСТЬ — берёшь ли ты на себя?
✅ РЕЗУЛЬТАТ — что ты реально сделала?

Общие слова — красная карточка на собеседовании.""",
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
        "psychology": """🧙 КАК ДУМАЕТ ЛЕО?

Лео не ищет правильные ответы.
Он оценивает три вещи:

✅ ГЛУБИНА — копаешь ли ты вглубь?
✅ ЧЕСТНОСТЬ — говоришь ли ты то, что думаешь?
✅ СВЯЗЬ С ЖИЗНЬЮ — как это работает на практике?

Он не спрашивает «что». Он спрашивает «почему».""",
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
        "psychology": """😈 КАК ДУМАЕТ ВИКТОР?

Виктор проверяет на прочность.
Он оценивает три вещи:

✅ УВЕРЕННОСТЬ — дрожит ли твой голос?
✅ КОНТРАРГУМЕНТЫ — можешь ли ты защищаться?
✅ СИЛА ВОЛИ — сдашься ли ты под давлением?

Одно сомнение — и ты проиграла.""",
    },
}

# ========== 3 СЛОЯ АНАЛИЗА ARENA ==========

# Коммуникационные скиллы (6 видимых + 1 скрытый — resilience)
COMMUNICATION_SKILLS = [
    "clarity",
    "argumentation",
    "adaptability",
    "persuasion",
    "evidence",
    "control",
]
HIDDEN_SKILLS = ["resilience"]

# Какой персонаж лучше всего "прокачивает" слабый communication-скилл
SKILL_TO_PERSONALITY = {
    "clarity": "journalist",
    "argumentation": "devil_advocate",
    "adaptability": "hr_manager",
    "persuasion": "ceo",
    "evidence": "professor",
    "control": "philosopher",
}

# Обратная связка: какой скилл прокачивает каждый персонаж (для начисления
# skill-прогресса и подбора "следующего хранителя" в finish_arena).
PERSONALITY_TO_SKILL = {person: skill for skill, person in SKILL_TO_PERSONALITY.items()}

# Обратная связка от персонажа к слабому скиллу, для подбора следующего
# персонажа по слабейшему навыку игрока.
SKILL_TO_PERSONALITY_REVERSE = SKILL_TO_PERSONALITY

# Совет "как говорить с персонажем" на случай, если GPT недоступен (нет
# ключа Yandex или ошибка сети). Используется в ai.generate_persona_tip.
PERSONA_TIP_FALLBACK = {
    "ceo": "Начни сразу с цифры или конкретного результата — без вступлений.",
    "journalist": "Дай ей что-то неожиданное с первой фразы, иначе она перебьёт вопросом.",
    "professor": "Строй ответ по схеме: тезис → аргумент → вывод, не перескакивай.",
    "hr_manager": "Приведи один конкретный пример из своего опыта, а не общие слова.",
    "philosopher": "Не спеши с ответом — сначала объясни, ПОЧЕМУ ты так думаешь.",
    "devil_advocate": "Заранее приготовь контраргумент — он обязательно начнёт тебе возражать.",
}

# ARENA RANK / MASTERY — что человек умеет делать языком.
# Определяется по слабому communication-скиллу.
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

# ARENA BEHAVIOUR — стиль игрока
ARENA_BEHAVIOURS = {
    "analyst": "🧠 The Analyst — много объясняет, любит логику, может быть сухим.",
    "challenger": "🔥 The Challenger — сразу спорит, уверенный, иногда не слушает.",
    "explorer": "🌊 The Explorer — легко поддерживает разговор, задаёт вопросы, но может не иметь чёткой позиции.",
    "precise": "🎯 The Precise One — краткий и точный, но недостаточно развивает мысль.",
    "defender": "🛡️ The Defender — хорошо защищается, но плохо начинает собственную стратегию.",
}

# Фиксированные UI-строки карточки Храма
ARENA_UI_STRINGS = {
    "english": {"heard_enough": "I'VE HEARD ENOUGH.", "your_move": "YOUR MOVE.", "arsenal": "ARSENAL", "min": "MIN", "enter_battle": "ENTER BATTLE"},
    "german": {"heard_enough": "ICH HABE GENUG GEHÖRT.", "your_move": "DU BIST DRAN.", "arsenal": "ARSENAL", "min": "MIN", "enter_battle": "KAMPF BEGINNEN"},
    "italian": {"heard_enough": "HO SENTITO ABBASTANZA.", "your_move": "TOCCA A TE.", "arsenal": "ARSENALE", "min": "MIN", "enter_battle": "INIZIA LA SFIDA"},
    "spanish": {"heard_enough": "YA HE OÍDO SUFICIENTE.", "your_move": "TU TURNO.", "arsenal": "ARSENAL", "min": "MIN", "enter_battle": "ENTRAR EN BATALLA"},
    "korean": {"heard_enough": "충분히 들었어.", "your_move": "이제 네 차례야.", "arsenal": "무기", "min": "분", "enter_battle": "전투 시작"},
    "chinese": {"heard_enough": "我听够了。", "your_move": "轮到你了。", "arsenal": "武器", "min": "分钟", "enter_battle": "开始对战"},
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
    "first_debate": {"name": "🏆 Первый бой", "description": "Завершил первый раунд с персонажем"},
    "grammar_master": {"name": "📚 Грамматический мастер", "description": "Грамматика выше 90%"},
    "wordsmith": {"name": "🗣️ Мастер слова", "description": "Словарный запас выше 90%"},
    "marathoner": {"name": "🏃 Марафонец", "description": "10+ ответов за один раунд"},
    "all_characters": {"name": "🎭 Коллекционер", "description": "Сыграл со всеми персонажами"},
    "high_scorer": {"name": "🔥 На вершине", "description": "Средний балл за раунд выше 85"},
    "quest_master": {"name": "🎯 Охотник за квестами", "description": "Выполнил еженедельный квест"},
    "nemesis_slayer": {"name": "⚡ Победитель немезиды", "description": "Победил своего персонажа-немезиду"},
    "full_convince": {"name": "💯 Полное убеждение", "description": "Полностью переубедил персонажа за один бой"},
}

# Уровень CEFR → "многослойность" арсенала. Используется в ai.py, чтобы
# начальные уровни получали простой список слов + один совет, а не
# перегруженную формулу победы.
BEGINNER_LEVELS = {"A1", "A2"}