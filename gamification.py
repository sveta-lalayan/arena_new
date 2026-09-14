"""
Геймификация ARENA: баллы, игровые уровни, скилл-прогресс, квесты, титулы,
достижения, профиль, мягкая адаптация уровня персонажей под участника.

Всё завязано на персонализацию: чем точнее игрок бьёт по своим слабым
местам (использует "оружие", выполняет квест, побеждает немезиду), тем
больше баллов и скилл-прогресса он получает — а не просто за количество
раундов.
"""
import random

import database as db
from game_data import BADGES, PERSONALITIES, ARENA_BEHAVIOURS

PLAYER_LEVELS = [
    {"name": "🌱 Новичок", "min_points": 0},
    {"name": "⚔️ Искатель", "min_points": 100},
    {"name": "🔥 Боец", "min_points": 300},
    {"name": "🧠 Мастер", "min_points": 600},
    {"name": "🏆 Легенда", "min_points": 1000},
]

# ---------- Баллы за бой ----------

POINTS_PER_ROUND = 6            # база за каждый раунд диалога
CONVICTION_BONUS_MAX = 40       # максимум баллов за то, что персонаж "сдался"
POINTS_PER_WEAPON = 6           # за каждое использованное оружие из арсенала
QUEST_BONUS = 25
FIRST_DAILY_BONUS = 10
NEW_CHARACTER_BONUS = 15
NEMESIS_BONUS = 30
MAX_POINTS_PER_BATTLE = 220


def calculate_points(
    rounds_completed: int,
    conviction: int,
    weapons_used: int,
    quest_done: bool,
    mistakes_count: int,
    is_first_daily: bool = False,
    is_new_character: bool = False,
    is_nemesis: bool = False,
) -> int:
    """
    conviction: 0 = персонаж полностью убеждён (лучший результат),
                100 = совсем не убеждён.
    Баллы построены так, чтобы САМЫМ весомым фактором было именно то,
    насколько убедительно и целенаправленно (через оружие) прошёл бой,
    а не просто число раундов.
    """
    points = rounds_completed * POINTS_PER_ROUND

    convinced_pct = max(0, min(100, 100 - conviction))
    points += round(convinced_pct * (CONVICTION_BONUS_MAX / 100))

    points += weapons_used * POINTS_PER_WEAPON

    if quest_done:
        points += QUEST_BONUS
    if is_first_daily:
        points += FIRST_DAILY_BONUS
    if is_new_character:
        points += NEW_CHARACTER_BONUS
    if is_nemesis and conviction <= 30:
        points += NEMESIS_BONUS

    # Ошибки не наказываем баллами (мы их и так собираем в словарь для
    # заучивания) — штрафовать за попытки использовать язык контрпродуктивно.
    return max(0, min(points, MAX_POINTS_PER_BATTLE))


def calculate_skill_delta(conviction: int, weapons_used: int, quest_done: bool, is_nemesis: bool = False) -> int:
    """
    Прирост очков скилла (0..1000 шкала на скилл), который качается у
    персонажа, отвечающего за слабый навык игрока (PERSONALITY_TO_SKILL).
    """
    convinced_pct = max(0, min(100, 100 - conviction))
    delta = round(convinced_pct / 4)          # 0..25
    delta += weapons_used * 3                 # использование оружия = целевая тренировка слабого места
    if quest_done:
        delta += 15
    if is_nemesis:
        delta = round(delta * 1.5)
    return max(3, min(delta, 60))


def get_player_level(total_points: int) -> dict:
    current = PLAYER_LEVELS[0]
    next_level = None
    for i, lvl in enumerate(PLAYER_LEVELS):
        if total_points >= lvl["min_points"]:
            current = lvl
            if i < len(PLAYER_LEVELS) - 1:
                next_level = PLAYER_LEVELS[i + 1]
    return {
        "current": current,
        "next": next_level,
        "points_to_next": next_level["min_points"] - total_points if next_level else None,
    }


# ---------- Квесты (персонализированные под слабый скилл/поведение) ----------

