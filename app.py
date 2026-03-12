import os

from games_manual_app import app
from games_manual_app.db import init_db


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug)
