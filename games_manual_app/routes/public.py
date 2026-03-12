import json

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

from ..access import can_edit_game, game_editor_required, get_current_user, get_current_user_email
from ..config import LOCATION_OPTIONS, SORTABLE_FIELDS, UPLOAD_DIR
from ..db import fetch_age_categories, fetch_game_types, get_db, init_db
from ..files import parse_files_json, save_uploaded_files
from ..games import build_filters, extract_game_form_data, get_game_or_404, get_sorting, handle_game_edit, validate_game_form, delete_game_record
from ..helpers import parse_multi_categories


def register_public_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return redirect(url_for("games_list"))

    @app.route("/games")
    def games_list():
        init_db()
        where_sql, params = build_filters(request.args)
        sort, order = get_sorting(request.args)

        query = f"""
            SELECT *
            FROM games
            {where_sql}
            ORDER BY {sort} {order.upper()}, id DESC
        """
        games = get_db().execute(query, params).fetchall()

        return render_template(
            "games_list.html",
            games=games,
            filters=request.args,
            sort=sort,
            order=order,
            sortable_fields=SORTABLE_FIELDS,
            game_types=fetch_game_types(),
            age_options=fetch_age_categories(),
            location_options=LOCATION_OPTIONS,
            parse_files_json=parse_files_json,
            parse_multi_categories=parse_multi_categories,
        )

    @app.route("/games/<int:game_id>")
    def game_detail(game_id: int):
        init_db()
        game = get_game_or_404(game_id)
        return render_template(
            "game_detail.html",
            game=game,
            parse_files_json=parse_files_json,
            parse_multi_categories=parse_multi_categories,
        )

    @app.route("/my-games")
    @game_editor_required
    def my_games():
        init_db()
        games = get_db().execute(
            """
            SELECT *
            FROM games
            WHERE created_by_email = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (get_current_user_email(),),
        ).fetchall()
        return render_template(
            "my_games.html",
            games=games,
            parse_files_json=parse_files_json,
            parse_multi_categories=parse_multi_categories,
        )

    @app.route("/games/new", methods=("GET", "POST"))
    @game_editor_required
    def add_game():
        init_db()
        current_user = get_current_user() or {}
        cancel_url = url_for("my_games")
        if request.method == "POST":
            data = extract_game_form_data(request.form)
            errors = validate_game_form(data)
            if errors:
                for error in errors:
                    flash(error, "error")
                return render_template(
                    "game_form.html",
                    game=data,
                    game_types=fetch_game_types(),
                    age_options=fetch_age_categories(),
                    location_options=LOCATION_OPTIONS,
                    is_edit=False,
                    cancel_url=cancel_url,
                    parse_multi_categories=parse_multi_categories,
                )

            files = save_uploaded_files(request.files.getlist("files"))
            db = get_db()
            db.execute(
                """
                INSERT INTO games (
                    title, game_type, goal, participants, age_category,
                    duration, location, equipment, rules, files_json,
                    created_by_email, created_by_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(files, ensure_ascii=False),
                    get_current_user_email(),
                    str(current_user.get("name", "")).strip() or get_current_user_email(),
                ),
            )
            db.commit()
            flash("Запись добавлена.", "success")
            return redirect(url_for("my_games"))

        return render_template(
            "game_form.html",
            game={},
            game_types=fetch_game_types(),
            age_options=fetch_age_categories(),
            location_options=LOCATION_OPTIONS,
            is_edit=False,
            cancel_url=cancel_url,
            parse_multi_categories=parse_multi_categories,
        )

    @app.route("/my-games/<int:game_id>/edit", methods=("GET", "POST"))
    @game_editor_required
    def edit_game(game_id: int):
        return handle_game_edit(game_id, url_for("my_games"))

    @app.post("/my-games/<int:game_id>/delete")
    @game_editor_required
    def delete_own_game(game_id: int):
        init_db()
        game = get_game_or_404(game_id)
        if not can_edit_game(game):
            flash("Вы можете удалять только игры, которые добавили сами.", "error")
            return redirect(url_for("my_games"))

        delete_game_record(game)
        flash("Запись удалена.", "success")
        return redirect(url_for("my_games"))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename: str):
        return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)
