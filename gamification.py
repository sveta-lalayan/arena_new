"""
Геймификация ARENA: баллы, игровые уровни, победа/поражение по 10 критериям,
подбор персонажа, скилл-прогресс, квесты, титулы, достижения, профиль.

Победа в бою = 50% «насколько персонаж убеждён» + 50% средний балл по 10 критериям
(языковые критерии оцениваются ОТНОСИТЕЛЬНО уровня игрока — сильный игрок любого
уровня может выиграть).
"""
import random
from html import escape

import database as db
from config import WIN_SCORE_THRESHOLD, MIN_ROUNDS_TO_WIN
from game_data import (
    BADGES, PERSONALITIES, ARENA_BEHAVIOURS, ALL_CRITERIA, LANGUAGE_CRITERIA,
    COMMUNICATION_SKILLS, CRITERIA_LABELS_RU, SKILL_TO_PERSONALITY, SKILL_LABELS_RU,
)

PLAYER_LEVELS = [
    {"name": "🌱 Новичок", "min_points": 0},
    {"name": "⚔️ Искатель", "min_points": 100},
    {"name": "🔥 Боец", "min_points": 300},
    {"name": "🧠 Мастер", "min_points": 600},
    {"name": "🏆 Легенда", "min_points": 1000},
]

# ---------- Победа / поражение ----------

def battle_result(criteria: dict, conviction: int, rounds: int, early_win: bool = False) -> dict:
    """
    criteria: 10 оценок 0..100. conviction: 0 = персонаж убеждён, 100 = не убеждён.
    """
    vals = [max(0, min(100, int(criteria.get(k, 50)))) for k in ALL_CRITERIA]
    overall = round(sum(vals) / len(vals))
    convinced = max(0, min(100, 100 - conviction))
    win_score = round(0.5 * convinced + 0.5 * overall)
    won = early_win or (win_score >= WIN_SCORE_THRESHOLD and rounds >= MIN_ROUNDS_TO_WIN)
    return {"overall": overall, "win_score": win_score, "won": bool(won), "convinced": convinced}


def result_stars(win_score: int) -> str:
    n = 5 if win_score >= 85 else 4 if win_score >= 70 else 3 if win_score >= 55 else 2 if win_score >= 40 else 1
    return "⭐" * n


# ---------- Баллы за бой ----------

POINTS_PER_ROUND = 6
CONVICTION_BONUS_MAX = 40
POINTS_PER_WEAPON = 6
QUEST_BONUS = 25
FIRST_DAILY_BONUS = 10
NEW_CHARACTER_BONUS = 15
NEMESIS_BONUS = 30
WIN_BONUS = 30
MAX_POINTS_PER_BATTLE = 250


def calculate_points(
    rounds_completed: int, conviction: int, weapons_used: int, quest_done: bool,
    mistakes_count: int, is_first_daily: bool = False, is_new_character: bool = False,
    is_nemesis: bool = False, won: bool = False,
) -> int:
    points = rounds_completed * POINTS_PER_ROUND
    points += round(max(0, min(100, 100 - conviction)) * (CONVICTION_BONUS_MAX / 100))
    points += weapons_used * POINTS_PER_WEAPON
    if won:
        points += WIN_BONUS
    if quest_done:
        points += QUEST_BONUS
    if is_first_daily:
        points += FIRST_DAILY_BONUS
    if is_new_character:
        points += NEW_CHARACTER_BONUS
    if is_nemesis and won:
        points += NEMESIS_BONUS
    # Ошибки баллами не наказываем — они идут в словарь для заучивания.
    return max(0, min(points, MAX_POINTS_PER_BATTLE))


def calculate_skill_delta(conviction: int, weapons_used: int, quest_done: bool,
                          is_nemesis: bool = False, won: bool = False) -> int:
    delta = round(max(0, min(100, 100 - conviction)) / 4)
    delta += weapons_used * 3
    if won:
        delta += 10
    if quest_done:
        delta += 15
    if is_nemesis:
        delta = round(delta * 1.5)
    return max(3, min(delta, 70))


def get_player_level(total_points: int) -> dict:
    current, next_level = PLAYER_LEVELS[0], None
    for i, lvl in enumerate(PLAYER_LEVELS):
        if total_points >= lvl["min_points"]:
            current = lvl
            next_level = PLAYER_LEVELS[i + 1] if i < len(PLAYER_LEVELS) - 1 else None
    return {
        "current": current,
        "next": next_level,
        "index": PLAYER_LEVELS.index(current),
        "points_to_next": next_level["min_points"] - total_points if next_level else None,
    }


# ---------- Подбор персонажа на день ----------

def weakest_criterion(criteria: dict, keys=None) -> str | None:
    keys = keys or ALL_CRITERIA
    known = {k: criteria[k] for k in keys if k in criteria}
    return min(known, key=known.get) if known else None


