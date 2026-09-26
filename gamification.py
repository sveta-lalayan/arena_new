"""
Геймификация ARENA: победа/поражение по 10 критериям, подбор персонажа,
скилл-прогресс, титулы, достижения.

Победа в бою = 50% «насколько персонаж убеждён» + 50% средний балл по 10 критериям
(языковые критерии оцениваются ОТНОСИТЕЛЬНО уровня игрока — сильный игрок любого
уровня может выиграть).

Система баллов/игровых уровней (🌱→🏆) и система квестов были в коде, но нигде
не подключены к реальному потоку (total_points никогда не увеличивался, у квестов
не было таблицы в БД) — сознательно убраны, чтобы не путать пользователя мёртвыми
цифрами. Фокус — на качестве самого дебрифа и ответов персонажей.
"""
import database as db
from config import WIN_SCORE_THRESHOLD, MIN_ROUNDS_TO_WIN
from game_data import (
    BADGES, PERSONALITIES, ALL_CRITERIA, COMMUNICATION_SKILLS, SKILL_TO_PERSONALITY,
)

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


# ---------- Скилл-прогресс ----------

def calculate_skill_delta(conviction: int, weapons_used: int,
                          is_nemesis: bool = False, won: bool = False) -> int:
    delta = round(max(0, min(100, 100 - conviction)) / 4)
    delta += weapons_used * 3
    if won:
        delta += 10
    if is_nemesis:
        delta = round(delta * 1.5)
    return max(3, min(delta, 70))


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
    conviction: int = 70, mistakes: list | None = None,
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
    _try("nemesis_slayer", is_nemesis and won)
    _try("full_convince", conviction <= 5)

    stats = db.get_user_stats(telegram_id)
    _try("all_characters", len(stats["unique_personalities"]) >= len(PERSONALITIES))
    _try("high_scorer", bool(stats.get("avg_score")) and stats["avg_score"] >= 85)
    return unlocked


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