"""Local admin opt-in and normal authentication regression checks."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from games_manual_app import create_app
from games_manual_app.db import get_db, init_db


class LocalAdminTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch("games_manual_app.db.DATABASE_PATH", Path(directory.name) / "games.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="local-admin-test", LOCAL_ADMIN=True)
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()

    def game_data(self, title="Локальная игра"):
        return MultiDict([
            ("title", title), ("game_type", "Бегалки"), ("goal", "Проверка доступа"),
            ("participants", "5–10"), ("age_category", "7+"), ("duration", "10 минут"),
            ("location", "Помещение"), ("equipment", ""), ("rules", "Правила игры"),
        ])

    def test_environment_flag_is_opt_in(self):
        with patch.dict(os.environ):
            os.environ.pop("LOCAL_ADMIN", None)
            self.assertFalse(create_app().config["LOCAL_ADMIN"])
        for value in ("1", "true", "yes", "on", " TRUE "):
            with self.subTest(value=value), patch.dict(os.environ, {"LOCAL_ADMIN": value}):
                self.assertTrue(create_app().config["LOCAL_ADMIN"])
        for value in ("0", "false", "no", "off", "", "other"):
            with self.subTest(value=value), patch.dict(os.environ, {"LOCAL_ADMIN": value}):
                self.assertFalse(create_app().config["LOCAL_ADMIN"])

    def test_guest_has_admin_pages_and_navigation_without_auth_buttons(self):
        with patch("games_manual_app.template_context.is_google_auth_enabled", return_value=True):
            for path in ("/games", "/admin", "/admin?tab=access", "/games/new", "/my-games"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertIn("Локальный администратор", html)
                    for link in ('href="/admin"', 'href="/games/new"', 'href="/my-games"'):
                        self.assertIn(link, html)
                    self.assertNotIn('action="/auth/logout"', html)
                    self.assertNotIn('href="/auth/google/login"', html)

    def test_guest_can_create_edit_and_delete_without_creating_accounts(self):
        response = self.client.post("/games/new", data=self.game_data())
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            game = get_db().execute("SELECT * FROM games WHERE title = 'Локальная игра'").fetchone()
            self.assertEqual(game["created_by_email"], "local-admin@example.test")
            self.assertEqual(game["created_by_name"], "Локальный администратор")
            game_id = game["id"]
        self.assertIn("Локальная игра", self.client.get("/my-games").get_data(as_text=True))
        response = self.client.post(f"/admin/{game_id}/edit", data=self.game_data("Обновлённая игра"))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()[0],
                             "Обновлённая игра")
        response = self.client.post(f"/admin/{game_id}/delete")
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            db = get_db()
            self.assertIsNone(db.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone())
            for table in ("access_users", "invite_links"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_guest_can_edit_and_delete_games_by_other_authors(self):
        self.assertEqual(self.client.get("/admin/1/edit").status_code, 200)
        self.assertEqual(self.client.post("/admin/1/edit", data=self.game_data("Чужая игра обновлена")).status_code, 302)
        self.assertEqual(self.client.post("/admin/1/delete").status_code, 302)
        self.assertEqual(self.client.get("/games/1").status_code, 404)

    def test_existing_session_is_overridden_without_being_replaced(self):
        session_user = {"email": "editor@example.test", "name": "Редактор", "email_verified": True}
        with self.client.session_transaction() as session:
            session["user"] = session_user
        with self.app.app_context():
            db = get_db()
            db.execute("INSERT INTO access_users (email, role) VALUES (?, 'editor')", (session_user["email"],))
            db.commit()
        self.assertEqual(self.client.get("/admin").status_code, 200)
        self.assertEqual(self.client.post("/games/new", data=self.game_data()).status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT created_by_email FROM games WHERE title = 'Локальная игра'").fetchone()[0],
                             "local-admin@example.test")
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM access_users").fetchone()[0], 1)
        with self.client.session_transaction() as session:
            self.assertEqual(session["user"], session_user)
        self.app.config["LOCAL_ADMIN"] = False
        self.assertEqual(self.client.get("/admin").status_code, 302)
        self.assertEqual(self.client.get("/games/new").status_code, 200)
        html = self.client.get("/games").get_data(as_text=True)
        self.assertIn("Редактор", html)
        self.assertNotIn("Локальный администратор", html)
        self.assertIn('action="/auth/logout"', html)

    def test_disabled_mode_keeps_guest_routes_protected(self):
        self.app.config["LOCAL_ADMIN"] = False
        with patch("games_manual_app.access.is_google_auth_enabled", return_value=False):
            for path in ("/admin", "/games/new", "/my-games", "/admin/1/edit"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.headers["Location"], "/games")
            self.assertEqual(self.client.post("/admin/1/delete").status_code, 302)
        self.assertEqual(self.client.get("/games/1").status_code, 200)
        self.assertNotIn("Локальный администратор", self.client.get("/games").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
