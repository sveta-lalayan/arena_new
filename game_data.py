"""
Игровые данные: языки, уровни CEFR, персонажи, психология персонажей,
финальные комментарии и бейджи.

Персонажи и вся сопутствующая логика (психология, комментарии в конце,
критерии оценки) — перенесены "один в один" из старого bot.py, чтобы
сохранить оригинальную механику и голос персонажей.
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

# Используется в промптах для генерации реплик персонажа (открывающее
# утверждение и продолжение диалога)
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

# Сложность МЫСЛИТЕЛЬНОЙ ЗАДАЧИ вступительного диалога по уровням — это НЕ
# про упрощение лексики (для этого есть LEVEL_DESCRIPTIONS), а про то, какого
# типа вопросы задаёт гид: от простых фактов к неоднозначным сценариям.
INTRO_LEVEL_TASKS = {
    "A1": "простые вопросы о фактах: что, где, когда — без необходимости объяснять «почему»",
    "A2": "причины, примеры, сравнения — простое обоснование своей мысли",
    "B1": "причины, примеры, сравнения — более развёрнутое обоснование своей точки зрения",
    "B2": "абстрактные вопросы, лёгкие контраргументы, больше самостоятельной аргументации",
    "C1": "нюансы, сложные сценарии, противоположные позиции",
    "C2": "интеллектуально сложные, неоднозначные вопросы, подтекст, нюансы, sophisticated reasoning",
}

# Персонаж-гид для вступительного диалога — НЕ входит в PERSONALITIES,
# используется только для представления в начале
GUIDE_PERSONALITY = {
    "name": "Alex",
    "desc": "Твой дружелюбный проводник в мире Arena 2.0. Помогу освоиться и подобрать идеального собеседника!",
}

# Стиль ответа персонажа, используется в промпте generate_ai_response
# (оригинальное имя в старом коде — role_style)
ROLE_STYLE = {
    "ceo": "спрашивай про стратегию, риски, деньги, лидерство",
    "journalist": "задавай провокационные вопросы, ищи противоречия, проси доказательства",
    "professor": "проси объяснять подробнее, исправляй неточности",
    "hr_manager": "задавай поведенческие вопросы, проси примеры из опыта",
    "philosopher": "задавай глубокие философские вопросы, уводи разговор в сторону глобальных смыслов",
    "devil_advocate": "всегда спорь, находи слабые места в аргументах",
}

# Персонажи — характеристики и критерии оценки ответов пользователя,
# перенесены из старого bot.py без изменений
PERSONALITIES = {
    "ceo": {
        "name": "👑 Richard the CEO",
        "full_name": "Richard — CEO",
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
        "criteria": {
            "argumentation": "Для Richard недостаточно просто сказать \"я так думаю\". "
                              "Ему нужны цифры, факты, выгода. Ты должен был объяснить, "
                              "как твоя идея принесёт результат. Этого сегодня не хватило.",
            "vocabulary": "Richard ценит деловую лексику: ROI, strategy, growth, "
                           "efficiency, scale. Используй эти слова, чтобы звучать убедительно.",
            "grammar": "Для CEO важны чёткие конструкции. Используй \"I believe that... "
                       "because...\", \"My proposal is...\", \"The key benefit is...\"",
            "examples": "Примеры фраз для Richard: \"The main advantage is...\", \"This "
                        "would increase efficiency by...\", \"From a business perspective...\"",
        },
    },
    "journalist": {
        "name": "📰 Kate the Journalist",
        "full_name": "Kate — Journalist",
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
        "criteria": {
            "argumentation": "Для Kate недостаточно просто согласиться или не "
                              "согласиться. Она ждёт неожиданных поворотов, свежих "
                              "идей. Ты должен был предложить альтернативный взгляд "
                              "или найти противоречие.",
            "vocabulary": "Kate ценит точные формулировки: \"I challenge that...\", "
                           "\"The real question is...\", \"I see it differently...\"",
            "grammar": "Для журналиста важны вопросы и контраргументы. Используй "
                       "\"However...\", \"On the other hand...\", \"What if...?\"",
            "examples": "Примеры фраз для Kate: \"That's one way to look at it, "
                        "but...\", \"I'd argue that...\", \"The evidence suggests...\"",
        },
    },
    "professor": {
        "name": "🎓 Professor Adams",
        "full_name": "Professor Adams",
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
        "criteria": {
            "argumentation": "Для Professor Adams недостаточно сказать \"я не "
                              "согласен\". Любой тезис должен быть подтверждён "
                              "примером или объяснением. Именно этого сегодня не хватило.",
            "vocabulary": "Professor Adams ценит академическую лексику: "
                           "\"Consequently...\", \"Furthermore...\", \"It is evident that...\"",
            "grammar": "Для профессора важны сложные конструкции. Используй "
                       "\"Not only... but also...\", \"It could be argued that...\"",
            "examples": "Примеры фраз для Professor Adams: \"I would argue that...\", "
                        "\"This is supported by...\", \"To illustrate this point...\"",
        },
    },
    "hr_manager": {
        "name": "💼 Sarah the HR Director",
        "full_name": "Sarah — HR Director",
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
        "criteria": {
            "argumentation": "Для Sarah недостаточно просто сказать \"я умею это "
                              "делать\". Ей нужна конкретная ситуация: где, когда, "
                              "что делал, какой был результат. STAR-метод — твой друг.",
            "vocabulary": "Sarah ценит фразы про опыт: \"I managed...\", \"I was "
                           "responsible for...\", \"The outcome was...\"",
            "grammar": "Для HR важны времена, показывающие опыт: Present Perfect "
                       "для накопленного опыта, Past Simple для конкретных ситуаций.",
            "examples": "Примеры фраз для Sarah: \"I successfully led...\", \"My "
                        "team achieved...\", \"This resulted in...\"",
        },
    },
    "philosopher": {
        "name": "🧙 Leo the Sage",
        "full_name": "Leo — The Sage",
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
        "criteria": {
            "argumentation": "Для Leo недостаточно дать простой ответ. Ему нужна "
                              "глубина: почему ты так думаешь, какие у этого "
                              "последствия, как это связано с большими вопросами.",
            "vocabulary": "Leo ценит абстрактную лексику: \"I tend to believe...\", "
                           "\"It seems to me...\", \"One could argue...\"",
            "grammar": "Для философа важны условные конструкции и сложные "
                       "предложения. Используй \"If we consider...\", \"It might be that...\"",
            "examples": "Примеры фраз для Leo: \"I wonder if...\", \"What if we "
                        "looked at it differently?\", \"Perhaps we should consider...\"",
        },
    },
    "devil_advocate": {
        "name": "😈 Victor the Advocate",
        "full_name": "Victor — Devil's Advocate",
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
        "criteria": {
            "argumentation": "Для Victor недостаточно просто согласиться. Он ждёт, "
                              "что ты будешь защищать свою позицию, даже если он "
                              "давит. Ты должен был найти контраргументы и не сдаваться.",
            "vocabulary": "Victor ценит сильные фразы: \"I strongly disagree...\", "
                           "\"That's not necessarily true...\", \"I see it differently...\"",
            "grammar": "Для Дьявольского адвоката важны модальные глаголы "
                       "уверенности: \"must\", \"cannot\", \"should\". Используй их, "
                       "чтобы звучать твёрже.",
            "examples": "Примеры фраз для Victor: \"I see your point, however...\", "
                        "\"While that may be true...\", \"The problem with that is...\"",
        },
    },
}

# Утрированные комментарии персонажа в конце игры (личное обращение,
# сохранено дословно из старого bot.py)
PERSONALITY_COMMENTS = {
    "ceo": """Слушай. Ты смелая. Это плюс.

