import ast
import json
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "games.db"
UPLOAD_DIR = BASE_DIR / "uploads"
TYPES_PATH = BASE_DIR / "types.txt"
AGE_OPTIONS = ("7+", "10+", "12+", "Любой")
LOCATION_OPTIONS = ("Не имеет значения", "Помещение", "Улица")

ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "mp3",
    "mp4",
    "ppt",
    "pptx",
    "zip",
}

SORTABLE_FIELDS = {
    "title": "Название",
    "game_type": "Тип",
    "goal": "Цель",
    "participants": "Количество участников",
    "age_category": "Возрастная категория",
    "duration": "Длительность",
    "location": "Место проведения",
    "equipment": "Оборудование",
    "rules": "Правила",
    "files_json": "Необходимые файлы",
}

FORM_LABELS = {
    "title": "Название",
    "game_type": "Тип",
    "goal": "Цель",
    "participants": "Количество участников",
    "age_category": "Возрастная категория",
    "duration": "Длительность",
    "location": "Место проведения",
    "equipment": "Необходимое оборудование",
    "rules": "Правила",
}

TEXT_FILTER_FIELDS = tuple(FORM_LABELS.keys())

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    game_type TEXT NOT NULL,
    goal TEXT NOT NULL,
    participants TEXT NOT NULL,
    age_category TEXT NOT NULL,
    duration TEXT NOT NULL,
    location TEXT NOT NULL,
    equipment TEXT NOT NULL,
    rules TEXT NOT NULL,
    files_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""


app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-me"
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


def load_game_types() -> list[str]:
    if not TYPES_PATH.exists():
        return []

    raw_text = TYPES_PATH.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    lines = raw_text.splitlines()
    payload = "\n".join(lines[1:]).strip() if len(lines) > 1 else lines[0]

    try:
        parsed = ast.literal_eval(payload)
    except (SyntaxError, ValueError):
        return [line.strip(" -") for line in lines if line.strip()]

    return [str(item).strip() for item in parsed if str(item).strip()]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    existing_types = db.execute("SELECT COUNT(*) FROM game_types").fetchone()[0]
    if existing_types == 0:
        for name in load_game_types():
            db.execute("INSERT OR IGNORE INTO game_types (name) VALUES (?)", (name,))
    db.commit()


