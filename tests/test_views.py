"""View regression checks using a disposable database and synthetic users.

Run with: python -m unittest discover -s tests -v
"""

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from games_manual_app import create_app
from games_manual_app.db import get_db, init_db


class FormControls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.selects = {}
        self.inputs = []
        self.current_select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "select":
            self.current_select = attrs["name"]
            self.selects[self.current_select] = {"attrs": attrs, "options": []}
        elif tag == "option" and self.current_select:
            self.selects[self.current_select]["options"].append(attrs)
        elif tag == "input":
            self.inputs.append(attrs)

    def handle_endtag(self, tag):
        if tag == "select":
            self.current_select = None

    def selected(self, name):
        options = self.selects[name]["options"]
        return next((option["value"] for option in options if "selected" in option), options[0]["value"])


class ViewTests(unittest.TestCase):
    LONG_TITLE = "ОченьДлинноеНазвание" * 12
    LONG_TYPE = "ОченьДлиннаяКатегория" * 10

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
        cls.app.config.update(TESTING=True, SECRET_KEY="test-only-secret", LOCAL_ADMIN=False)
        cls.reset_database()

    @classmethod
    def reset_database(cls):
        with cls.app.app_context():
            init_db()
            db = get_db()
            for table in ("games", "access_users", "game_types", "age_categories", "invite_links"):
                db.execute(f"DELETE FROM {table}")
            db.execute("DELETE FROM sqlite_sequence")
            db.commit()
            init_db()
            db.execute("INSERT INTO access_users (email, role) VALUES (?, ?)",
                       ("editor@example.test", "editor"))
            db.execute("INSERT INTO game_types (name) VALUES (?)", (cls.LONG_TYPE,))
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
                    (cls.LONG_TITLE, cls.LONG_TYPE, "Long content", "4–6", "10+", "10 minutes",
                     "Помещение", "Rope", "Long rules", "[]", "other@example.test",
                     "Other Editor", "2026-01-01 03:04:00"),
                ],
            )
            db.commit()

    def setUp(self):
        self.reset_database()
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

    def test_sorting_preserves_requested_order(self):
        html = self.page("/games?sort=created_at&order=desc")
        self.assertLess(html.index("Beta game"), html.index("Alpha &lt;game&gt;"))

    def test_empty_search(self):
        self.assertIn("Ничего не найдено", self.page("/games?search=missing-game"))

    def test_long_titles_and_categories_render(self):
        html = self.page("/games/3")
        self.assertIn(self.LONG_TITLE, html)
        self.assertIn(self.LONG_TYPE, html)

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
                     'name="delete_files" value="rules.pdf"'):
            self.assertIn(text, html)
        controls = FormControls(html)
        self.assertEqual(controls.selected("age_category"), "10+")
        self.assertEqual(controls.selected("location"), "Улица")
        self.assertIn("required", controls.selects["age_category"]["attrs"])

    def test_catalog_native_selects_preserve_query_values(self):
        controls = FormControls(self.page("/games?game_type=Бегалки&age_category=10%2B&location=Улица&sort=duration&order=desc"))
        for name, expected in (("game_type", "Бегалки"), ("age_category", "10+"),
                               ("location", "Улица"), ("sort", "duration"), ("order", "desc")):
            self.assertEqual(controls.selected(name), expected)
        self.assertFalse(any(item.get("name", "").endswith("_choice") for item in controls.inputs))
        self.assertFalse(any(item.get("type") == "hidden" and item.get("name") in controls.selects
                             for item in controls.inputs))

    def game_data(self, title="Edited game"):
        return MultiDict([
            ("title", title), ("game_type", "Бегалки"), ("game_type", "Командообразование"),
            ("goal", "Cooperation"), ("participants", "8–12"), ("age_category", "12+"),
            ("duration", "15 minutes"), ("location", "Улица"), ("equipment", "Ball"),
            ("rules", "Updated rules"),
        ])

    def test_validation_failure_preserves_native_selections(self):
        self.login("editor@example.test")
        for path in ("/games/new", "/my-games/1/edit"):
            with self.subTest(path=path):
                response = self.client.post(path, data=self.game_data(title=""))
                self.assertEqual(response.status_code, 200)
                controls = FormControls(response.get_data(as_text=True))
                self.assertEqual(controls.selected("age_category"), "12+")
                self.assertEqual(controls.selected("location"), "Улица")
                checked_types = [item["value"] for item in controls.inputs
                                 if item.get("name") == "game_type" and "checked" in item]
                self.assertEqual(set(checked_types), {"Бегалки", "Командообразование"})

    def test_edit_submission_saves_multiple_types_and_selects(self):
        self.login("editor@example.test")
        response = self.client.post("/my-games/1/edit", data=self.game_data())
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            game = get_db().execute("SELECT * FROM games WHERE id = 1").fetchone()
            self.assertEqual(game["game_type"], "Бегалки, Командообразование")
            self.assertEqual(game["age_category"], "12+")
            self.assertEqual(game["location"], "Улица")

    def test_admin_tabs_render(self):
        self.login("admin@example.test")
        for query, text in (("tab=games", "Beta game"),
                            ("tab=properties&property_tab=game-types", "Категории игр"),
                            ("tab=properties&property_tab=age-categories", "Возрастные категории"),
                            ("tab=access", "editor@example.test")):
            with self.subTest(query=query):
                self.assertIn(text, self.page("/admin?" + query))

    def test_native_admin_role_and_delete_submissions(self):
        self.login("admin@example.test")
        controls = FormControls(self.page("/admin?tab=access"))
        self.assertEqual(controls.selected("item_role"), "editor")
        self.assertTrue(any(item.get("name") == "delete_item" and item.get("type") == "checkbox"
                            for item in controls.inputs))
        response = self.client.post("/admin/properties/access-users", data={
            "item_id": "1", "item_email": "editor@example.test", "item_role": "admin",
            "new_admins": "admin@example.test",
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT role FROM access_users WHERE id = 1").fetchone()[0], "admin")
        response = self.client.post("/admin/properties/access-users", data=MultiDict([
            ("item_id", "1"), ("item_email", "editor@example.test"), ("item_role", "admin"),
            ("item_id", "2"), ("item_email", "admin@example.test"), ("item_role", "admin"),
            ("delete_item", "1"),
        ]))
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT id FROM access_users WHERE id = 1").fetchone())

    def test_native_property_delete_checkbox(self):
        self.login("admin@example.test")
        with self.app.app_context():
            category_id = str(get_db().execute("SELECT id FROM game_types WHERE name = 'Black magic'").fetchone()[0])
        response = self.client.post("/admin/properties/game-types", data={
            "item_id": category_id, "item_name": "Black magic", "delete_item": category_id,
        })
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNone(get_db().execute("SELECT id FROM game_types WHERE id = ?", (category_id,)).fetchone())

    def test_protected_views_redirect_visitors(self):
        for path in ("/my-games", "/games/new", "/admin"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)


if __name__ == "__main__":
    unittest.main()