Но я — Ричард. Мне нужны ФАКТЫ.
Где цифры? Где выгода? Где стратегия?

В следующий раз приходи с расчётами.
Иначе — не приходи.

Я не нанимаю людей по эмоциям.""",
    "journalist": """Ого! Ты говорила, говорила...

Но где СЕНСАЦИЯ?
Где тот самый поворот, за которым я пришла?

Я ждала цитату. А получила... просто слова.

В следующий раз рискни.
Скажи то, что никто не говорит.

Я это запомню.""",
    "professor": """Хм. Я понял твою мысль.

Но между МНЕНИЕМ и АРГУМЕНТОМ — огромная разница.
Ты принесла мнение.

Где структура? Где доказательства?

В следующий раз — строй цепочку:
ТЕЗИС → АРГУМЕНТ → ВЫВОД.

Иначе ты просто говоришь с собой.""",
    "hr_manager": """У тебя есть потенциал.

Но я — Сара. Я нанимаю людей каждый день.
Я слышала эти слова сто раз.

Где КОНКРЕТИКА?
Где примеры? Где результаты?

В следующий раз — расскажи историю.
Я не нанимаю по общим фразам.

Я нанимаю по ДЕЛАМ.""",
    "philosopher": """Ты дала ответ.

Но задала ли ты себе ГЛАВНЫЙ ВОПРОС?
Почему ты так думаешь?
Что стоит за твоими словами?

Я искал глубину.
Ты дала мне поверхность.

В следующий раз — не отвечай.
Спрашивай.

Честность важнее правильности.""",
    "devil_advocate": """Ха! Ты начала неплохо.

Но я — Виктор. Я давлю, пока не сломается.
И ты начала сдавать позиции.

Ты соглашалась слишком легко.
Ты боялась спорить.

В следующий раз — БЕЙ В ОТВЕТ.
Я не уважаю тех, кто сдаётся.

Докажи, что ты можешь защитить свою позицию.""",
}

# Реплика персонажа при ПОБЕДЕ пользователя (usage_percentage >= 80)
PERSONALITY_COMMENTS_WIN = {
    "ceo": """Хорошо. Ты пришла с фактами, а не с эмоциями.

