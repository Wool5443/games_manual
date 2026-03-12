import sqlite3

from flask import Flask, g

from .config import DATABASE_PATH, DEFAULT_AGE_OPTIONS, DEFAULT_GAME_TYPES, SCHEMA


def register_db(app: Flask) -> None:
    app.teardown_appcontext(close_db)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    game_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(games)").fetchall()
    }
    if "created_by_email" not in game_columns:
        db.execute("ALTER TABLE games ADD COLUMN created_by_email TEXT NOT NULL DEFAULT ''")
    if "created_by_name" not in game_columns:
        db.execute("ALTER TABLE games ADD COLUMN created_by_name TEXT NOT NULL DEFAULT ''")
    existing_types = db.execute("SELECT COUNT(*) FROM game_types").fetchone()[0]
    if existing_types == 0:
        for name in DEFAULT_GAME_TYPES:
            db.execute("INSERT OR IGNORE INTO game_types (name) VALUES (?)", (name,))
    existing_age_categories = db.execute("SELECT COUNT(*) FROM age_categories").fetchone()[0]
    if existing_age_categories == 0:
        for name in DEFAULT_AGE_OPTIONS:
            db.execute("INSERT OR IGNORE INTO age_categories (name) VALUES (?)", (name,))
    db.commit()


def fetch_game_types() -> list[str]:
    init_db()
    rows = get_db().execute("SELECT name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()
    return [row["name"] for row in rows]


def fetch_game_type_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute("SELECT id, name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()


def fetch_age_categories() -> list[str]:
    init_db()
    rows = get_db().execute("SELECT name FROM age_categories ORDER BY id ASC").fetchall()
    return [row["name"] for row in rows]


def fetch_age_category_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute("SELECT id, name FROM age_categories ORDER BY id ASC").fetchall()


def fetch_access_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute(
        """
        SELECT id, email, role
        FROM access_users
        ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, email COLLATE NOCASE
        """
    ).fetchall()


def fetch_invite_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute(
        """
        SELECT id, token, role, created_by_email, created_at
        FROM invite_links
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
