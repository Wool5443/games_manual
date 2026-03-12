import sqlite3
from functools import wraps

from flask import flash, redirect, request, session, url_for

from .config import ACCESS_ROLE_LABELS, ADMIN_EMAILS, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PUBLIC_BASE_URL
from .db import get_db, init_db
from .extensions import oauth
from .helpers import normalize_email, safe_redirect_target


def is_google_auth_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and oauth.create_client("google"))


def get_current_user() -> dict[str, str] | None:
    user = session.get("user")
    return user if isinstance(user, dict) else None


def get_current_user_email() -> str:
    user = get_current_user()
    if not user or not user.get("email_verified"):
        return ""
    return normalize_email(user.get("email"))


def get_user_role(email: str | None) -> str | None:
    normalized_email = normalize_email(email)
    if not normalized_email:
        return None
    if normalized_email in ADMIN_EMAILS:
        return "admin"

    init_db()
    row = get_db().execute(
        "SELECT role FROM access_users WHERE email = ?",
        (normalized_email,),
    ).fetchone()
    if row is None:
        return None
    role = row["role"]
    return role if role in ACCESS_ROLE_LABELS else None


def fetch_invite_row_by_token(token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    init_db()
    return get_db().execute(
        "SELECT id, token, role, created_by_email, created_at FROM invite_links WHERE token = ?",
        (str(token).strip(),),
    ).fetchone()


def upsert_access_user(email: str, role: str) -> None:
    normalized_email = normalize_email(email)
    if not normalized_email or role not in ACCESS_ROLE_LABELS:
        return

    db = get_db()
    existing = db.execute("SELECT id FROM access_users WHERE email = ?", (normalized_email,)).fetchone()
    if existing is None:
        db.execute("INSERT INTO access_users (email, role) VALUES (?, ?)", (normalized_email, role))
    else:
        db.execute("UPDATE access_users SET role = ? WHERE email = ?", (role, normalized_email))
    db.commit()


def apply_invite_to_email(token: str | None, email: str) -> tuple[bool, str]:
    invite = fetch_invite_row_by_token(token)
    if invite is None:
        return False, "Ссылка-приглашение недействительна или была отозвана."

    role = invite["role"]
    if role not in ACCESS_ROLE_LABELS:
        return False, "В ссылке-приглашении указана неизвестная роль."

    upsert_access_user(email, role)
    role_label = ACCESS_ROLE_LABELS[role]
    return True, f"Доступ «{role_label}» выдан для {normalize_email(email)}."


def get_current_user_role() -> str | None:
    user = get_current_user()
    if not user:
        return None

    email = str(user.get("email", "")).strip().casefold()
    if not email or not user.get("email_verified"):
        return None
    return get_user_role(email)


def is_admin_authenticated() -> bool:
    return get_current_user_role() == "admin"


def can_add_games() -> bool:
    return get_current_user_role() in {"admin", "editor"}


def can_edit_game(game: sqlite3.Row | dict) -> bool:
    if is_admin_authenticated():
        return True
    if not can_add_games():
        return False
    return normalize_email(game["created_by_email"]) == get_current_user_email()


def is_own_game(game: sqlite3.Row | dict) -> bool:
    if not get_current_user_email():
        return False
    return normalize_email(game["created_by_email"]) == get_current_user_email()


def build_invite_url(token: str) -> str:
    invite_path = url_for("accept_invite", token=token)
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}{invite_path}"
    return url_for("accept_invite", token=token, _external=True)


def get_google_redirect_uri() -> str:
    callback_path = url_for("google_callback")
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}{callback_path}"
    return url_for("google_callback", _external=True)


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if is_admin_authenticated():
            return view_func(*args, **kwargs)

        if get_current_user():
            flash("У этого аккаунта нет прав администратора.", "error")
            return redirect(url_for("games_list"))

        if not is_google_auth_enabled():
            flash(
                "Google авторизация не настроена. Укажите GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET. Первого администратора можно задать через ADMIN_EMAILS.",
                "error",
            )
            return redirect(url_for("games_list"))

        session["auth_next"] = safe_redirect_target(request.full_path if request.query_string else request.path)
        flash("Войдите через Google для доступа к административным разделам.", "warning")
        return redirect(url_for("login_google"))

    return wrapped_view


def game_editor_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if can_add_games():
            return view_func(*args, **kwargs)

        if get_current_user():
            flash("У этого аккаунта нет прав на добавление игр.", "error")
            return redirect(url_for("games_list"))

        if not is_google_auth_enabled():
            flash(
                "Google авторизация не настроена. Укажите GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET. Первого администратора можно задать через ADMIN_EMAILS.",
                "error",
            )
            return redirect(url_for("games_list"))

        session["auth_next"] = safe_redirect_target(request.full_path if request.query_string else request.path)
        flash("Войдите через Google для добавления новых игр.", "warning")
        return redirect(url_for("login_google"))

    return wrapped_view
