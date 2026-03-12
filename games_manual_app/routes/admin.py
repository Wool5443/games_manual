import csv
import io
import os
import secrets
import sqlite3
import tempfile
from pathlib import Path

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, send_file, url_for

from ..access import admin_required, build_invite_url, get_current_user_email
from ..admin_services import apply_bulk_access_updates, apply_bulk_property_updates
from ..config import ACCESS_ROLE_LABELS, ADMIN_GAMES_ORDER_OPTIONS, CSV_EXPORT_FIELDS, DATABASE_PATH, IMPORTABLE_CSV_EXTENSIONS, IMPORTABLE_DB_EXTENSIONS
from ..db import close_db, fetch_access_rows, fetch_age_category_rows, fetch_game_type_rows, fetch_invite_rows, get_db, init_db
from ..files import parse_files_json, serialize_csv_files
from ..games import delete_game_record, get_admin_games_order, get_game_or_404, handle_game_edit
from ..helpers import parse_multi_categories
from ..import_export import import_games_from_csv, validate_import_database


def register_admin_routes(app: Flask) -> None:
    @app.route("/admin")
    @admin_required
    def admin_list():
        init_db()
        active_tab = request.args.get("tab", "games")
        if active_tab not in {"games", "properties", "access"}:
            active_tab = "games"
        property_tab = request.args.get("property_tab", "game-types")
        if property_tab not in {"game-types", "age-categories"}:
            property_tab = "game-types"
        games_order = get_admin_games_order(request.args)
        tie_breaker = "DESC" if games_order == "desc" else "ASC"
        games = get_db().execute(
            f"SELECT * FROM games ORDER BY created_at {games_order.upper()}, id {tie_breaker}"
        ).fetchall()
        invite_links = [
            {
                **dict(row),
                "url": build_invite_url(row["token"]),
            }
            for row in fetch_invite_rows()
        ]
        return render_template(
            "admin_list.html",
            games=games,
            game_types=fetch_game_type_rows(),
            age_categories=fetch_age_category_rows(),
            access_users=fetch_access_rows(),
            invite_links=invite_links,
            access_role_labels=ACCESS_ROLE_LABELS,
            active_tab=active_tab,
            property_tab=property_tab,
            games_order=games_order,
            admin_games_order_options=ADMIN_GAMES_ORDER_OPTIONS,
            parse_files_json=parse_files_json,
            parse_multi_categories=parse_multi_categories,
        )

    @app.get("/admin/export")
    @admin_required
    def export_database():
        init_db()
        if "db" in g:
            g.db.commit()

        if not DATABASE_PATH.exists():
            flash("Файл базы данных пока не создан.", "error")
            return redirect(url_for("admin_list", tab="games"))

        return send_file(
            DATABASE_PATH,
            as_attachment=True,
            download_name="games_manual_export.db",
            mimetype="application/octet-stream",
        )

    @app.get("/admin/export/csv")
    @admin_required
    def export_games_csv():
        init_db()
        games = get_db().execute(
            """
            SELECT id, title, game_type, goal, participants, age_category, duration,
                   location, equipment, rules, files_json, created_by_email, created_by_name
            FROM games
            ORDER BY id ASC
            """
        ).fetchall()

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CSV_EXPORT_FIELDS)
        writer.writeheader()
        for game in games:
            writer.writerow(
                {
                    "id": game["id"],
                    "title": game["title"],
                    "game_type": game["game_type"],
                    "goal": game["goal"],
                    "participants": game["participants"],
                    "age_category": game["age_category"],
                    "duration": game["duration"],
                    "location": game["location"],
                    "equipment": game["equipment"],
                    "rules": game["rules"],
                    "files": serialize_csv_files(game["files_json"]),
                    "created_by_email": game["created_by_email"],
                    "created_by_name": game["created_by_name"],
                }
            )

        csv_content = "\ufeff" + buffer.getvalue()
        return Response(
            csv_content,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=games_manual_export.csv",
            },
        )

    @app.post("/admin/import")
    @admin_required
    def import_database():
        uploaded_file = request.files.get("database_file")
        if not uploaded_file or not uploaded_file.filename:
            flash("Выберите файл базы данных для импорта.", "error")
            return redirect(url_for("admin_list", tab="games"))

        extension = Path(uploaded_file.filename).suffix.lower()
        if extension not in IMPORTABLE_DB_EXTENSIONS:
            flash("Поддерживаются только файлы .db, .sqlite и .sqlite3.", "error")
            return redirect(url_for("admin_list", tab="games"))

        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=DATABASE_PATH.parent,
            suffix=extension,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            uploaded_file.save(temp_path)
            is_valid, error_message = validate_import_database(temp_path)
            if not is_valid:
                temp_path.unlink(missing_ok=True)
                flash(error_message, "error")
                return redirect(url_for("admin_list", tab="games"))

            close_db(None)
            os.replace(temp_path, DATABASE_PATH)
            flash("База данных импортирована.", "success")
        except OSError:
            temp_path.unlink(missing_ok=True)
            flash("Не удалось сохранить импортируемую базу данных.", "error")

        return redirect(url_for("admin_list", tab="games"))

    @app.post("/admin/import/csv")
    @admin_required
    def import_games_csv():
        uploaded_file = request.files.get("csv_file")
        if not uploaded_file or not uploaded_file.filename:
            flash("Выберите CSV-файл для импорта упражнений.", "error")
            return redirect(url_for("admin_list", tab="games"))

        extension = Path(uploaded_file.filename).suffix.lower()
        if extension not in IMPORTABLE_CSV_EXTENSIONS:
            flash("Поддерживаются только файлы .csv.", "error")
            return redirect(url_for("admin_list", tab="games"))

        success, message = import_games_from_csv(uploaded_file)
        flash(message, "success" if success else "error")
        return redirect(url_for("admin_list", tab="games"))

    @app.route("/admin/<int:game_id>/edit", methods=("GET", "POST"))
    @admin_required
    def admin_edit_game(game_id: int):
        return handle_game_edit(game_id, url_for("admin_list"))

    @app.post("/admin/<int:game_id>/delete")
    @admin_required
    def delete_game(game_id: int):
        init_db()
        game = get_game_or_404(game_id)
        delete_game_record(game)
        flash("Запись удалена.", "success")
        return redirect(url_for("admin_list", tab="games"))

    @app.post("/admin/categories")
    @admin_required
    def add_category():
        init_db()
        name = request.form.get("name", "").strip()
        if not name:
            flash("Название категории не может быть пустым.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

        db = get_db()
        try:
            db.execute("INSERT INTO game_types (name) VALUES (?)", (name,))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Такая категория уже существует.", "warning")
        else:
            flash("Категория добавлена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

    @app.post("/admin/properties/game-types")
    @admin_required
    def save_game_types():
        init_db()
        success, message = apply_bulk_property_updates(
            table_name="game_types",
            entity_label="Категории игр",
            game_field="game_type",
            existing_rows=fetch_game_type_rows(),
            form=request.form,
        )
        flash(message, "success" if success else "error")
        return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

    @app.post("/admin/categories/<int:type_id>/edit")
    @admin_required
    def edit_category(type_id: int):
        init_db()
        new_name = request.form.get("name", "").strip()
        if not new_name:
            flash("Название категории не может быть пустым.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

        db = get_db()
        current = db.execute("SELECT * FROM game_types WHERE id = ?", (type_id,)).fetchone()
        if current is None:
            abort(404)

        try:
            db.execute("UPDATE game_types SET name = ? WHERE id = ?", (new_name, type_id))
            db.execute("UPDATE games SET game_type = ? WHERE game_type = ?", (new_name, current["name"]))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Такая категория уже существует.", "warning")
        else:
            flash("Категория обновлена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

    @app.post("/admin/categories/<int:type_id>/delete")
    @admin_required
    def delete_category(type_id: int):
        init_db()
        db = get_db()
        current = db.execute("SELECT * FROM game_types WHERE id = ?", (type_id,)).fetchone()
        if current is None:
            abort(404)

        usage_count = db.execute("SELECT COUNT(*) FROM games WHERE game_type = ?", (current["name"],)).fetchone()[0]
        if usage_count:
            flash("Нельзя удалить категорию, пока она используется в играх.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

        db.execute("DELETE FROM game_types WHERE id = ?", (type_id,))
        db.commit()
        flash("Категория удалена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="game-types"))

    @app.post("/admin/age-categories")
    @admin_required
    def add_age_category():
        init_db()
        name = request.form.get("name", "").strip()
        if not name:
            flash("Название возрастной категории не может быть пустым.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

        db = get_db()
        try:
            db.execute("INSERT INTO age_categories (name) VALUES (?)", (name,))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Такая возрастная категория уже существует.", "warning")
        else:
            flash("Возрастная категория добавлена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

    @app.post("/admin/properties/age-categories")
    @admin_required
    def save_age_categories():
        init_db()
        success, message = apply_bulk_property_updates(
            table_name="age_categories",
            entity_label="Возрастные категории",
            game_field="age_category",
            existing_rows=fetch_age_category_rows(),
            form=request.form,
        )
        flash(message, "success" if success else "error")
        return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

    @app.post("/admin/properties/access-users")
    @admin_required
    def save_access_users():
        init_db()
        success, message = apply_bulk_access_updates(request.form)
        flash(message, "success" if success else "error")
        return redirect(url_for("admin_list", tab="access"))

    @app.post("/admin/invite-links")
    @admin_required
    def create_invite_link():
        init_db()
        role = request.form.get("role", "").strip()
        if role not in ACCESS_ROLE_LABELS:
            flash("Указана неизвестная роль для ссылки-приглашения.", "error")
            return redirect(url_for("admin_list", tab="access"))

        token = secrets.token_urlsafe(24)
        get_db().execute(
            "INSERT INTO invite_links (token, role, created_by_email) VALUES (?, ?, ?)",
            (token, role, get_current_user_email()),
        )
        get_db().commit()
        flash(f"Ссылка-приглашение для роли «{ACCESS_ROLE_LABELS[role]}» создана.", "success")
        return redirect(url_for("admin_list", tab="access"))

    @app.post("/admin/invite-links/<int:invite_id>/delete")
    @admin_required
    def delete_invite_link(invite_id: int):
        init_db()
        row = get_db().execute("SELECT id FROM invite_links WHERE id = ?", (invite_id,)).fetchone()
        if row is None:
            abort(404)

        get_db().execute("DELETE FROM invite_links WHERE id = ?", (invite_id,))
        get_db().commit()
        flash("Ссылка-приглашение отозвана.", "success")
        return redirect(url_for("admin_list", tab="access"))

    @app.post("/admin/age-categories/<int:age_id>/edit")
    @admin_required
    def edit_age_category(age_id: int):
        init_db()
        new_name = request.form.get("name", "").strip()
        if not new_name:
            flash("Название возрастной категории не может быть пустым.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

        db = get_db()
        current = db.execute("SELECT * FROM age_categories WHERE id = ?", (age_id,)).fetchone()
        if current is None:
            abort(404)

        try:
            db.execute("UPDATE age_categories SET name = ? WHERE id = ?", (new_name, age_id))
            db.execute("UPDATE games SET age_category = ? WHERE age_category = ?", (new_name, current["name"]))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Такая возрастная категория уже существует.", "warning")
        else:
            flash("Возрастная категория обновлена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

    @app.post("/admin/age-categories/<int:age_id>/delete")
    @admin_required
    def delete_age_category(age_id: int):
        init_db()
        db = get_db()
        current = db.execute("SELECT * FROM age_categories WHERE id = ?", (age_id,)).fetchone()
        if current is None:
            abort(404)

        usage_count = db.execute("SELECT COUNT(*) FROM games WHERE age_category = ?", (current["name"],)).fetchone()[0]
        if usage_count:
            flash("Нельзя удалить возрастную категорию, пока она используется в играх.", "error")
            return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))

        db.execute("DELETE FROM age_categories WHERE id = ?", (age_id,))
        db.commit()
        flash("Возрастная категория удалена.", "success")
        return redirect(url_for("admin_list", tab="properties", property_tab="age-categories"))
