import json
import sqlite3

from flask import abort, flash, redirect, render_template, request, url_for

from .access import can_edit_game, get_current_user_email, is_admin_authenticated
from .config import ADMIN_GAMES_ORDER_OPTIONS, FORM_LABELS, LOCATION_OPTIONS, SORTABLE_FIELDS, TEXT_FILTER_FIELDS, UPLOAD_DIR
from .db import fetch_age_categories, fetch_game_types, get_db, init_db
from .files import parse_files_json, save_uploaded_files
from .helpers import join_multi_categories, parse_multi_categories, safe_redirect_target


def build_filters(args) -> tuple[str, list[str]]:
    clauses = []
    params: list[str] = []

    search = args.get("search", "").strip()
    if search:
        clauses.append(
            "(" + " OR ".join(f"{field} LIKE ?" for field in (*TEXT_FILTER_FIELDS, "files_json")) + ")"
        )
        params.extend([f"%{search}%"] * (len(TEXT_FILTER_FIELDS) + 1))

    for field in TEXT_FILTER_FIELDS:
        value = args.get(field, "").strip()
        if value:
            if field == "game_type":
                clauses.append("game_type LIKE ?")
                params.append(f"%{value}%")
            elif field in {"age_category", "location"}:
                clauses.append(f"{field} = ?")
                params.append(value)
            else:
                clauses.append(f"{field} LIKE ?")
                params.append(f"%{value}%")

    files_query = args.get("files_json", "").strip()
    if files_query:
        clauses.append("files_json LIKE ?")
        params.append(f"%{files_query}%")

    if args.get("no_equipment") == "1":
        clauses.append("(equipment = '' OR equipment IS NULL)")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def get_sorting(args) -> tuple[str, str]:
    sort = args.get("sort", "title")
    order = args.get("order", "asc").lower()

    if sort not in SORTABLE_FIELDS:
        sort = "title"
    if order not in {"asc", "desc"}:
        order = "asc"

    return sort, order


def get_admin_games_order(args) -> str:
    order = args.get("games_order", "desc").lower()
    if order not in ADMIN_GAMES_ORDER_OPTIONS:
        order = "desc"
    return order


def get_game_or_404(game_id: int) -> sqlite3.Row:
    game = get_db().execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        abort(404)
    return game


def extract_game_form_data(form) -> dict[str, str]:
    selected_types = join_multi_categories(form.getlist("game_type"))
    return {
        "title": form.get("title", "").strip(),
        "game_type": selected_types,
        "goal": form.get("goal", "").strip(),
        "participants": form.get("participants", "").strip(),
        "age_category": form.get("age_category", "").strip(),
        "duration": form.get("duration", "").strip(),
        "location": form.get("location", "").strip(),
        "equipment": form.get("equipment", "").strip(),
        "rules": form.get("rules", "").strip(),
    }


def validate_game_form(data: dict[str, str]) -> list[str]:
    errors = []
    for key, value in data.items():
        if key == "equipment":
            continue
        if not value:
            errors.append(f"Поле «{FORM_LABELS.get(key, key)}» обязательно для заполнения.")
    return errors


def render_game_edit_form(game, current_files: list[str], return_to: str, delete_url: str | None = None):
    return render_template(
        "game_form.html",
        game=game,
        game_types=fetch_game_types(),
        age_options=fetch_age_categories(),
        location_options=LOCATION_OPTIONS,
        is_edit=True,
        existing_files=current_files,
        cancel_url=return_to,
        return_to=return_to,
        delete_url=delete_url,
        parse_multi_categories=parse_multi_categories,
    )


def delete_game_record(game: sqlite3.Row | dict) -> None:
    for filename in parse_files_json(game["files_json"]):
        target = UPLOAD_DIR / filename
        if target.exists():
            target.unlink()

    db = get_db()
    db.execute("DELETE FROM games WHERE id = ?", (game["id"],))
    db.commit()


def handle_game_edit(game_id: int, default_return: str):
    init_db()
    game = get_game_or_404(game_id)
    if not can_edit_game(game):
        flash("Вы можете редактировать только игры, которые добавили сами.", "error")
        return redirect(url_for("my_games"))

    return_to = safe_redirect_target(request.values.get("return_to"), fallback=default_return)
    delete_url = url_for("delete_game", game_id=game_id) if is_admin_authenticated() else url_for("delete_own_game", game_id=game_id)

    if request.method == "POST":
        data = extract_game_form_data(request.form)
        errors = validate_game_form(data)
        current_files = parse_files_json(game["files_json"])

        if errors:
            for error in errors:
                flash(error, "error")
            draft_game = dict(data)
            draft_game["id"] = game_id
            return render_game_edit_form(draft_game, current_files, return_to, delete_url)

        files_to_remove = set(request.form.getlist("delete_files"))
        remaining_files = [name for name in current_files if name not in files_to_remove]
        updated_files = save_uploaded_files(request.files.getlist("files"), remaining_files)

        for filename in files_to_remove:
            target = UPLOAD_DIR / filename
            if target.exists():
                target.unlink()

        db = get_db()
        db.execute(
            """
            UPDATE games
            SET title = ?, game_type = ?, goal = ?, participants = ?,
                age_category = ?, duration = ?, location = ?, equipment = ?,
                rules = ?, files_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                data["title"],
                data["game_type"],
                data["goal"],
                data["participants"],
                data["age_category"],
                data["duration"],
                data["location"],
                data["equipment"],
                data["rules"],
                json.dumps(updated_files, ensure_ascii=False),
                game_id,
            ),
        )
        db.commit()
        flash("Запись обновлена.", "success")
        return redirect(return_to)

    game_dict = dict(game)
    existing_files = parse_files_json(game["files_json"])
    return render_game_edit_form(game_dict, existing_files, return_to, delete_url)