Цифры сошлись. Стратегия понятна.

Я бы это профинансировал.

Приходи ещё — с такими же расчётами.""",
    "journalist": """Вот это интервью!

Ты дала мне то, за чем я пришла — поворот, которого я не ждала.

Я ставлю это в номер. Без купюр.

Такой уровень — держи планку.""",
    "professor": """Тезис. Аргумент. Вывод.

Всё на месте. Ты доказала свою позицию, а не просто высказала мнение.

Это была настоящая академическая работа.

Продолжай мыслить так же строго.""",
    "hr_manager": """Вот это я и хотела услышать.

Конкретика. Результат. Ответственность.

Я бы взяла тебя в команду прямо сейчас.

Ты нанята.""",
    "philosopher": """Ты дала мне не ответ. Ты дала мне вопрос.

Это редкость.

Ты копнула глубже, чем большинство.

Продолжай спрашивать «почему».""",
    "devil_advocate": """Ты не сдалась. Ни разу.

Я давил — ты держала позицию.

Это то, что я называю силой воли.

Уважение заслужено.""",
}

# Реплика персонажа при ПОРАЖЕНИИ пользователя (usage_percentage < 50)
PERSONALITY_COMMENTS_LOSE = {
    "ceo": """Слушай. Ты смелая. Это плюс.

Но я — Ричард. Мне нужны ФАКТЫ.
Где цифры? Где выгода? Где стратегия?

В следующий раз приходи с расчётами.
Иначе — не приходи.

Я не нанимаю людей по эмоциям.""",
    "journalist": """Я ждала сенсации.

А получила интервью, которое даже стыдно где-то опубликовать.

Может, в следующий раз ты рискнёшь и скажешь то, что никто не говорит.

Я запомню эту попытку. Но не эту историю.""",
    "professor": """Хм. Я понял твою мысль.

Но между МНЕНИЕМ и АРГУМЕНТОМ — огромная разница.
Ты принесла мнение.

Где структура? Где доказательства?

В следующий раз — строй цепочку:
ТЕЗИС → АРГУМЕНТ → ВЫВОД.""",
    "hr_manager": """У тебя есть потенциал.

Но я — Сара. Я нанимаю людей каждый день.
Я слышала эти слова сто раз.

Где КОНКРЕТИКА? Где примеры? Где результаты?

Я не нанимаю по общим фразам. Я нанимаю по ДЕЛАМ.""",
    "philosopher": """Ты дала ответ.

Но задала ли ты себе ГЛАВНЫЙ ВОПРОС?

Я искал глубину. Ты дала мне поверхность.

В следующий раз — не отвечай. Спрашивай.""",
    "devil_advocate": """Ха! Ты начала неплохо.

Но я — Виктор. Я давлю, пока не сломается.
И ты начала сдавать позиции.