QUEST_BUILDERS = {
    "weapon": lambda skill, behaviour: {
        "type": "weapon",
        "description": "Используй минимум 3 предмета из арсенала за один бой.",
        "target": 3,
        "skill_bonus": skill,
    },
    "clean": lambda skill, behaviour: {
        "type": "clean",
        "description": "Заверши бой, набрав не больше 1 ошибки в словаре/грамматике.",
        "target": 1,
        "skill_bonus": skill,
    },
    "skill": lambda skill, behaviour: {
        "type": "skill",
        "description": f"Победи персонажа, который качает твой слабый навык ({skill}) — доведи убеждённость ниже 30%.",
        "target": 1,
        "skill_bonus": skill,
    },
    "behaviour": lambda skill, behaviour: {
        "type": "behaviour",
        "description": f"Проведи бой в стиле, обратном твоему обычному ({ARENA_BEHAVIOURS.get(behaviour, behaviour)}).",
        "target": 1,
        "skill_bonus": skill,
    },
}


def generate_quest(analysis: dict) -> dict:
    """
    Генерирует персональный еженедельный квест на основе разбора Храма
    (analyze_first_encounter): опирается на слабый скилл и поведенческий стиль.
    """
    weakest_skill = analysis.get("weakest_skill", "argumentation")
    behaviour = analysis.get("behaviour", "explorer")
    quest_type = random.choice(list(QUEST_BUILDERS.keys()))
    return QUEST_BUILDERS[quest_type](weakest_skill, behaviour)


# ---------- Титулы по поведенческому стилю ----------

BEHAVIOUR_TITLES = {
    "analyst":   ["Начинающий аналитик", "Логик", "Стратег", "Мастер логики", "Архитектор мысли"],
    "challenger": ["Спорщик", "Боец", "Провокатор", "Несгибаемый", "Разрушитель аргументов"],
    "explorer":  ["Собеседник", "Искатель", "Дипломат", "Проводник разговора", "Мастер контакта"],
    "precise":   ["Лаконичный", "Точный", "Снайпер слова", "Хирург аргумента", "Мастер краткости"],
    "defender":  ["Щит", "Оборонец", "Несокрушимый", "Крепость", "Непробиваемый"],
}


def get_title(behaviour: str, rank: int = 1) -> str:
    titles = BEHAVIOUR_TITLES.get(behaviour, ["Игрок ARENA"])
    idx = max(0, min(rank - 1, len(titles) - 1))
    return titles[idx]


# ---------- Оценка результата боя (для UI) ----------

def _conviction_stars(conviction: int) -> tuple[str, str]:
    """
    conviction: 0 = персонаж полностью убеждён, 100 = совсем не убеждён.
    Возвращает (звёзды, короткий текст результата).
    """
    convinced_pct = max(0, min(100, 100 - conviction))
    if convinced_pct >= 80:
        return "⭐⭐⭐⭐⭐", "Полная победа! Ты его переубедил."
    if convinced_pct >= 60:
        return "⭐⭐⭐⭐", "Убедительная победа."
    if convinced_pct >= 40:
        return "⭐⭐⭐", "Небольшой перевес в твою пользу."
    if convinced_pct >= 20:
        return "⭐⭐", "Ты сдвинул его с места, но немного."
    return "⭐", "Он остался при своём мнении. Попробуй ещё раз."


# ---------- Достижения ----------

def check_and_unlock_achievements(
    telegram_id: int,
    personality: str,
    rounds: int,
    scores: dict,
    conviction: int = 70,
    quest_done: bool = False,
    mistakes: list | None = None,
    is_nemesis: bool = False,
    is_rematch: bool = False,
    prev_defeated: bool = False,
) -> list[str]:
    unlocked = []
    mistakes = mistakes or []

    if db.unlock_achievement(telegram_id, "first_debate"):
        unlocked.append("first_debate")

    if scores.get("grammar", 0) >= 90 and db.unlock_achievement(telegram_id, "grammar_master"):
        unlocked.append("grammar_master")

    if scores.get("vocabulary", 0) >= 90 and db.unlock_achievement(telegram_id, "wordsmith"):
        unlocked.append("wordsmith")

    if rounds >= 10 and db.unlock_achievement(telegram_id, "marathoner"):
        unlocked.append("marathoner")

    if quest_done and db.unlock_achievement(telegram_id, "quest_master"):
        unlocked.append("quest_master")

    if is_nemesis and conviction <= 30 and db.unlock_achievement(telegram_id, "nemesis_slayer"):
        unlocked.append("nemesis_slayer")

    if conviction <= 5 and db.unlock_achievement(telegram_id, "full_convince"):
        unlocked.append("full_convince")

    stats = db.get_user_stats(telegram_id)
    if len(stats["unique_personalities"]) >= len(PERSONALITIES) and db.unlock_achievement(telegram_id, "all_characters"):
        unlocked.append("all_characters")

    if stats.get("avg_score") and stats["avg_score"] >= 85 and db.unlock_achievement(telegram_id, "high_scorer"):
        unlocked.append("high_scorer")

    return unlocked


