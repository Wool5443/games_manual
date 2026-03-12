from flask import Flask

from .config import BASE_DIR, MAX_CONTENT_LENGTH, SECRET_KEY
from .db import register_db
from .extensions import init_extensions
from .routes.admin import register_admin_routes
from .routes.auth import register_auth_routes
from .routes.public import register_public_routes
from .template_context import register_template_context


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    init_extensions(app)
    register_db(app)
    register_public_routes(app)
    register_admin_routes(app)
    register_auth_routes(app)
    register_template_context(app)

    return app


app = create_app()
