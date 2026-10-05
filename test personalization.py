"""
Запуск:  python -m unittest discover -s tests -v
LLM подменяется заглушками, БД — временный файл. Сетевых вызовов нет.
"""
import json
import os
import random
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

_TMP = tempfile.mkdtemp()
os.environ.update({"DB_PATH": os.path.join(_TMP, "t.db"), "BOT_TOKEN": "1:x", "OPENAI_API_KEY": "x"})

import ai  # noqa: E402
import database as db  # noqa: E402
import personalization as pz  # noqa: E402

_uid = [1000]


def new_user() -> int:
    _uid[0] += 1
    db.get_or_create_user(_uid[0], "u", "U")
    return _uid[0]


def age(table: str, col: str, uid: int, days: int):
    ts = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db.get_conn() as conn:
        conn.execute(f"UPDATE {table} SET {col} = ? WHERE telegram_id = ?", (ts, uid))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def setUp(self):
        self._ask_json, self._ask = ai._ask_json, ai._ask

    def tearDown(self):
        ai._ask_json, ai._ask = self._ask_json, self._ask

    def stub_signals(self, topics=(), patterns=()):
        ai._ask_json = lambda *a, **k: {"topics": list(topics), "patterns": list(patterns)}


LINES = ["I think remote work is better.", "Because it is better for people.",
         "I said it is better, it is simply better.", "Okay."]


class TestMemory(Base):
    def test_topics_are_semantic_clusters_not_raw_words(self):
        u = new_user()
        self.stub_signals(topics=[{"cluster": "Technology & AI", "example": "AI startups"},
                                  {"cluster": "weather", "example": "sunny"}])      # чужой кластер -> отброшен
        pz.record_session(u, "free_talk", LINES, "english")
        self.stub_signals(topics=[{"cluster": "technology & ai", "example": "artificial intelligence"}])
        pz.record_session(u, "battle", LINES, "english")
        cl = db.get_interest_clusters(u)
        self.assertEqual(len(cl), 1)                                    # один кластер, не пять «интересов»
        self.assertEqual((cl[0]["cluster"], cl[0]["count"]), ("Technology & AI", 2))
        self.assertEqual(set(cl[0]["examples"]), {"AI startups", "artificial intelligence"})

    def test_unsupported_pattern_quote_is_dropped(self):
        u = new_user()
        self.stub_signals(patterns=[{"id": "repeats_claim", "example": "I never said this sentence"},
                                    {"id": "made_up_id", "example": "it is simply better"}])
        pz.record_session(u, "battle", LINES, "english")
        self.assertEqual(db.get_patterns(u), [])

    def test_free_talk_feeds_memory(self):
        u = new_user()
        self.stub_signals(patterns=[{"id": "repeats_claim", "example": "it is simply better"}])
        pz.record_session(u, "free_talk", LINES, "english")
        self.assertEqual(db.get_patterns(u)[0]["status"], "hypothesis")

    def test_too_few_messages_give_no_pattern(self):
        u = new_user()
        self.stub_signals(patterns=[{"id": "repeats_claim", "example": "it is simply better"}])
        pz.record_session(u, "free_talk", LINES[:2], "english")
        self.assertEqual(db.get_patterns(u), [])

    def test_pattern_lifecycle(self):
        u = new_user()
        obs = lambda pid, **kw: db.observe_pattern(u, pid, "argumentation", kw.get("kind", "growth"),
                                                    "x", kw.get("counter_of"))
        self.assertEqual(obs("repeats_claim"), "hypothesis")            # одно наблюдение — не слабость
        self.assertEqual(db.get_patterns(u, ("confirmed", "improving")), [])
        self.assertEqual(obs("repeats_claim"), "emerging")
        self.assertEqual(obs("repeats_claim"), "confirmed")             # повторяется -> подтверждён
        counter = lambda: obs("develops_argument", kind="strength", counter_of="repeats_claim")
        counter()
        self.assertEqual(self._status(u, "repeats_claim"), "improving")
        counter(); counter()
        self.assertEqual(self._status(u, "repeats_claim"), "resolved")
        obs("repeats_claim")                                            # откат
        self.assertEqual(self._status(u, "repeats_claim"), "confirmed")

    @staticmethod
    def _status(u, pid):
        return next(p["status"] for p in db.get_patterns(u) if p["pattern_id"] == pid)


class TestDebriefAndNotifications(Base):
    def _debrief(self, up):
        ai._ask_json = lambda *a, **k: {"result_line": "r", "language_upgrade": up, "next_target": "evidence"}
        dlg = [{"speaker": "User", "text": "I think sunny weather is better because people feel happier."},
               {"speaker": "Adams", "text": "Why?"}]
        return ai.generate_battle_debrief("U", "english", "B1", "professor", "weather", "m", True, 70, 30,
                                          {"clarity": 60}, dlg)

    def test_language_upgrade_must_quote_real_words(self):
        good = {"said": "sunny weather is better", "better": "sunny weather tends to lift people's mood",
                "why": "hedged and more precise"}
        self.assertEqual(self._debrief(good)["language_upgrade"]["better"], good["better"])
        self.assertIsNone(self._debrief({**good, "said": "something they never said"})["language_upgrade"])
        self.assertIsNone(self._debrief(None)["language_upgrade"])      # нет осмысленного апгрейда -> пропуск

    def test_debrief_is_stored_with_session(self):
        u = new_user()
        sid = db.save_game_session(u, "professor", "en", "B1", "weather", 3, {"clarity": 50}, 0, mission="m")
        db.save_session_debrief(sid, {"cost": "repeated the claim", "next_target": "evidence", "junk": 1})
        last = db.get_last_session(u)
        self.assertEqual(last["debrief"], {"cost": "repeated the claim", "next_target": "evidence"})

    def test_notification_history(self):
        u = new_user()
        n1 = db.log_notification(u, "interest_hook", "t1", interest="Travel & places")
        db.mark_previous_unclicked_dismissed(u)
        n2 = db.log_notification(u, "arsenal_hook", "t2", arsenal_item="reframe")
        db.mark_notification_clicked(n2, u)
        rows = {r["id"]: r for r in db.get_recent_notifications(u)}
        self.assertEqual((rows[n1]["dismissed"], rows[n1]["clicked"]), (1, 0))
        self.assertEqual((rows[n2]["dismissed"], rows[n2]["clicked"]), (0, 1))

    def test_generic_reminder_is_rejected(self):
        sel = {"type": "interest_hook", "facts": ["Interest area: Travel."]}
        ai._ask = lambda *a, **k: "Ready for your daily Battle?"
        self.assertIsNone(ai.generate_personalized_reminder(sel, "U", "english"))
        ai._ask = lambda *a, **k: "You keep circling back to Lisbon. Would you really move there?"
        self.assertIn("Lisbon", ai.generate_personalized_reminder(sel, "U", "english"))


