"""
Игровые данные: языки, уровни CEFR, персонажи и бейджи.
Ничего телеграм-специфичного здесь нет — можно переиспользовать где угодно.
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
          "базовую лексику (до 500 слов), Present Simple, говори медленно и чётко",
    "A2": "используй простые предложения, Past Simple, Future Simple, "
          "лексика до 1000 слов, короткие связки (and, but, because)",
    "B1": "используй среднюю сложность, Present Perfect, Past Continuous, "
          "лексика до 2000 слов, связки (however, although, therefore)",
    "B2": "используй сложные предложения, все времена, модальные глаголы, "
          "пассивный залог, лексика до 4000 слов, идиомы среднего уровня",
    "C1": "используй сложные грамматические конструкции, инверсию, "
          "академическую лексику, идиомы, абстрактные понятия",
    "C2": "используй академическую лексику, сложные синтаксические конструкции, "
          "нюансированные аргументы, продвинутые идиомы",
}

# Персонажи — у каждого свой характер, стиль и критерии оценки ответов
PERSONALITIES = {
    "ceo": {
        "name": "👑 Richard the CEO",
        "full_name": "Richard — CEO",
        "desc": "Построил три международные компании. Ненавидит воду, длинные "
                "вступления и отсутствие цифр. Любит факты, уверенность и структуру.",
        "style": "задавай короткие деловые вопросы про стратегию, риски, деньги, лидерство",
        "phrase": "Convince me.",
        "criteria": {
            "argumentation": "Ричарду нужны цифры, факты, выгода — не просто мнение.",
            "vocabulary": "Ценит деловую лексику: ROI, strategy, growth, efficiency, scale.",
            "grammar": "Чёткие конструкции: \"I believe that... because...\", \"My proposal is...\"",
        },
    },
    "journalist": {
        "name": "📰 Kate the Journalist",
        "full_name": "Kate — Journalist",
        "desc": "Ищет слабые места. Любит задавать неудобные вопросы. Никогда не "
                "принимает ответ сразу.",
        "style": "задавай провокационные вопросы, ищи противоречия, проси доказательства",
        "phrase": "Are you sure?",
        "criteria": {
            "argumentation": "Ждёт неожиданных поворотов и свежих идей, а не общих фраз.",
            "vocabulary": "\"I challenge that...\", \"The real question is...\"",
            "grammar": "\"However...\", \"On the other hand...\", \"What if...?\"",
        },
    },
    "professor": {
        "name": "🎓 Professor Adams",
        "full_name": "Professor Adams",
        "desc": "Академик. Требует точности и доказательств. Исправляет ошибки.",
        "style": "проси объяснять подробнее, исправляй неточности",
        "phrase": "Can you elaborate?",
        "criteria": {
            "argumentation": "Любой тезис должен быть подтверждён примером или объяснением.",
            "vocabulary": "\"Consequently...\", \"Furthermore...\", \"It is evident that...\"",
            "grammar": "\"Not only... but also...\", \"It could be argued that...\"",
        },
    },
    "hr_manager": {
        "name": "💼 Sarah the HR Director",
        "full_name": "Sarah — HR Director",
        "desc": "Проводит собеседования. Любую тему переводит в вопросы о работе, "
                "опыте, навыках.",
        "style": "задавай поведенческие вопросы, проси примеры из опыта (STAR-метод)",
        "phrase": "Tell me about a time when...",
        "criteria": {
            "argumentation": "Нужна конкретная ситуация: где, когда, что делал, какой результат.",
            "vocabulary": "\"I managed...\", \"I was responsible for...\", \"The outcome was...\"",
            "grammar": "Present Perfect для опыта, Past Simple для конкретных ситуаций.",
        },
    },
    "philosopher": {
        "name": "🧙 Leo the Sage",
        "full_name": "Leo — The Sage",
        "desc": "Почти никогда не говорит прямо. Отвечает вопросом. Заставляет думать.",
        "style": "задавай глубокие философские вопросы, уводи разговор к глобальным смыслам",
        "phrase": "What makes a good life?",
        "criteria": {
            "argumentation": "Нужна глубина: почему ты так думаешь, к чему это ведёт.",
            "vocabulary": "\"I tend to believe...\", \"It seems to me...\", \"One could argue...\"",
            "grammar": "Условные конструкции: \"If we consider...\", \"It might be that...\"",
        },
    },
    "devil_advocate": {
        "name": "😈 Victor the Advocate",
        "full_name": "Victor — Devil's Advocate",
        "desc": "Всегда спорит. Даже если согласен. Учит защищать свою позицию.",
        "style": "всегда спорь, находи слабые места в аргументах",
        "phrase": "What if you're wrong?",
        "criteria": {
            "argumentation": "Нужно защищать позицию до конца, не сдаваясь при давлении.",
            "vocabulary": "\"I strongly disagree...\", \"That's not necessarily true...\"",
            "grammar": "Модальные глаголы уверенности: must, cannot, should.",
        },
    },
}

# Бейджи/достижения
BADGES = {
    "first_debate": {"name": "🏆 Первый бой", "description": "Завершил первый раунд с персонажем"},
    "grammar_master": {"name": "📚 Грамматический мастер", "description": "Грамматика выше 90%"},
    "wordsmith": {"name": "🗣️ Мастер слова", "description": "Словарный запас выше 90%"},
    "marathoner": {"name": "🏃 Марафонец", "description": "10+ ответов за один раунд"},
    "all_characters": {"name": "🎭 Коллекционер", "description": "Сыграл со всеми персонажами"},
    "high_scorer": {"name": "🔥 На вершине", "description": "Средний балл за раунд выше 85"},
}