def format_profile(telegram_id: int, first_name: str) -> str:
    stats = db.get_user_stats(telegram_id)
    level_info = get_player_level(stats["total_points"])
    skills = db.get_all_skills(telegram_id)

    text = f"""
👤 <b>{first_name}</b>
"""
    if stats.get("title"):
        text += f"🎖️ {stats['title']}\n"

    text += (
        f"\n📊 Баллы: {stats['total_points']}\n"
        f"🏅 Уровень: {level_info['current']['name']}\n"
    )
    if level_info["next"]:
        text += f"До {level_info['next']['name']}: {level_info['points_to_next']} баллов\n"

    text += (
        f"\n🎮 Боёв сыграно: {stats['games_played']}\n"
        f"🎭 Персонажей встречено: {len(stats['unique_personalities'])} из {len(PERSONALITIES)}\n"
        f"📈 Средний балл: {stats['avg_score'] or '—'}%\n"
        f"🏆 Достижения: {len(stats['achievements'])} / {len(BADGES)}\n"
        f"⚡ Побед над немезидой: {stats.get('nemesis_defeated', 0)}\n"
    )

    if skills:
        text += "\n🧩 <b>Скиллы:</b>\n"
        for skill, data in sorted(skills.items(), key=lambda kv: -kv[1]["points"]):
            text += f"  • {skill}: {data['points']} очк. (ранг {data['rank']})\n"

    if stats.get("latest_strength") or stats.get("latest_growth"):
        text += (
            f"\n✅ <b>Сильная сторона:</b> {stats.get('latest_strength', '—')}\n"
            f"🎯 <b>Зона роста:</b> {stats.get('latest_growth', '—')}\n"
        )

    if stats.get("latest_growth_plan"):
        text += f"\n🗺️ <b>План на следующие 10 раундов:</b>\n{stats['latest_growth_plan']}\n"

    quest = db.get_active_quest(telegram_id)
    if quest:
        text += f"\n🎯 <b>Текущий квест:</b> {quest['description']}\n"

    vocab = db.get_vocabulary_to_learn(telegram_id, limit=8)
    if vocab:
        text += "\n📚 <b>Слова для заучивания</b> (были использованы неправильно):\n"
        for v in vocab:
            text += f"  • {v['wrong']} → <b>{v['correct']}</b>\n"

    return text


def format_achievements(telegram_id: int) -> str:
    stats = db.get_user_stats(telegram_id)
    unlocked = set(stats["achievements"])
    if not unlocked:
        return "🏆 <b>Достижения</b>\n\nПока нет разблокированных достижений. Сыграй несколько игр, чтобы открыть их!"
    lines = ["🏆 <b>Достижения</b>\n"]
    for key, badge in BADGES.items():
        status = "✅" if key in unlocked else "⬜"
        lines.append(f"{status} {badge['name']} — {badge['description']}")
    return "\n".join(lines)


# ---------- Мягкая адаптация уровня персонажей под участника ----------

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def adapt_level(current_level: str, avg_score: float | None) -> str:
    if avg_score is None or current_level not in LEVEL_ORDER:
        return current_level
    idx = LEVEL_ORDER.index(current_level)
    if avg_score >= 82 and idx < len(LEVEL_ORDER) - 1:
        return LEVEL_ORDER[idx + 1]
    if avg_score <= 45 and idx > 0:
        return LEVEL_ORDER[idx - 1]
    return current_level