class TestReminderSelection(Base):
    def test_no_data_means_neutral_fallback(self):                       # сценарий: данных нет
        self.assertIsNone(pz.select_reminder(new_user()))

    def test_temple_only(self):                                          # сценарий A
        u = new_user()
        self.stub_signals(topics=[{"cluster": "Travel & places", "example": "Lisbon"}])
        pz.record_session(u, "temple", LINES, "english")
        sel = pz.select_reminder(u, random.Random(1))
        self.assertIn(sel["type"], {"interest_hook", "provocative_question"})
        self.assertEqual(sel["refs"]["interest"], "Travel & places")
        self.assertIn("Lisbon", " ".join(sel["facts"]))

    def test_hypotheses_are_not_used_in_reminders(self):
        u = new_user()
        db.observe_pattern(u, "claims_without_evidence", "evidence", "growth", "x")      # 1 наблюдение
        self.assertIsNone(pz.select_reminder(u))

    def test_variety_no_repeats(self):                                   # сценарии H, E
        u = new_user()
        self.stub_signals(topics=[{"cluster": "Travel & places", "example": "Lisbon"},
                                  {"cluster": "Technology & AI", "example": "AI startups"}])
        pz.record_session(u, "free_talk", LINES, "english")
        sid = db.save_game_session(u, "professor", "en", "B1", "remote work", 3, {"clarity": 50}, 0)
        db.save_session_debrief(sid, {"cost": "repeated the claim", "next_target": "evidence"})
        db.unlock_tool(u, "reframe")
        db.add_level_snapshot(u, "B2", "test")

        rng, seen_types, seen_interests = random.Random(7), [], []
        for _ in range(4):
            sel = pz.select_reminder(u, rng)
            if not sel:
                break
            seen_types.append(sel["type"])
            r = sel["refs"]
            db.log_notification(u, sel["type"], "t", r["interest"], r["pattern"], r["battle"], r["arsenal"])
            if r["interest"]:
                seen_interests.append(r["interest"].lower())
        self.assertGreaterEqual(len(seen_types), 3)
        for a, b in zip(seen_types, seen_types[1:]):
            self.assertNotEqual(a, b)                                    # один тип два раза подряд — нет
        self.assertEqual(len(seen_interests), len(set(seen_interests)))  # один интерес не повторяется

    def test_old_activity_has_no_fake_recency(self):                     # сценарий G
        u = new_user()
        self.stub_signals(topics=[{"cluster": "Travel & places", "example": "Lisbon"}])
        pz.record_session(u, "free_talk", LINES, "english")
        age("user_interest_clusters", "last_seen_at", u, 30)
        sel = pz.select_reminder(u, random.Random(1))
        self.assertNotEqual(sel["type"], "continuation")                 # «продолжение» только для свежего (≤3 дней)
        self.assertIn("days ago: 30", " ".join(sel["facts"]))            # LLM знает реальную давность

    def test_confirmed_pattern_drives_challenge(self):                   # сценарий J
        u = new_user()
        for _ in range(3):
            db.observe_pattern(u, "repeats_claim", "argumentation", "growth", "x")
        sid = db.save_game_session(u, "devil_advocate", "en", "B1", "t", 3, {"argumentation": 40}, 0)
        db.save_session_debrief(sid, {"next_target": "argumentation"})
        db.log_notification(u, "continuation", "t")
        sel = next(s for s in (pz.select_reminder(u, random.Random(i)) for i in range(30))
                   if s and s["type"] == "challenge_hook")
        self.assertEqual(sel["refs"]["pattern"], "repeats_claim")


class TestLocalization(unittest.TestCase):
    def test_every_pattern_and_criterion_is_localised(self):
        from config import SUPPORTED_LANGUAGES
        crit = {"grammar", "vocabulary", "fluency", "naturalness", "clarity", "argumentation",
                "adaptability", "persuasion", "evidence", "control"}
        for lang in SUPPORTED_LANGUAGES:
            with open(f"locales/{lang}.json", encoding="utf-8") as fh:
                d = json.load(fh)
            self.assertTrue(set(pz.PATTERN_CATALOG) <= set(d["PATTERNS"]), lang)
            self.assertTrue(crit <= set(d["CRITERIA"]), lang)
            for k in ("LANGUAGE_UPGRADE", "YOU_SAID", "BETTER"):
                self.assertIn(k, d["DEBRIEF"], lang)
            for k in ("COMMUNICATION", "LANGUAGE"):
                self.assertIn(k, d["MY_ARENA"], lang)


if __name__ == "__main__":
    unittest.main()