"""View regression checks using a disposable database and synthetic users.

Run with: python -m unittest discover -s tests -v
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from games_manual_app import create_app
from games_manual_app.db import get_db, init_db


class ViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp_dir.cleanup)
        for target, value in (
            ("games_manual_app.db.DATABASE_PATH", Path(cls.temp_dir.name) / "games.db"),
            ("games_manual_app.access.ADMIN_EMAILS", {"admin@example.test"}),
        ):
            patcher = patch(target, value)
            patcher.start()
            cls.addClassCleanup(patcher.stop)
        cls.app = create_app()
        cls.app.config.update(TESTING=True, SECRET_KEY="test-only-secret")
        with cls.app.app_context():
            init_db()
            db = get_db()
            db.execute("INSERT INTO access_users (email, role) VALUES (?, ?)",
                       ("editor@example.test", "editor"))
            db.executemany(
                """INSERT INTO games (
                    title, game_type, goal, participants, age_category, duration,
                    location, equipment, rules, files_json, created_by_email,
                    created_by_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("Alpha <game>", "Бегалки, Командообразование", "Cooperation", "8–12",
                     "10+", "15 minutes", "Улица", "Ball", "Rules <stay escaped>",
                     '["rules.pdf"]', "editor@example.test", "Test Editor", "2026-01-02 03:04:00"),
                    ("Beta game", "Бодряк", "Warm up", "4–6", "7+", "5 minutes",
                     "Помещение", "", "Other rules", "[]", "other@example.test",
                     "Other Editor", "2026-01-03 03:04:00"),
                ],
            )
            db.commit()

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, email):
        with self.client.session_transaction() as session:
            session["user"] = {"email": email, "name": "Test User", "email_verified": True}

    def page(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_catalog_shows_details_and_escapes_user_content(self):
        html = self.page("/games")
        for text in ("Alpha &lt;game&gt;", "Beta game", "Cooperation", "8–12", "10+",
                     "15 minutes", "Ball", "Rules &lt;stay escaped&gt;", "02.01.2026 03:04",
                     'href="/uploads/rules.pdf"', "Не требуется", "Нет прикреплённых файлов."):
            self.assertIn(text, html)
        self.assertNotIn("Моя игра", html)

    def test_search_and_equipment_filter(self):
        html = self.page("/games?search=Cooperation")
        self.assertIn("Alpha &lt;game&gt;", html)
        self.assertNotIn("Beta game", html)
        html = self.page("/games?no_equipment=1")
        self.assertIn("Beta game", html)
        self.assertNotIn("Alpha &lt;game&gt;", html)

    def test_empty_search(self):
        self.assertIn("Ничего не найдено", self.page("/games?search=missing-game"))

    def test_detail_and_missing_game(self):
        html = self.page("/games/1")
        self.assertIn("Rules &lt;stay escaped&gt;", html)
        self.assertIn('href="/uploads/rules.pdf"', html)
        self.assertEqual(self.client.get("/games/999").status_code, 404)

    def test_editor_sees_only_own_games_and_edit_actions(self):
        self.login("editor@example.test")
        html = self.page("/my-games")
        self.assertIn("Alpha &lt;game&gt;", html)
        self.assertNotIn("Beta game", html)
        self.assertIn('href="/my-games/1/edit?', html)
        html = self.page("/games/1")
        self.assertIn("Моя игра", html)
        self.assertIn('href="/my-games/1/edit?', html)
        self.assertNotIn("Редактировать", self.page("/games/2"))

    def test_create_and_edit_forms_preserve_selections(self):
        self.login("editor@example.test")
        self.assertIn('name="files" multiple', self.page("/games/new"))
        html = self.page("/my-games/1/edit")
        for text in ('value="Бегалки" checked', 'value="Командообразование" checked',
                     'value="10+" checked', 'value="Улица" checked',
                     'name="delete_files" value="rules.pdf"'):
            self.assertIn(text, html)

    def test_admin_tabs_render(self):
        self.login("admin@example.test")
        for query, text in (("tab=games", "Beta game"),
                            ("tab=properties&property_tab=game-types", "Категории игр"),
                            ("tab=properties&property_tab=age-categories", "Возрастные категории"),
                            ("tab=access", "editor@example.test")):
            with self.subTest(query=query):
                self.assertIn(text, self.page("/admin?" + query))

    def test_protected_views_redirect_visitors(self):
        for path in ("/my-games", "/games/new", "/admin"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)


if __name__ == "__main__":
    unittest.main()
