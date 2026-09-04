"""
Игровые данные: языки, уровни CEFR, персонажи, психология персонажей,
финальные комментарии и бейджи.
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

# Используется в промптах для генерации реплик персонажа
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

# Адаптация длины ответа под уровень
RESPONSE_LENGTH = {
    "A1": "1 короткое предложение (4-8 слов)",
    "A2": "1 предложение (6-10 слов)",
    "B1": "1-2 предложения (8-14 слов)",
    "B2": "1-2 предложения (10-16 слов)",
    "C1": "2-3 предложения (14-22 слов)",
    "C2": "2-3 предложения (16-25 слов)",
}

# Сложность МЫСЛИТЕЛЬНОЙ ЗАДАЧИ вступительного диалога по уровням
INTRO_LEVEL_TASKS = {
    "A1": "простые вопросы о фактах: что, где, когда — без необходимости объяснять «почему»",
    "A2": "причины, примеры, сравнения — простое обоснование своей мысли",
    "B1": "причины, примеры, сравнения — более развёрнутое обоснование своей точки зрения",
    "B2": "абстрактные вопросы, лёгкие контраргументы, больше самостоятельной аргументации",
    "C1": "нюансы, сложные сценарии, противоположные позиции",
    "C2": "интеллектуально сложные, неоднозначные вопросы, подтекст, нюансы, sophisticated reasoning",
}

GUIDE_PERSONALITY = {
    "name": "Alex",
    "desc": "Твой дружелюбный проводник в мире Arena 2.0. Помогу освоиться и подобрать идеального собеседника!",
}

ROLE_STYLE = {
    "ceo": "спрашивай про стратегию, риски, деньги, лидерство",
    "journalist": "задавай провокационные вопросы, ищи противоречия, проси доказательства",
    "professor": "проси объяснять подробнее, исправляй неточности",
    "hr_manager": "задавай поведенческие вопросы, проси примеры из опыта",
    "philosopher": "задавай глубокие философские вопросы, уводи разговор в сторону глобальных смыслов",
    "devil_advocate": "всегда спорь, находи слабые места в аргументах",
}

# Голос персонажа — примеры фраз для разных ситуаций
PERSONALITY_VOICE = {
    "ceo": {
        "opening": ["Convince me.", "I'm listening. But I need facts.", "What's your bottom line?"],
        "agree": ["That's a solid point.", "You're making sense.", "I like the way you think."],
        "disagree": ["That's not how it works.", "Show me the numbers.", "You're missing the ROI."],
        "challenge": ["And the risk?", "What about the cost?", "What's your backup plan?"],
        "closing": ["You've got potential. But next time, come with data."]
    },
    "journalist": {
        "opening": ["Are you sure?", "That's a bold claim.", "What's the real story here?"],
        "agree": ["Now that's interesting.", "I didn't expect that.", "That's a fresh angle."],
        "disagree": ["That's too obvious.", "You're not telling me everything.", "Where's the evidence?"],
        "challenge": ["What would your opponent say?", "And the other side?", "Can you prove that?"],
        "closing": ["You almost had me. But I wanted a scoop, not a statement."]
    },
    "professor": {
        "opening": ["Can you elaborate?", "What's your thesis?", "I'd like to hear your argument."],
        "agree": ["That's well-argued.", "You've made a solid case.", "I see your logic."],
        "disagree": ["That's not a valid conclusion.", "You're missing a step.", "Your evidence doesn't support that."],
        "challenge": ["What about counter-evidence?", "How do you defend that?", "What's your methodology?"],
        "closing": ["You have a good mind. But structure matters — thesis, argument, conclusion."]
    },
    "hr_manager": {
        "opening": ["Tell me about a time when...", "Can you give me a specific example?", "What's your approach to...?"],
        "agree": ["That's exactly the kind of thing we value.", "Great example.", "I like how you handled that."],
        "disagree": ["That's too vague. Give me specifics.", "How did that actually work?", "What was the outcome?"],
        "challenge": ["What would you do differently?", "How did others react?", "What did you learn?"],
        "closing": ["I hear good things. But next time, show me the result, not just the action."]
    },
    "philosopher": {
        "opening": ["What makes a good life?", "Why does that matter?", "What if you looked at it differently?"],
        "agree": ["You're touching on something deep.", "That's a profound thought.", "I like how you think."],
        "disagree": ["But is that really true?", "What about the other perspective?", "Are you being honest with yourself?"],
        "challenge": ["And what does that say about you?", "What's the alternative?", "How does that connect to everything?"],
        "closing": ["You gave me an answer. But I wanted a question."]
    },
    "devil_advocate": {
        "opening": ["What if you're wrong?", "I'm not convinced.", "Let me play devil's advocate."],
        "agree": ["You're holding up well.", "I like the way you fight.", "You're tougher than I thought."],
        "disagree": ["That's weak.", "You can do better.", "Try again."],
        "challenge": ["And what if I'm right?", "Prove it.", "Defend that."],
        "closing": ["You didn't break. I respect that. But next time, come harder."]
    }
}

# Персонажи
PERSONALITIES = {
    "ceo": {
        "name": "👑 Richard the CEO",
        "full_name": "Richard — CEO",
        "desc": "Построил три международные компании. Ненавидит воду, длинные "
                "вступления и отсутствие цифр. Любит факты, уверенность и структуру.",
        "style": "Любит короткие ответы. Не любит эмоции. Лучше работает логика.",
        "phrase": "Convince me.",
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

FALLBACK_LINKING_PHRASES = {
    "A1": ["and — и — соединение", "but — но — контраст", "because — потому что — причина"],
    "A2": ["and — и — соединение", "but — но — контраст", "because — потому что — причина", "so — поэтому — результат"],
    "B1": ["however — однако — контраст", "although — хотя — уступка", "therefore — следовательно — вывод", "for example — например — пример"],
    "B2": ["however — однако — контраст", "although — хотя — уступка", "therefore — следовательно — вывод", "furthermore — более того — добавление"],
    "C1": ["nonetheless — тем не менее — контраст", "consequently — вследствие этого — результат", "in addition — кроме того — добавление", "on the contrary — напротив — противопоставление"],
    "C2": ["nevertheless — тем не менее — контраст", "consequently — вследствие этого — результат", "in light of — в свете — учёт", "on the contrary — напротив — противопоставление"],
}

BADGES = {
    "first_debate": {"name": "🏆 Первый бой", "description": "Завершил первый раунд с персонажем"},
    "grammar_master": {"name": "📚 Грамматический мастер", "description": "Грамматика выше 90%"},
    "wordsmith": {"name": "🗣️ Мастер слова", "description": "Словарный запас выше 90%"},
    "marathoner": {"name": "🏃 Марафонец", "description": "10+ ответов за один раунд"},
    "all_characters": {"name": "🎭 Коллекционер", "description": "Сыграл со всеми персонажами"},
    "high_scorer": {"name": "🔥 На вершине", "description": "Средний балл за раунд выше 85"},
}

# ---------- НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ AI.PY ----------

# Зоны роста (для подбора персонажа)
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

SKILL_WEIGHTS = {
    "A1": {"language": 0.85, "communication": 0.15},
    "A2": {"language": 0.80, "communication": 0.20},
    "B1": {"language": 0.65, "communication": 0.35},
    "B2": {"language": 0.50, "communication": 0.50},
    "C1": {"language": 0.35, "communication": 0.65},
    "C2": {"language": 0.20, "communication": 0.80},
}

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

ARENA_MOVES = {
    "clarify": {"name": "Clarify", "description": "Уточнить расплывчатую мысль"},
    "contrast": {"name": "Contrast", "description": "Предложить противоположный взгляд"},
    "follow_up": {"name": "Follow Up", "description": "Развить интересную деталь"},
    "reflect": {"name": "Reflect", "description": "Показать человеку его собственную мысль"},
    "test": {"name": "Test", "description": "Проверить устойчивость позиции"},
    "connect": {"name": "Connect", "description": "Связать с предыдущим ответом"},
    "deepen": {"name": "Deepen", "description": "Перевести разговор на уровень глубже"},
    "observe": {"name": "Observe", "description": "Просто отметить паттерн"},
}

BATTLE_COMPLEXITY = {
    "A1": {"label": "Начальный уровень", "instruction": "Используй простые слова", "focus": "Базовые фразы", "target_skills": ["vocabulary", "grammar"]},
    "A2": {"label": "Базовый уровень", "instruction": "Используй простые конструкции", "focus": "Простые предложения", "target_skills": ["vocabulary", "grammar", "clarity"]},
    "B1": {"label": "Средний уровень", "instruction": "Используй связки", "focus": "Связки, аргументация", "target_skills": ["argumentation", "clarity", "precision"]},
    "B2": {"label": "Продвинутый средний", "instruction": "Используй сложные конструкции", "focus": "Пассивный залог, модальные глаголы", "target_skills": ["argumentation", "persuasion", "adaptability"]},
    "C1": {"label": "Продвинутый уровень", "instruction": "Используй сложные фразы, идиомы", "focus": "Академическая лексика", "target_skills": ["persuasion", "critical_thinking", "depth"]},
    "C2": {"label": "Экспертный уровень", "instruction": "Используй нюансированные аргументы", "focus": "Подтекст, сложная аргументация", "target_skills": ["depth", "adaptability", "persuasion"]},
}

LEVEL_WORDS = {
    "A1": ["good", "bad", "like", "want", "think", "because", "and", "but"],
    "A2": ["important", "interesting", "difficult", "easy", "should", "could", "would"],
    "B1": ["however", "therefore", "although", "furthermore", "consequently", "moreover"],
    "B2": ["nevertheless", "nonetheless", "accordingly", "in addition", "on the other hand"],
    "C1": ["notwithstanding", "consequently", "subsequently", "ultimately", "in light of"],
    "C2": ["insofar as", "insofar", "nonetheless", "notwithstanding", "in the event of"]
}

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

MISSION_SCENARIOS = {
    "work": {"templates": [
        "убедить {personality} что {topic} — это правильное решение для команды",
        "доказать {personality} что {topic} принесёт больше пользы, чем вреда",
    ]},
    "life": {"templates": [
        "убедить {personality} что {topic} — это действительно важно",
        "доказать {personality} что {topic} может изменить жизнь к лучшему",
    ]},
    "money": {"templates": [
        "убедить {personality} что {topic} — это хорошая инвестиция",
        "доказать {personality} что {topic} стоит потраченных денег",
    ]},
    "abstract": {"templates": [
        "убедить {personality} что {topic} — это ключ к успеху",
        "доказать {personality} что {topic} — это не просто слова",
    ]}
}

BATTLE_TYPES = {
    "mission": {"name": "Миссия", "description": "Убеди персонажа в чём-то важном", "time_limit": 15, "has_verdict": True, "xp_reward": 100},
    "free_talk": {"name": "Свободный разговор", "description": "Просто поговори с персонажем без оценки", "time_limit": None, "has_verdict": False, "xp_reward": 0},
}

BATTLE_OBJECTIVES = {
    "ceo": {
        "objectives": ["Привести 3 убедительных аргумента с цифрами", "Ответить на 2 возражения CEO", "Достичь согласия по 1 пункту"],
        "weapons": ["ROI", "strategy", "growth", "efficiency", "scale"],
        "win_condition": "CEO говорит: 'You've convinced me.'"
    },
    "journalist": {
        "objectives": ["Дать 3 неожиданных факта", "Ответить на 2 провокационных вопроса", "Заставить журналиста замолчать"],
        "weapons": ["evidence", "source", "investigation", "perspective", "controversy"],
        "win_condition": "Journalist говорит: 'That's actually a good point.'"
    },
    "professor": {
        "objectives": ["Сформулировать чёткий тезис", "Подтвердить его 2 аргументами", "Сделать вывод"],
        "weapons": ["hypothesis", "evidence", "analysis", "conclusion", "methodology"],
        "win_condition": "Professor говорит: 'Your thesis is well-argued.'"
    },
    "hr_manager": {
        "objectives": ["Рассказать 1 конкретную ситуацию по STAR", "Ответить на 2 вопроса о деталях", "Показать результат"],
        "weapons": ["experience", "responsibility", "achievement", "team", "result"],
        "win_condition": "HR Manager говорит: 'I would hire you for this role.'"
    },
    "philosopher": {
        "objectives": ["Задать 3 глубоких вопроса", "Ответить на 2 философских вопроса", "Связать тему с жизнью"],
        "weapons": ["meaning", "purpose", "existence", "value", "perspective"],
        "win_condition": "Philosopher говорит: 'You've given me something to think about.'"
    },
    "devil_advocate": {
        "objectives": ["Защитить свою позицию против 3 атак", "Не сдаться ни разу", "Найти слабое место оппонента"],
        "weapons": ["nevertheless", "furthermore", "consequently", "moreover", "despite"],
        "win_condition": "Devil's Advocate говорит: 'You've earned my respect.'"
    }
}