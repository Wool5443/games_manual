"""First-run demo data and explicit seed regression checks on temporary SQLite files."""

import io
import runpy
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from games_manual_app import create_app
from games_manual_app.config import DEFAULT_AGE_OPTIONS, DEFAULT_GAME_TYPES, SCHEMA
from games_manual_app.db import close_db, get_db, init_db
from games_manual_app.demo_data import DEMO_AUTHOR_EMAIL, DEMO_GAMES, seed_demo_games
from games_manual_app.helpers import parse_multi_categories


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "games.db"
        patcher = patch("games_manual_app.db.DATABASE_PATH", self.database_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="demo-test-secret")

    def count_games(self, db):
        return db.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    def test_new_database_gets_ten_complete_games_and_no_accounts(self):
        with self.app.app_context():
            init_db()
            db = get_db()
            self.assertEqual(self.count_games(db), 10)
            rows = db.execute("SELECT * FROM games ORDER BY created_at").fetchall()
            for game in rows:
                self.assertEqual(game["created_by_email"], DEMO_AUTHOR_EMAIL)
                self.assertEqual(game["files_json"], "[]")
                self.assertEqual(game["updated_at"], game["created_at"])
                self.assertIn(game["age_category"], DEFAULT_AGE_OPTIONS)
                for category in parse_multi_categories(game["game_type"]):
                    self.assertIn(category, DEFAULT_GAME_TYPES)
                for field in ("title", "goal", "participants", "duration", "rules"):
                    self.assertTrue(game[field])
            self.assertEqual(len({row["created_at"] for row in rows}), 10)
            self.assertTrue(any(row["equipment"] for row in rows))
            self.assertTrue(any(not row["equipment"] for row in rows))
            for table in ("access_users", "invite_links"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_reinitialization_and_restart_do_not_duplicate_games(self):
        with self.app.app_context():
            init_db()
            original = [tuple(row) for row in get_db().execute("SELECT * FROM games ORDER BY id")]
            init_db()
            close_db(None)
            init_db()
            self.assertEqual(
                [tuple(row) for row in get_db().execute("SELECT * FROM games ORDER BY id")],
                original,
            )

    def test_existing_empty_database_is_not_automatically_seeded(self):
        with self.app.app_context():
            db = get_db()
            db.executescript(SCHEMA)
            init_db()
            self.assertEqual(self.count_games(db), 0)

    def test_deleted_games_do_not_return_after_restart(self):
        with self.app.app_context():
            init_db()
            db = get_db()
            db.execute("DELETE FROM games")
            db.commit()
            close_db(None)
            init_db()
            self.assertEqual(self.count_games(get_db()), 0)

    def test_existing_game_and_custom_reference_data_are_preserved(self):
        with self.app.app_context():
            db = get_db()
            db.executescript(SCHEMA)
            db.execute("INSERT INTO game_types (name) VALUES ('Своя категория')")
            db.execute("INSERT INTO age_categories (name) VALUES ('16+')")
            db.execute(
                """INSERT INTO games (
                    title, game_type, goal, participants, age_category,
                    duration, location, equipment, rules
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Своя игра", "Своя категория", "Цель", "10", "16+",
                 "10 минут", "Помещение", "", "Свои правила"),
            )
            db.commit()
            original = tuple(db.execute("SELECT * FROM games").fetchone())
            init_db()
            self.assertEqual(self.count_games(db), 1)
            self.assertEqual(tuple(db.execute("SELECT * FROM games").fetchone()), original)
            self.assertEqual([row[0] for row in db.execute("SELECT name FROM game_types")], ["Своя категория"])
            self.assertEqual([row[0] for row in db.execute("SELECT name FROM age_categories")], ["16+"])

    def test_explicit_seed_preserves_edits_and_uses_author_and_title(self):
        with self.app.app_context():
            db = get_db()
            db.executescript(SCHEMA)
            self.assertEqual(seed_demo_games(db), 10)
            db.execute("UPDATE games SET rules = 'Изменённые правила' WHERE id = 1")
            db.execute("UPDATE games SET created_by_email = 'another@example.test' WHERE id = 2")
            db.commit()
            self.assertEqual(seed_demo_games(db), 1)
            self.assertEqual(seed_demo_games(db), 0)
            self.assertEqual(self.count_games(db), 11)
            self.assertEqual(db.execute("SELECT rules FROM games WHERE id = 1").fetchone()[0],
                             "Изменённые правила")
            self.assertEqual(db.execute("SELECT created_by_email FROM games WHERE id = 2").fetchone()[0],
                             "another@example.test")

    def test_seed_rolls_back_all_games_on_insert_failure(self):
        with self.app.app_context():
            db = get_db()
            db.executescript(SCHEMA)
            # Reject the second demo insert, after the first has succeeded.
            db.executescript("""
                CREATE TRIGGER reject_second_game BEFORE INSERT ON games
                WHEN (SELECT COUNT(*) FROM games) = 1
                BEGIN SELECT RAISE(ABORT, 'test insert failure'); END;
            """)
            with self.assertRaises(sqlite3.IntegrityError):
                seed_demo_games(db)
            self.assertEqual(self.count_games(db), 0)
            db.execute("DROP TRIGGER reject_second_game")
            self.assertEqual(seed_demo_games(db), 10)

    def test_cli_fills_existing_empty_database_without_duplicates(self):
        with self.app.app_context():
            get_db().executescript(SCHEMA)
        script = Path(__file__).resolve().parents[1] / "scripts" / "seed_dummy.py"
        output = io.StringIO()
        with redirect_stdout(output):
            runpy.run_path(str(script), run_name="__main__")
            runpy.run_path(str(script), run_name="__main__")
        self.assertIn("Добавлено демонстрационных игр: 10. Всего игр: 10.", output.getvalue())
        self.assertIn("Добавлено демонстрационных игр: 0. Всего игр: 10.", output.getvalue())
        with self.app.app_context():
            self.assertEqual(self.count_games(get_db()), 10)

    def test_fresh_catalog_detail_search_equipment_and_date_sort(self):
        client = self.app.test_client()
        response = client.get("/games")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for game in DEMO_GAMES:
            self.assertIn(game["title"], html)
        html = client.get("/games?search=Бумажная+башня").get_data(as_text=True)
        self.assertIn("Бумажная башня", html)
        self.assertNotIn("Круг благодарности", html)
        html = client.get("/games?no_equipment=1").get_data(as_text=True)
        for game in DEMO_GAMES:
            if game["equipment"]:
                self.assertNotIn(game["title"], html)
            else:
                self.assertIn(game["title"], html)
        html = client.get("/games?sort=created_at&order=desc").get_data(as_text=True)
        positions = [html.index(game["title"]) for game in reversed(DEMO_GAMES)]
        self.assertEqual(positions, sorted(positions))
        response = client.get("/games/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(DEMO_GAMES[0]["rules"], response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
