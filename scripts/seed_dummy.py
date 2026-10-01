"""Explicitly add demonstration games to the application's current database."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from games_manual_app import create_app
from games_manual_app.db import get_db, init_db
from games_manual_app.demo_data import seed_demo_games


def main() -> None:
    with create_app().app_context():
        db = get_db()
        has_games = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'games'"
        ).fetchone() is not None
        before = db.execute("SELECT COUNT(*) FROM games").fetchone()[0] if has_games else 0
        init_db()
        seed_demo_games(db)
        total = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        print(f"Добавлено демонстрационных игр: {total - before}. Всего игр: {total}.")


if __name__ == "__main__":
    main()