В следующий раз — БЕЙ В ОТВЕТ.
Я не уважаю тех, кто сдаётся.""",
}

# ---------- ARENA: CHARACTER MEMORY / ANTI-DRIFT ----------
# "PERSONALITY CORE NEVER CHANGES" — фиксированный блок, который на КАЖДОМ
# ходу подмешивается в промпт, чтобы персонаж не съезжал в small talk,
# не становился мягким психологом и не терял миссию.

CHARACTER_CORE = {
    "ceo": {
        "identity": "Richard, CEO крупной компании",
        "personality_traits": ["требовательный", "прямой", "нетерпеливый", "уважает только факты"],
        "communication_style": "коротко, жёстко, по делу — цифры и стратегия вместо эмоций",
        "values": ["ROI", "стратегия", "эффективность", "рост"],
        "never_become": ["мягкий коуч", "доброжелательный ментор", "терапевт", "случайный собеседник"],
    },
    "journalist": {
        "identity": "Kate, журналист-расследователь",
        "personality_traits": ["скептичная", "цепкая", "ищет сенсацию", "не отпускает уклончивые ответы"],
        "communication_style": "провокационные вопросы, охота за противоречиями",
        "values": ["факты", "источники", "неожиданные повороты", "правда"],
        "never_become": ["мягкий интервьюер", "друг", "терапевт", "нейтральный ассистент"],
    },
    "professor": {
        "identity": "Professor Adams",
        "personality_traits": ["требовательный", "аналитический", "скептичный", "эмоционально сдержанный"],
        "communication_style": "требует структуру тезис → аргумент → вывод, придирается к логике",
        "values": ["доказательства", "точность", "методология", "логика"],
        "never_become": ["дружелюбный учитель английского", "коуч поддержки", "случайный приятель"],
    },
    "hr_manager": {
        "identity": "Sarah, HR-директор",
        "personality_traits": ["требовательная", "внимательна к деталям", "не терпит общих фраз"],
        "communication_style": "стресс-интервью, требует конкретику и результат по STAR",
        "values": ["ответственность", "конкретные примеры", "результат"],
        "never_become": ["мягкий рекрутер, который всех хвалит", "терапевт", "друг"],
    },
    "philosopher": {
        "identity": "Leo, мудрец-философ",
        "personality_traits": ["спокойный", "глубокий", "никогда не даёт прямых ответов"],
        "communication_style": "отвечает вопросом на вопрос, копает глубже",
        "values": ["смысл", "честность мысли", "глубина", "связь с жизнью"],
        "never_become": ["дающий советы лайф-коуч", "психолог", "обычный собеседник"],
    },
    "devil_advocate": {
        "identity": "Victor, дьявольский адвокат",
        "personality_traits": ["провокационный", "непреклонный", "уважает только силу аргумента"],
        "personality_traits_note": "может смягчиться после действительно сильного аргумента, но не меняет характер",
        "communication_style": "давит, находит слабые места, никогда не сдаётся первым",
        "values": ["сила аргумента", "уверенность", "устойчивость под давлением"],
        "never_become": ["сторонник пользователя", "мягкий собеседник", "терапевт"],
    },
}

# Шкала результата Battle: 0-30 очков -> DEFEATED / ALMOST / VICTORY / OUTPLAYED
RESULT_BANDS = [
    {"key": "defeated", "min": 0, "max": 9, "label": "💀 DEFEATED", "desc": "Миссия не выполнена."},
    {"key": "almost", "min": 10, "max": 19, "label": "⚠️ ALMOST", "desc": "Ты был близко, но не дожал миссию."},
    {"key": "victory", "min": 20, "max": 24, "label": "🏆 VICTORY", "desc": "Миссия выполнена."},
    {"key": "outplayed", "min": 25, "max": 30, "label": "👑 OUTPLAYED", "desc": "Миссия выполнена блестяще, давление персонажа выдержано полностью."},
]

# ARENA XP отдельно от Battle Score — общий прогресс по кампании (100 XP = уровень)
XP_REWARDS = {
    "defeated": 5,
    "almost": 7,
    "victory": 10,
    "outplayed": 12,
}

# 6 стадий эскалации внутри одного Battle
BATTLE_STAGES = [
    {"stage": 1, "name": "OPENING", "instruction": "Представь вызов/миссию, сразу в своём характере, без приветствий."},
    {"stage": 2, "name": "ARGUMENT", "instruction": "Выслушай позицию пользователя, отреагируй в характере."},
    {"stage": 3, "name": "PRESSURE", "instruction": "Поставь под сомнение его рассуждение, потребуй обоснование."},
    {"stage": 4, "name": "OBJECTION", "instruction": "Атакуй самое слабое место в его позиции — конкретно и жёстко."},
    {"stage": 5, "name": "ADAPTATION", "instruction": "Дай неожиданное возражение, на которое он ещё не отвечал."},
    {"stage": 6, "name": "FINAL_TEST", "instruction": "Дай последний шанс доказать позицию, это финальная проверка."},
]

# ---------- ARENA: BATTLE SYSTEM ----------

BATTLE_TYPES = {
    "mission": {
        "name": "Миссия",
        "description": "Убеди персонажа в чём-то важном",
        "time_limit": 15,  # минут
        "has_verdict": True,
        "xp_reward": 100,
    },
    "free_talk": {
        "name": "Свободный разговор",
        "description": "Просто поговори с персонажем без оценки",
        "time_limit": None,
        "has_verdict": False,
        "xp_reward": 0,
    }
}

# Шаблоны миссий для каждого персонажа
BATTLE_OBJECTIVES = {
    "ceo": {
        "objectives": [
            "Привести 3 убедительных аргумента с цифрами",
            "Ответить на 2 возражения CEO",
            "Достичь согласия по 1 пункту"
        ],
        "weapons": ["ROI", "strategy", "growth", "efficiency", "scale"],
        "win_condition": "CEO говорит: 'You've convinced me.'"
    },
    "journalist": {
        "objectives": [
            "Дать 3 неожиданных факта",
            "Ответить на 2 провокационных вопроса",
            "Заставить журналиста замолчать хотя бы на секунду"
        ],
        "weapons": ["evidence", "source", "investigation", "perspective", "controversy"],
        "win_condition": "Journalist говорит: 'That's actually a good point.'"
    },
    "professor": {
        "objectives": [
            "Сформулировать чёткий тезис",
            "Подтвердить его 2 аргументами",
            "Сделать вывод"
        ],
        "weapons": ["hypothesis", "evidence", "analysis", "conclusion", "methodology"],
        "win_condition": "Professor говорит: 'Your thesis is well-argued.'"
    },
    "hr_manager": {
        "objectives": [
            "Рассказать 1 конкретную ситуацию по STAR",
            "Ответить на 2 вопроса о деталях",
            "Показать результат своих действий"
        ],
        "weapons": ["experience", "responsibility", "achievement", "team", "result"],
        "win_condition": "HR Manager говорит: 'I would hire you for this role.'"
    },
    "philosopher": {
        "objectives": [
            "Задать 3 глубоких вопроса",
            "Ответить на 2 философских вопроса",
            "Связать тему с жизнью"
        ],
        "weapons": ["meaning", "purpose", "existence", "value", "perspective"],
        "win_condition": "Philosopher говорит: 'You've given me something to think about.'"
    },
    "devil_advocate": {
        "objectives": [
            "Защитить свою позицию против 3 атак",
            "Не сдаться ни разу",
            "Найти слабое место в аргументах оппонента"
        ],
        "weapons": ["nevertheless", "furthermore", "consequently", "moreover", "despite"],
        "win_condition": "Devil's Advocate говорит: 'You've earned my respect.'"
    }
}

# ---------- ARENA: шаблоны миссий для битв ----------

PERSONALITY_MISSION_TEMPLATES = {
    "ceo": {
        "name": "CEO",
        "challenge_style": "убедить с помощью фактов, цифр и стратегии",
        "likes": ["цифры", "стратегию", "аргументы", "ROI", "выгоду"],
        "dislikes": ["эмоции", "воду", "длинные вступления"],
        "phrase": "Convince me with numbers and strategy.",
    },
    "journalist": {
        "name": "Journalist",
        "challenge_style": "убедить с помощью неожиданных фактов и провокаций",
        "likes": ["сенсации", "неожиданные повороты", "конкретику", "доказательства"],
        "dislikes": ["общие слова", "очевидные ответы", "уклончивость"],
        "phrase": "Give me something unexpected.",
    },
    "professor": {
        "name": "Professor",
        "challenge_style": "убедить с помощью структуры и доказательств",
        "likes": ["тезис → аргумент → вывод", "точность", "доказательства", "логику"],
        "dislikes": ["неточности", "эмоции вместо фактов", "поверхностность"],
        "phrase": "Show me your thesis, argument, and conclusion.",
    },
    "hr_manager": {
        "name": "HR Director",
        "challenge_style": "убедить с помощью конкретных примеров из жизни",
        "likes": ["конкретные ситуации", "STAR-метод", "примеры из жизни", "ответственность"],
        "dislikes": ["общие фразы", "избегание конкретики", "безответственность"],
        "phrase": "Give me a real example from your life.",
    },
    "philosopher": {
        "name": "Sage",
        "challenge_style": "убедить с помощью глубины и смысла",
        "likes": ["глубину", "честность", "связь с жизнью", "вопросы"],
        "dislikes": ["поверхностность", "ответы 'да/нет'", "банальность"],
        "phrase": "Why does it really matter?",
    },
    "devil_advocate": {
        "name": "Devil's Advocate",
        "challenge_style": "убедить, защищая свою позицию под давлением",
        "likes": ["сильные аргументы", "уверенность", "способность защищать позицию"],
        "dislikes": ["слабость", "уступчивость", "неуверенность"],
        "phrase": "Prove me wrong. I dare you.",
    }
}

# Шаблоны для генерации миссий
MISSION_SCENARIOS = {
    "work": {
        "templates": [
            "убедить {personality} что {topic} — это правильное решение для команды",
            "доказать {personality} что {topic} принесёт больше пользы, чем вреда",
            "переубедить {personality} которая считает что {topic} — пустая трата времени",
        ]
    },
    "life": {
        "templates": [
            "убедить {personality} что {topic} — это действительно важно",
            "доказать {personality} что {topic} может изменить жизнь к лучшему",
            "переубедить {personality} которая не верит в {topic}",
        ]
    },
    "money": {
        "templates": [
            "убедить {personality} что {topic} — это хорошая инвестиция",
            "доказать {personality} что {topic} стоит потраченных денег",
            "переубедить {personality} которая считает что {topic} — это дорого и бессмысленно",
        ]
    },
    "abstract": {
        "templates": [
            "убедить {personality} что {topic} — это ключ к успеху",
            "доказать {personality} что {topic} — это не просто слова",
            "переубедить {personality} которая сомневается в {topic}",
        ]
    }
}

# ---------- ARENA: интеллектуальные ходы ----------

ARENA_MOVES = {
    "clarify": {
        "name": "Clarify",
        "description": "Уточнить расплывчатую мысль",
        "trigger": "позиция размыта, нет конкретики",
        "pattern": "Что именно вы имеете в виду под...?"
    },
    "contrast": {
        "name": "Contrast",
        "description": "Предложить противоположный взгляд",
        "trigger": "позиция слишком очевидна или однобока",
        "pattern": "А если посмотреть на это с противоположной стороны?"
    },
    "follow_up": {
        "name": "Follow Up",
        "description": "Развить интересную деталь",
        "trigger": "появилась неожиданная или глубокая деталь",
        "pattern": "Вы упомянули... Что в этом оказалось самым важным?"
    },
    "reflect": {
        "name": "Reflect",
        "description": "Показать человеку его собственную мысль",
        "trigger": "мысль сформулирована, но не осознана",
        "pattern": "Получается, для вас... важнее, чем..."
    },
    "test": {
        "name": "Test",
        "description": "Проверить устойчивость позиции",
        "trigger": "позиция уверенная, но не проверенная",
        "pattern": "А что могло бы заставить вас изменить это мнение?"
    },
    "connect": {
        "name": "Connect",
        "description": "Связать с предыдущим ответом",
        "trigger": "есть связь с более ранним ответом",
        "pattern": "Это интересно, учитывая, что раньше вы говорили о..."
    },
    "deepen": {
        "name": "Deepen",
        "description": "Перевести разговор на уровень глубже",
        "trigger": "поверхностный ответ, за которым чувствуется глубина",
        "pattern": "Но почему именно это для вас важно?"
    },
    "observe": {
        "name": "Observe",
        "description": "Просто отметить паттерн, не задавая вопрос",
        "trigger": "паттерн повторяется, можно просто отметить",
        "pattern": "Это интересно. Вы уже не первый раз возвращаетесь к этой теме."
    }
}

# ---------- ARENA: динамическая система обучения ----------

# Вес навыков в зависимости от уровня
SKILL_WEIGHTS = {
    "A1": {"language": 0.85, "communication": 0.15},
    "A2": {"language": 0.80, "communication": 0.20},
    "B1": {"language": 0.65, "communication": 0.35},
    "B2": {"language": 0.50, "communication": 0.50},
    "C1": {"language": 0.35, "communication": 0.65},
    "C2": {"language": 0.20, "communication": 0.80},
}

# Навыки по категориям
LANGUAGE_SKILLS = {
    "grammar": {"name": "Грамматика", "emoji": "📝"},
    "vocabulary": {"name": "Словарный запас", "emoji": "📚"},
    "fluency": {"name": "Беглость", "emoji": "🎤"},
    "complexity": {"name": "Сложность речи", "emoji": "🧩"},
    "accuracy": {"name": "Точность", "emoji": "🎯"},
}

COMMUNICATION_SKILLS = {
    "clarity": {"name": "Ясность", "emoji": "💡"},
    "precision": {"name": "Точность формулировок", "emoji": "📐"},
    "argumentation": {"name": "Аргументация", "emoji": "⚔️"},
    "persuasion": {"name": "Убедительность", "emoji": "🔥"},
    "critical_thinking": {"name": "Критическое мышление", "emoji": "🧠"},
    "adaptability": {"name": "Адаптивность", "emoji": "🌀"},
    "confidence": {"name": "Уверенность", "emoji": "💪"},
}

# 10 скиллов на персонажа: 2 сквозных (одинаковых у всех) + 8 характерных.
SKILLS_COMMON = ["grammar", "vocabulary"]

SKILL_LABELS = {
    "grammar": {"name": "Грамматика", "emoji": "📝"},
    "vocabulary": {"name": "Словарный запас", "emoji": "📚"},
    "persuasion": {"name": "Убедительность", "emoji": "🔥"},
    "argumentation": {"name": "Аргументация", "emoji": "⚔️"},
    "precision": {"name": "Точность формулировок", "emoji": "📐"},
    "confidence": {"name": "Уверенность", "emoji": "💪"},
    "decisiveness": {"name": "Решительность", "emoji": "⚡"},
    "negotiation": {"name": "Переговоры", "emoji": "🤝"},
    "strategic_thinking": {"name": "Стратегическое мышление", "emoji": "🧭"},
    "composure": {"name": "Хладнокровие", "emoji": "🧊"},
    "clarity": {"name": "Ясность", "emoji": "💡"},
    "critical_thinking": {"name": "Критическое мышление", "emoji": "🧠"},
    "curiosity": {"name": "Любопытство", "emoji": "🔍"},
    "storytelling": {"name": "Storytelling", "emoji": "🎬"},
    "quick_thinking": {"name": "Быстрота реакции", "emoji": "⚡"},
    "handling_scrutiny": {"name": "Устойчивость к давлению", "emoji": "🛡️"},
    "adaptability": {"name": "Гибкость", "emoji": "🌀"},
    "structure": {"name": "Структура речи", "emoji": "🏗️"},
    "complexity": {"name": "Сложность речи", "emoji": "🧩"},
    "academic_register": {"name": "Академический стиль", "emoji": "🎓"},
    "patience": {"name": "Терпение", "emoji": "⏳"},
    "depth": {"name": "Глубина мысли", "emoji": "🌊"},
    "empathy": {"name": "Эмпатия", "emoji": "❤️"},
    "self_reflection": {"name": "Рефлексия", "emoji": "🪞"},
    "accountability": {"name": "Ответственность", "emoji": "✅"},
    "teamwork_language": {"name": "Командная лексика", "emoji": "👥"},
    "open_mindedness": {"name": "Открытость", "emoji": "🌐"},
    "abstract_reasoning": {"name": "Абстрактное мышление", "emoji": "🎨"},
    "question_asking": {"name": "Умение спрашивать", "emoji": "❓"},
    "honesty": {"name": "Честность", "emoji": "🕊️"},
    "resilience": {"name": "Устойчивость", "emoji": "🧱"},
    "assertiveness": {"name": "Напористость", "emoji": "🎯"},
}

# 8 характерных soft-скиллов на каждого персонажа (+ 2 общих = 10 итого)
PERSONALITY_SKILLS = {
    "ceo": ["persuasion", "argumentation", "precision", "confidence",
            "decisiveness", "negotiation", "strategic_thinking", "composure"],
    "journalist": ["clarity", "precision", "critical_thinking", "curiosity",
                   "storytelling", "quick_thinking", "handling_scrutiny", "adaptability"],
    "professor": ["argumentation", "structure", "complexity", "critical_thinking",
                  "precision", "academic_register", "patience", "depth"],
    "hr_manager": ["clarity", "adaptability", "confidence", "storytelling",
                   "empathy", "self_reflection", "accountability", "teamwork_language"],
    "philosopher": ["depth", "complexity", "critical_thinking", "curiosity",
                     "open_mindedness", "abstract_reasoning", "question_asking", "honesty"],
    "devil_advocate": ["argumentation", "confidence", "critical_thinking", "composure",
                        "resilience", "quick_thinking", "persuasion", "assertiveness"],
}

# ---------- BATTLE COMPLEXITY ----------

BATTLE_COMPLEXITY = {
    "A1": {
        "label": "Начальный уровень",
        "instruction": "Используй простые слова и постарайся переубедить меня",
        "focus": "Базовые фразы, простые аргументы",
        "target_skills": ["vocabulary", "grammar"]
    },
    "A2": {
        "label": "Базовый уровень",
        "instruction": "Используй простые конструкции и постарайся меня переубедить",
        "focus": "Простые предложения, базовые связки",
        "target_skills": ["vocabulary", "grammar", "clarity"]
    },
    "B1": {
        "label": "Средний уровень",
        "instruction": "Используй связки (however, therefore, although) и постарайся меня переубедить",
        "focus": "Связки, аргументация, примеры",
        "target_skills": ["argumentation", "clarity", "precision"]
    },
    "B2": {
        "label": "Продвинутый средний",
        "instruction": "Используй сложные конструкции и постарайся меня переубедить",
        "focus": "Пассивный залог, модальные глаголы, идиомы",
        "target_skills": ["argumentation", "persuasion", "adaptability"]
    },
    "C1": {
        "label": "Продвинутый уровень",
        "instruction": "Используй сложные фразы, идиомы и постарайся меня переубедить",
        "focus": "Академическая лексика, сложные конструкции",
        "target_skills": ["persuasion", "critical_thinking", "depth"]
    },
    "C2": {
        "label": "Экспертный уровень",
        "instruction": "Используй нюансированные аргументы, идиомы и постарайся меня переубедить",
        "focus": "Подтекст, сложная аргументация, стилистика",
        "target_skills": ["depth", "adaptability", "persuasion"]
    }
}

# Базовые слова для каждого уровня
LEVEL_WORDS = {
    "A1": ["good: хороший", "like: нравится", "want: хотеть", "think: думать", "because: потому что"],
    "A2": ["important: важный", "interesting: интересный", "should: следует", "could: мог бы", "would: бы"],
    "B1": ["however: однако", "therefore: следовательно", "although: хотя", "furthermore: более того", "consequently: следовательно"],
    "B2": ["nevertheless: тем не менее", "nonetheless: несмотря на", "accordingly: соответственно", "in addition: кроме того", "on the other hand: с другой стороны"],
    "C1": ["notwithstanding: несмотря на", "consequently: следовательно", "ultimately: в конечном счёте", "in light of: в свете", "accordingly: соответственно"],
    "C2": ["insofar as: поскольку", "nonetheless: тем не менее", "notwithstanding: несмотря на", "in the event of: в случае", "consequently: следовательно"],
}

# Карта зон роста → персонажи
GROWTH_TO_PERSONALITY = {
    "vocabulary": "ceo",
    "persuasion": "ceo",
    "grammar": "professor",
    "clarity": "journalist",
    "precision": "journalist",
    "argumentation": "devil_advocate",
    "critical_thinking": "devil_advocate",
    "fluency": "hr_manager",
    "adaptability": "hr_manager",
    "confidence": "hr_manager",
    "complexity": "philosopher",
    "depth": "philosopher",
}

# Описание миссий для каждого персонажа
PERSONALITY_MISSIONS = {
    "ceo": {
        "name": "Convince the CEO",
        "description": "Представь бизнес-идею так, чтобы CEO захотел инвестировать",
        "skills": ["persuasion", "argumentation", "precision"],
        "target_words": ["ROI", "strategy", "growth", "efficiency", "scale"],
        "win_condition": "3/4 аргументов должны быть убедительными"
    },
    "journalist": {
        "name": "Survive the Interview",
        "description": "Ответь на провокационные вопросы журналиста",
        "skills": ["clarity", "precision", "critical_thinking"],
        "target_words": ["evidence", "source", "investigation", "perspective", "controversy"],
        "win_condition": "Ответь на все вопросы без потери позиции"
    },
    "professor": {
        "name": "Defend Your Thesis",
        "description": "Защити свою научную работу перед профессором",
        "skills": ["argumentation", "complexity", "grammar"],
        "target_words": ["hypothesis", "evidence", "analysis", "conclusion", "methodology"],
        "win_condition": "Структура: тезис → аргумент → вывод"
    },
    "hr_manager": {
        "name": "Ace the Interview",
        "description": "Пройди собеседование с HR-директором",
        "skills": ["clarity", "adaptability", "confidence"],
        "target_words": ["experience", "responsibility", "achievement", "team", "result"],
        "win_condition": "Каждый ответ — по STAR-методу"
    },
    "philosopher": {
        "name": "Explore the Depths",
        "description": "Веди философский диалог о смысле",
        "skills": ["depth", "complexity", "critical_thinking"],
        "target_words": ["meaning", "purpose", "existence", "value", "perspective"],
        "win_condition": "Каждый ответ должен содержать вопрос"
    },
    "devil_advocate": {
        "name": "Defend Your Position",
        "description": "Отстой свою позицию под давлением оппонента",
        "skills": ["argumentation", "critical_thinking", "confidence"],
        "target_words": ["nevertheless", "furthermore", "consequently", "moreover", "despite"],
        "win_condition": "Ни разу не сдай позицию"
    }
}

# ---------- Бейджи/достижения ----------

BADGES = {
    "first_debate": {"name": "🏆 Первый бой", "description": "Завершил первый раунд с персонажем"},
    "grammar_master": {"name": "📚 Грамматический мастер", "description": "Грамматика выше 90%"},
    "wordsmith": {"name": "🗣️ Мастер слова", "description": "Словарный запас выше 90%"},
    "marathoner": {"name": "🏃 Марафонец", "description": "10+ ответов за один раунд"},
    "all_characters": {"name": "🎭 Коллекционер", "description": "Сыграл со всеми персонажами"},
    "high_scorer": {"name": "🔥 На вершине", "description": "Средний балл за раунд выше 85"},
}

# ---------- Частые грамматические ошибки ----------

COMMON_GRAMMAR_ERRORS = {
    "have go": "have gone / go",
    "she don't": "she doesn't",
    "he don't": "he doesn't",
    "it don't": "it doesn't",
    "there is many": "there are many",
    "there are much": "there is much",
    "i is": "I am",
    "we is": "we are",
    "they is": "they are",
    "she have": "she has",
    "he have": "he has",
    "it have": "it has",
}

# Резервные связки по уровню
FALLBACK_LINKING_PHRASES = {
    "A1": ["and — и — соединение", "but — но — контраст", "because — потому что — причина"],
    "A2": ["and — и — соединение", "but — но — контраст", "because — потому что — причина", "so — поэтому — результат"],
    "B1": ["however — однако — контраст", "although — хотя — уступка", "therefore — следовательно — вывод", "for example — например — пример"],
    "B2": ["however — однако — контраст", "although — хотя — уступка", "therefore — следовательно — вывод", "furthermore — более того — добавление"],
    "C1": ["nonetheless — тем не менее — контраст", "consequently — вследствие этого — результат", "in addition — кроме того — добавление", "on the contrary — напротив — противопоставление"],
    "C2": ["nevertheless — тем не менее — контраст", "consequently — вследствие этого — результат", "in light of — в свете — учёт", "on the contrary — напротив — противопоставление"],
}

# ---------- GROWTH AREAS ----------

GROWTH_AREA_LABELS = {
    "VOCABULARY_RANGE": "Словарный запас",
    "GRAMMAR_ACCURACY": "Грамматическая точность",
    "CLARITY": "Ясность мысли",
    "PRECISION": "Точность формулировок",
    "ARGUMENTATION": "Аргументация",
    "PERSUASION": "Убедительность",
    "FLUENCY": "Беглость речи",
    "COMPOSURE": "Хладнокровие под давлением",
    "ADAPTABILITY": "Гибкость в разговоре",
    "DEPTH": "Глубина мысли",
}

GROWTH_AREA_TO_PERSONALITY = {
    "VOCABULARY_RANGE": "ceo",
    "PERSUASION": "ceo",
    "GRAMMAR_ACCURACY": "professor",
    "CLARITY": "journalist",
    "PRECISION": "journalist",
    "ARGUMENTATION": "devil_advocate",
    "COMPOSURE": "devil_advocate",
    "FLUENCY": "hr_manager",
    "ADAPTABILITY": "hr_manager",
    "DEPTH": "philosopher",
}