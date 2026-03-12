from flask import Flask

from .access import (
    can_add_games,
    can_edit_game,
    get_current_user,
    get_current_user_email,
    get_current_user_role,
    is_admin_authenticated,
    is_google_auth_enabled,
    is_own_game,
)
from .config import ADMIN_GAMES_ORDER_OPTIONS, SORTABLE_FIELDS
from .helpers import format_datetime, parse_multi_categories, versioned_static


def register_template_context(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        return {
            "sortable_fields": SORTABLE_FIELDS,
            "admin_games_order_options": ADMIN_GAMES_ORDER_OPTIONS,
            "parse_multi_categories": parse_multi_categories,
            "format_datetime": format_datetime,
            "current_user": get_current_user(),
            "current_user_email": get_current_user_email(),
            "current_user_role": get_current_user_role(),
            "can_add_games": can_add_games(),
            "can_edit_game": can_edit_game,
            "is_own_game": is_own_game,
            "is_admin_authenticated": is_admin_authenticated(),
            "google_auth_enabled": is_google_auth_enabled(),
            "versioned_static": versioned_static,
        }