def fetch_game_types() -> list[str]:
    init_db()
    rows = get_db().execute("SELECT name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()
    return [row["name"] for row in rows]


def fetch_game_type_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute("SELECT id, name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_files(uploaded_files: list, existing_files: list[str] | None = None) -> list[str]:
    saved_files = list(existing_files or [])
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for uploaded in uploaded_files:
        if not uploaded or not uploaded.filename:
            continue
        if not allowed_file(uploaded.filename):
            flash(f"Файл {uploaded.filename} пропущен: недопустимое расширение.", "warning")
            continue

        safe_name = secure_filename(uploaded.filename)
        unique_name = f"{secrets.token_hex(8)}_{safe_name}"
        target = UPLOAD_DIR / unique_name
        uploaded.save(target)
        saved_files.append(unique_name)

    return saved_files


def parse_files_json(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, str)]


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
            if field in {"game_type", "age_category", "location"}:
                clauses.append(f"{field} = ?")
                params.append(value)
            else:
                clauses.append(f"{field} LIKE ?")
                params.append(f"%{value}%")

    files_query = args.get("files_json", "").strip()
    if files_query:
        clauses.append("files_json LIKE ?")
        params.append(f"%{files_query}%")

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


def get_game_or_404(game_id: int) -> sqlite3.Row:
    game = get_db().execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        abort(404)
    return game


def extract_game_form_data(form) -> dict[str, str]:
    return {
        "title": form.get("title", "").strip(),
        "game_type": form.get("game_type", "").strip(),
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
        if not value:
            errors.append(f"Поле «{FORM_LABELS.get(key, key)}» обязательно для заполнения.")
    return errors


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
        age_options=AGE_OPTIONS,
        location_options=LOCATION_OPTIONS,
        parse_files_json=parse_files_json,
    )


@app.route("/games/new", methods=("GET", "POST"))
def add_game():
    init_db()
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
                age_options=AGE_OPTIONS,
                location_options=LOCATION_OPTIONS,
                is_edit=False,
            )

        files = save_uploaded_files(request.files.getlist("files"))
        db = get_db()
        db.execute(
            """
            INSERT INTO games (
                title, game_type, goal, participants, age_category,
                duration, location, equipment, rules, files_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        db.commit()
        flash("Запись добавлена.", "success")
        return redirect(url_for("games_list"))

    return render_template(
        "game_form.html",
        game={},
        game_types=fetch_game_types(),
        age_options=AGE_OPTIONS,
        location_options=LOCATION_OPTIONS,
        is_edit=False,
    )


@app.route("/admin")
def admin_list():
    init_db()
    games = get_db().execute("SELECT * FROM games ORDER BY updated_at DESC, id DESC").fetchall()
    return render_template(
        "admin_list.html",
        games=games,
        game_types=fetch_game_type_rows(),
        parse_files_json=parse_files_json,
    )


@app.route("/admin/<int:game_id>/edit", methods=("GET", "POST"))
def edit_game(game_id: int):
    init_db()
    game = get_game_or_404(game_id)

    if request.method == "POST":
        data = extract_game_form_data(request.form)
        errors = validate_game_form(data)
        current_files = parse_files_json(game["files_json"])

        if errors:
            for error in errors:
                flash(error, "error")
            draft_game = dict(data)
            draft_game["id"] = game_id
            return render_template(
                "game_form.html",
                game=draft_game,
                game_types=fetch_game_types(),
                age_options=AGE_OPTIONS,
                location_options=LOCATION_OPTIONS,
                is_edit=True,
                existing_files=current_files,
            )

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
        return redirect(url_for("admin_list"))

    game_dict = dict(game)
    existing_files = parse_files_json(game["files_json"])
    return render_template(
        "game_form.html",
        game=game_dict,
        game_types=fetch_game_types(),
        age_options=AGE_OPTIONS,
        location_options=LOCATION_OPTIONS,
        is_edit=True,
        existing_files=existing_files,
    )


@app.post("/admin/<int:game_id>/delete")
def delete_game(game_id: int):
    init_db()
    game = get_game_or_404(game_id)
    for filename in parse_files_json(game["files_json"]):
        target = UPLOAD_DIR / filename
        if target.exists():
            target.unlink()

    db = get_db()
    db.execute("DELETE FROM games WHERE id = ?", (game_id,))
    db.commit()
    flash("Запись удалена.", "success")
    return redirect(url_for("admin_list"))


@app.post("/admin/categories")
def add_category():
    init_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Название категории не может быть пустым.", "error")
        return redirect(url_for("admin_list"))

    db = get_db()
    try:
        db.execute("INSERT INTO game_types (name) VALUES (?)", (name,))
        db.commit()
    except sqlite3.IntegrityError:
        flash("Такая категория уже существует.", "warning")
    else:
        flash("Категория добавлена.", "success")
    return redirect(url_for("admin_list"))


@app.post("/admin/categories/<int:type_id>/edit")
def edit_category(type_id: int):
    init_db()
    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash("Название категории не может быть пустым.", "error")
        return redirect(url_for("admin_list"))

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
    return redirect(url_for("admin_list"))


@app.post("/admin/categories/<int:type_id>/delete")
def delete_category(type_id: int):
    init_db()
    db = get_db()
    current = db.execute("SELECT * FROM game_types WHERE id = ?", (type_id,)).fetchone()
    if current is None:
        abort(404)

    usage_count = db.execute("SELECT COUNT(*) FROM games WHERE game_type = ?", (current["name"],)).fetchone()[0]
    if usage_count:
        flash("Нельзя удалить категорию, пока она используется в играх.", "error")
        return redirect(url_for("admin_list"))

    db.execute("DELETE FROM game_types WHERE id = ?", (type_id,))
    db.commit()
    flash("Категория удалена.", "success")
    return redirect(url_for("admin_list"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)


@app.context_processor
def inject_globals():
    return {"sortable_fields": SORTABLE_FIELDS}


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
