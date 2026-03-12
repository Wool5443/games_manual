from flask import Flask, flash, redirect, request, session, url_for

from ..access import (
    apply_invite_to_email,
    fetch_invite_row_by_token,
    get_current_user_email,
    get_google_redirect_uri,
    get_user_role,
    is_google_auth_enabled,
)
from ..config import ACCESS_ROLE_LABELS
from ..extensions import oauth
from ..helpers import safe_redirect_target


def register_auth_routes(app: Flask) -> None:
    @app.get("/auth/google/login")
    def login_google():
        if not is_google_auth_enabled():
            flash(
                "Google авторизация не настроена. Укажите GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET.",
                "error",
            )
            return redirect(url_for("games_list"))

        next_target = safe_redirect_target(request.args.get("next"))
        if next_target:
            session["auth_next"] = next_target

        google = oauth.create_client("google")
        redirect_uri = get_google_redirect_uri()
        return google.authorize_redirect(redirect_uri)

    @app.get("/invite/<token>")
    def accept_invite(token: str):
        invite = fetch_invite_row_by_token(token)
        if invite is None:
            flash("Ссылка-приглашение недействительна или была отозвана.", "error")
            return redirect(url_for("games_list"))

        target = url_for("admin_list") if invite["role"] == "admin" else url_for("add_game")
        current_email = get_current_user_email()
        if current_email:
            success, message = apply_invite_to_email(token, current_email)
            flash(message, "success" if success else "error")
            return redirect(target if success else url_for("games_list"))

        if not is_google_auth_enabled():
            flash("Google авторизация не настроена. Ссылка-приглашение пока не может быть использована.", "error")
            return redirect(url_for("games_list"))

        session["pending_invite_token"] = token
        session["auth_next"] = target
        flash(f"Войдите через Google, чтобы получить доступ «{ACCESS_ROLE_LABELS[invite['role']]}».", "warning")
        return redirect(url_for("login_google"))

    @app.get("/auth/google/callback")
    def google_callback():
        if not is_google_auth_enabled():
            flash("Google авторизация не настроена.", "error")
            return redirect(url_for("games_list"))

        google = oauth.create_client("google")
        token = google.authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = google.userinfo()

        email = str(userinfo.get("email", "")).strip()
        if not userinfo.get("email_verified") or not email:
            session.pop("user", None)
            flash("Google-аккаунт должен иметь подтверждённый email.", "error")
            return redirect(url_for("games_list"))

        invite_token = session.pop("pending_invite_token", None)
        if invite_token:
            success, message = apply_invite_to_email(invite_token, email)
            flash(message, "success" if success else "error")

        role = get_user_role(email)
        if role is None:
            session.pop("user", None)
            flash("У этого аккаунта нет доступа к добавлению игр или админ-панели.", "error")
            return redirect(url_for("games_list"))

        session["user"] = {
            "email": email,
            "name": str(userinfo.get("name", "")).strip() or email,
            "picture": str(userinfo.get("picture", "")).strip(),
            "email_verified": bool(userinfo.get("email_verified")),
        }
        flash("Вход через Google выполнен.", "success")
        return redirect(session.pop("auth_next", url_for("games_list")))

    @app.post("/auth/logout")
    def logout():
        session.pop("user", None)
        session.pop("auth_next", None)
        session.pop("pending_invite_token", None)
        flash("Вы вышли из аккаунта.", "success")
        return redirect(url_for("games_list"))