def pick_next_personality(user_id: int) -> str:
    """
    Персонаж следующего боя — тот, кто качает СЕЙЧАС самый слабый communication-скилл.
    Каждый 4-й бой — немезида (если ещё не побеждена). Одного и того же
    персонажа два дня подряд не даём, если второй по слабости навык почти так же слаб.
    """
    criteria = db.get_criteria(user_id)
    games = db.count_battles(user_id)
    nemesis = db.get_nemesis(user_id)
    if nemesis and not nemesis["defeated"] and games > 0 and games % 4 == 3:
        return nemesis["personality"]

    ranked = sorted(COMMUNICATION_SKILLS, key=lambda s: criteria.get(s, 50))
    first, second = ranked[0], ranked[1]
    last = db.get_last_personality(user_id)
    if (SKILL_TO_PERSONALITY[first] == last
            and criteria.get(second, 50) - criteria.get(first, 50) <= 10):
        return SKILL_TO_PERSONALITY[second]
    return SKILL_TO_PERSONALITY[first]


# ---------- Квесты ----------

QUEST_BUILDERS = {
    "weapon": lambda skill, behaviour: {
        "type": "weapon",
        "description": "Используй минимум 3 слова из арсенала за один бой.",
        "target": 3,
        "skill_bonus": skill,
    },
    "clean": lambda skill, behaviour: {
        "type": "clean",
        "description": "Заверши бой, допустив не больше 1 языковой ошибки.",
        "target": 1,
        "skill_bonus": skill,
    },
    "skill": lambda skill, behaviour: {
        "type": "skill",
        "description": f"Победи персонажа, который качает твой слабый навык ({SKILL_LABELS_RU.get(skill, skill)}).",
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
    weakest = analysis.get("weakest_skill") or "argumentation"
    behaviour = analysis.get("behaviour") or "explorer"
    return QUEST_BUILDERS[random.choice(list(QUEST_BUILDERS))](weakest, behaviour)


def ensure_quest(user_id: int):
    """Если активного квеста нет (выполнен или истёк) — выдаём новый."""
    if db.get_active_quest(user_id):
        return
    analysis = dict(db.get_latest_arena_analysis(user_id) or {})
    weakest = weakest_criterion(db.get_criteria(user_id), COMMUNICATION_SKILLS)
    if weakest:
        analysis["weakest_skill"] = weakest
    q = generate_quest(analysis)
    db.set_quest(user_id, q["type"], q["description"], q["target"], q["skill_bonus"])


def evaluate_quest(quest: dict | None, used_weapons: int, personality: str, won: bool,
                   mistakes_count: int, judged_by_ai: bool) -> bool:
    if not quest:
        return False
    qtype = quest["type"]
    if qtype == "weapon":
        return used_weapons >= max(1, quest.get("target", 3))
    if qtype == "clean":
        return mistakes_count <= 1
    if qtype == "skill":
        return won and personality == SKILL_TO_PERSONALITY.get(quest.get("skill_bonus"))
    return bool(judged_by_ai)


# ---------- Титулы ----------

BEHAVIOUR_TITLES = {
    "analyst": ["Начинающий аналитик", "Логик", "Стратег", "Мастер логики", "Архитектор мысли"],
    "challenger": ["Спорщик", "Боец", "Провокатор", "Несгибаемый", "Разрушитель аргументов"],
    "explorer": ["Собеседник", "Искатель", "Дипломат", "Проводник разговора", "Мастер контакта"],
    "precise": ["Лаконичный", "Точный", "Снайпер слова", "Хирург аргумента", "Мастер краткости"],
    "defender": ["Щит", "Оборонец", "Несокрушимый", "Крепость", "Непробиваемый"],
}


def get_title(behaviour: str, rank: int = 1) -> str:
    titles = BEHAVIOUR_TITLES.get(behaviour, ["Игрок ARENA"])
    return titles[max(0, min(rank - 1, len(titles) - 1))]


# ---------- Достижения ----------

def check_and_unlock_achievements(
    telegram_id: int, personality: str, rounds: int, scores: dict,
    conviction: int = 70, quest_done: bool = False, mistakes: list | None = None,
    is_nemesis: bool = False, is_rematch: bool = False, prev_defeated: bool = False,
    won: bool = False,
) -> list[str]:
    unlocked = []

    def _try(key, cond=True):
        if cond and db.unlock_achievement(telegram_id, key):
            unlocked.append(key)

    _try("first_debate")
    _try("first_victory", won)
    _try("grammar_master", scores.get("grammar", 0) >= 90)
    _try("wordsmith", scores.get("vocabulary", 0) >= 90)
    _try("marathoner", rounds >= 10)
    _try("quest_master", quest_done)
    _try("nemesis_slayer", is_nemesis and won)
    _try("full_convince", conviction <= 5)

    stats = db.get_user_stats(telegram_id)
    _try("all_characters", len(stats["unique_personalities"]) >= len(PERSONALITIES))
    _try("high_scorer", bool(stats.get("avg_score")) and stats["avg_score"] >= 85)
    return unlocked


# ---------- Шкала и профиль ----------

def bar(value: int) -> str:
    filled = int(round(max(0, min(100, value)) / 10))
    return "█" * filled + "░" * (10 - filled)


def format_criteria_block(criteria: dict) -> str:
    """Шкала по 10 критериям (для итогов боя и профиля)."""
    def rows(keys):
        return [f"  {CRITERIA_LABELS_RU[k]:<16} {bar(criteria[k])} {criteria[k]}" for k in keys if k in criteria]
    lines = ["<b>ЯЗЫК</b>"] + rows(LANGUAGE_CRITERIA) + ["<b>КОММУНИКАЦИЯ</b>"] + rows(COMMUNICATION_SKILLS)
    return "<pre>" + "\n".join(l.replace("<b>", "").replace("</b>", "") for l in lines) + "</pre>"


def format_profile(telegram_id: int, first_name: str) -> str:
    stats = db.get_user_stats(telegram_id)
    level_info = get_player_level(stats["total_points"])
    criteria = db.get_criteria(telegram_id)
    skills = db.get_all_skills(telegram_id)
    cefr = db.get_current_level(telegram_id)

    text = f"🏛️ <b>Моя арена</b> — {escape(first_name or '')}\n"
    if stats.get("title"):
        text += f"🎖️ {escape(stats['title'])}\n"

    text += f"\n📊 Баллы: {stats['total_points']} · {level_info['current']['name']}\n"
    if level_info["next"]:
        text += f"До {level_info['next']['name']}: {level_info['points_to_next']}\n"
    if cefr:
        text += f"🗣️ Уровень языка: <b>{cefr}</b>\n"

    games, wins = stats["games_played"], stats["wins"]
    text += (
        f"\n🎮 Боёв: {games} (🏆 {wins} / 💀 {games - wins})\n"
        f"🎭 Персонажей встречено: {len(stats['unique_personalities'])} из {len(PERSONALITIES)}\n"
        f"📈 Средний балл боя: {stats['avg_score'] if stats['avg_score'] is not None else '—'}\n"
        f"🏆 Достижения: {len(stats['achievements'])} / {len(BADGES)}\n"
        f"⚡ Побед над немезидой: {stats.get('nemesis_defeated', 0)}\n"
    )

    if criteria:
        text += "\n📐 <b>Твоя шкала (10 критериев)</b>\n" + format_criteria_block(criteria)
        best, worst = max(criteria, key=criteria.get), weakest_criterion(criteria)
        text += f"✅ <b>Круто:</b> {CRITERIA_LABELS_RU[best]} ({criteria[best]})\n"
        text += f"🎯 <b>Над чем работать:</b> {CRITERIA_LABELS_RU[worst]} ({criteria[worst]})"
        if worst in SKILL_TO_PERSONALITY:
            person = PERSONALITIES[SKILL_TO_PERSONALITY[worst]]
            text += f" — качает {escape(person['short_name'])}"
        text += "\n"

    text += "\n🎭 <b>Кто что тренирует</b>\n"
    for skill in COMMUNICATION_SKILLS:
        person = PERSONALITIES[SKILL_TO_PERSONALITY[skill]]
        data = skills.get(skill, {"points": 0, "rank": 1})
        text += f"  {escape(person['name'])} — {CRITERIA_LABELS_RU[skill].lower()} · {data['points']} XP (ранг {data['rank']})\n"

    if stats.get("latest_growth_plan"):
        text += f"\n💬 <b>Последний совет персонажа:</b>\n<i>{escape(stats['latest_growth_plan'])}</i>\n"

    quest = db.get_active_quest(telegram_id)
    if quest:
        text += f"\n🎯 <b>Квест недели:</b> {escape(quest['description'])}\n"

    vocab = db.get_vocabulary_to_learn(telegram_id, limit=5)
    if vocab:
        text += "\n📚 <b>Слова для заучивания:</b>\n"
        for v in vocab:
            text += f"  • {escape(v['wrong'])} → <b>{escape(v['correct'])}</b>\n"

    if db.has_battled_today(telegram_id):
        text += f"\n🗓️ Следующий бой через ~{int(db.cooldown_hours_left(telegram_id)) + 1} ч."
    else:
        text += "\n⚔️ Бой доступен прямо сейчас."
    return text


def format_achievements(telegram_id: int) -> str:
    stats = db.get_user_stats(telegram_id)
    unlocked = set(stats["achievements"])
    lines = ["🏆 <b>Достижения</b>\n"]
    for key, badge in BADGES.items():
        lines.append(f"{'✅' if key in unlocked else '⬜'} {badge['name']} — {badge['description']}")
    return "\n".join(lines)


# ---------- Мягкая адаптация CEFR-уровня ----------

LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def adapt_level(current_level: str, avg_score: float | None) -> str:
    """Общий балл считается ОТНОСИТЕЛЬНО уровня: стабильно ≥82 → уровень выше, ≤45 → ниже."""
    if avg_score is None or current_level not in LEVEL_ORDER:
        return current_level
    idx = LEVEL_ORDER.index(current_level)
    if avg_score >= 82 and idx < len(LEVEL_ORDER) - 1:
        return LEVEL_ORDER[idx + 1]
    if avg_score <= 45 and idx > 0:
        return LEVEL_ORDER[idx - 1]
    return current_level