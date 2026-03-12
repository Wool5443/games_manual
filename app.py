import json
import os
import secrets
import sqlite3
import tempfile
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, abort, flash, g, redirect, render_template, request, send_file, send_from_directory, session, url_for
from werkzeug.utils import secure_filename


from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "games.db"
UPLOAD_DIR = BASE_DIR / "uploads"
DEFAULT_GAME_TYPES = (
    "Black magic",
    "Black magic / Шутка минутка",
    "Repeat after me song",
    "Бегалки",
    "Бодряк",
    "Веревочный курс",
    "Детектив",
    "Для настроения",
    "Игры для заполнения времени",
    "Игры для объединения в группы",
    "Игры для разогрева (Ice breaker)",
    "Игры на запоминание",
    "Игры на знакомство",
    "Игры на логику",
    "Инженерная игра",
    "Квест выбраться из комнаты",
    "Командообразование",
    "Массовые игры",
    "Метаигра",
    "Мета игры",
    "Подвижные игры",
    "Прощание",
    "Псевдоспортивная",
    "Рефлексия",
    "Ролевые игра",
    "Самопознание",
    "Сценки",
    "Творчество",
    "Упражнения для малой группы",
    "Упражнения на доверие",
    "Упражнения на коммуникацию",
    "Упражнения на релаксацию",
    "Шутка минутка",
)
DEFAULT_AGE_OPTIONS = ("7+", "10+", "12+", "Любой")
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
    "odt",
    "ods",
    "odp",
    "odg",
    "odf",
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

CREATE TABLE IF NOT EXISTS age_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""

IMPORTABLE_DB_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
REQUIRED_TABLE_COLUMNS = {
    "games": {
        "id",
        "title",
        "game_type",
        "goal",
        "participants",
        "age_category",
        "duration",
        "location",
        "equipment",
        "rules",
        "files_json",
        "created_at",
        "updated_at",
    },
    "game_types": {"id", "name"},
    "age_categories": {"id", "name"},
}


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
ADMIN_EMAILS = {email.strip().casefold() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()}
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth = OAuth(app)
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_kwargs={"scope": "openid email profile"},
    )


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
        for name in DEFAULT_GAME_TYPES:
            db.execute("INSERT OR IGNORE INTO game_types (name) VALUES (?)", (name,))
    existing_age_categories = db.execute("SELECT COUNT(*) FROM age_categories").fetchone()[0]
    if existing_age_categories == 0:
        for name in DEFAULT_AGE_OPTIONS:
            db.execute("INSERT OR IGNORE INTO age_categories (name) VALUES (?)", (name,))
    db.commit()


def fetch_game_types() -> list[str]:
    init_db()
    rows = get_db().execute("SELECT name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()
    return [row["name"] for row in rows]


def fetch_game_type_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute("SELECT id, name FROM game_types ORDER BY name COLLATE NOCASE").fetchall()


def fetch_age_categories() -> list[str]:
    init_db()
    rows = get_db().execute("SELECT name FROM age_categories ORDER BY id ASC").fetchall()
    return [row["name"] for row in rows]


def fetch_age_category_rows() -> list[sqlite3.Row]:
    init_db()
    return get_db().execute("SELECT id, name FROM age_categories ORDER BY id ASC").fetchall()


def parse_multi_categories(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [item.strip() for item in value.split(",")]
    seen: list[str] = []
    for item in parts:
        if item and item not in seen:
            seen.append(item)
    return seen


def join_multi_categories(values: list[str]) -> str:
    return ", ".join(parse_multi_categories(", ".join(values)))


def apply_bulk_property_updates(
    table_name: str,
    entity_label: str,
    game_field: str | None,
    existing_rows: list[sqlite3.Row],
    form,
) -> tuple[bool, str]:
    db = get_db()
    existing_by_id = {str(row["id"]): row["name"] for row in existing_rows}
    submitted_ids = form.getlist("item_id")
    submitted_names = form.getlist("item_name")
    delete_ids = set(form.getlist("delete_item"))
    new_names = [name.strip() for name in form.get("new_items", "").splitlines() if name.strip()]

    if len(submitted_ids) != len(submitted_names):
        return False, "Некорректные данные формы."

    final_names: list[str] = []
    rename_pairs: list[tuple[str, str]] = []
    delete_names: list[str] = []

    for item_id, raw_name in zip(submitted_ids, submitted_names):
        if item_id not in existing_by_id:
            return False, "Один из элементов справочника не найден."

        current_name = existing_by_id[item_id]
        updated_name = raw_name.strip()

        if item_id in delete_ids:
            delete_names.append(current_name)
            continue

        if not updated_name:
            return False, f"Название для {entity_label.lower()} не может быть пустым."

        final_names.append(updated_name)
        if updated_name != current_name:
            rename_pairs.append((current_name, updated_name))

    final_names.extend(new_names)
    normalized_names = [name.casefold() for name in final_names]
    if len(normalized_names) != len(set(normalized_names)):
        return False, f"Найдены повторяющиеся значения в списке «{entity_label}»."

    if game_field:
        for deleted_name in delete_names:
            if game_field == "game_type":
                usage_count = db.execute(
                    "SELECT COUNT(*) FROM games WHERE game_type LIKE ?",
                    (f"%{deleted_name}%",),
                ).fetchone()[0]
            else:
                usage_count = db.execute(
                    f"SELECT COUNT(*) FROM games WHERE {game_field} = ?",
                    (deleted_name,),
                ).fetchone()[0]
            if usage_count:
                return False, f"Нельзя удалить «{deleted_name}», пока значение используется в играх."

    try:
        db.execute("BEGIN")

        for current_name, updated_name in rename_pairs:
            db.execute(
                f"UPDATE {table_name} SET name = ? WHERE name = ?",
                (updated_name, current_name),
            )
            if game_field:
                if game_field == "game_type":
                    games = db.execute(
                        "SELECT id, game_type FROM games WHERE game_type LIKE ?",
                        (f"%{current_name}%",),
                    ).fetchall()
                    for game in games:
                        updated_types = [
                            updated_name if item == current_name else item
                            for item in parse_multi_categories(game["game_type"])
                        ]
                        db.execute(
                            "UPDATE games SET game_type = ? WHERE id = ?",
                            (join_multi_categories(updated_types), game["id"]),
                        )
                else:
                    db.execute(
                        f"UPDATE games SET {game_field} = ? WHERE {game_field} = ?",
                        (updated_name, current_name),
                    )

        for deleted_name in delete_names:
            db.execute(f"DELETE FROM {table_name} WHERE name = ?", (deleted_name,))

        for name in new_names:
            db.execute(f"INSERT INTO {table_name} (name) VALUES (?)", (name,))

        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return False, f"Не удалось сохранить «{entity_label}»: найдено дублирующееся значение."

    return True, f"Список «{entity_label}» обновлён."


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


def validate_import_database(path: Path) -> tuple[bool, str]:
    try:
        with sqlite3.connect(path) as db:
            for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
                table_exists = db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table_name,),
                ).fetchone()
                if table_exists is None:
                    return False, f"В импортируемой базе нет таблицы {table_name}."

                columns = {
                    row[1]
                    for row in db.execute(f"PRAGMA table_info({table_name})").fetchall()
                }
                missing_columns = required_columns - columns
                if missing_columns:
                    missing = ", ".join(sorted(missing_columns))
                    return False, f"В таблице {table_name} отсутствуют поля: {missing}."
    except sqlite3.Error:
        return False, "Файл не является корректной SQLite-базой."

    return True, ""


def is_google_auth_enabled() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and ADMIN_EMAILS and oauth.create_client("google"))


def get_current_user() -> dict[str, str] | None:
    user = session.get("user")
    return user if isinstance(user, dict) else None


def is_admin_authenticated() -> bool:
    user = get_current_user()
    if not user:
        return False

    email = str(user.get("email", "")).strip().casefold()
    if not email or not user.get("email_verified"):
        return False
    if ADMIN_EMAILS and email not in ADMIN_EMAILS:
        return False
    return True


def safe_redirect_target(raw_target: str | None) -> str:
    if not raw_target:
        return url_for("admin_list")
    if raw_target.startswith("/") and not raw_target.startswith("//"):
        return raw_target
    return url_for("admin_list")


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if is_admin_authenticated():
            return view_func(*args, **kwargs)

        if not is_google_auth_enabled():
            flash(
                "Google авторизация не настроена. Укажите GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET и ADMIN_EMAILS.",
                "error",
            )
            return redirect(url_for("games_list"))

        session["auth_next"] = safe_redirect_target(request.full_path if request.query_string else request.path)
        flash("Войдите через Google для доступа к административным разделам.", "warning")
        return redirect(url_for("login_google"))

    return wrapped_view


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


@app.route("/games/new", methods=("GET", "POST"))
@admin_required
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
                age_options=fetch_age_categories(),
                location_options=LOCATION_OPTIONS,
                is_edit=False,
                parse_multi_categories=parse_multi_categories,
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
        age_options=fetch_age_categories(),
        location_options=LOCATION_OPTIONS,
        is_edit=False,
        parse_multi_categories=parse_multi_categories,
    )


@app.route("/admin")
@admin_required
def admin_list():
    init_db()
    active_tab = request.args.get("tab", "games")
    if active_tab not in {"games", "properties"}:
        active_tab = "games"
    property_tab = request.args.get("property_tab", "game-types")
    if property_tab not in {"game-types", "age-categories"}:
        property_tab = "game-types"
    games = get_db().execute("SELECT * FROM games ORDER BY updated_at DESC, id DESC").fetchall()
    return render_template(
        "admin_list.html",
        games=games,
        game_types=fetch_game_type_rows(),
        age_categories=fetch_age_category_rows(),
        active_tab=active_tab,
        property_tab=property_tab,
        parse_files_json=parse_files_json,
        parse_multi_categories=parse_multi_categories,
    )


@app.get("/auth/google/login")
def login_google():
    if not is_google_auth_enabled():
        flash(
            "Google авторизация не настроена. Укажите GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET и ADMIN_EMAILS.",
            "error",
        )
        return redirect(url_for("games_list"))

    next_target = safe_redirect_target(request.args.get("next"))
    if next_target:
        session["auth_next"] = next_target

    google = oauth.create_client("google")
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


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

    if ADMIN_EMAILS and email.casefold() not in ADMIN_EMAILS:
        session.pop("user", None)
        flash("У этого аккаунта нет доступа к админ-панели.", "error")
        return redirect(url_for("games_list"))

    session["user"] = {
        "email": email,
        "name": str(userinfo.get("name", "")).strip() or email,
        "picture": str(userinfo.get("picture", "")).strip(),
        "email_verified": bool(userinfo.get("email_verified")),
    }
    flash("Вход через Google выполнен.", "success")
    return redirect(session.pop("auth_next", url_for("admin_list")))


@app.post("/auth/logout")
def logout():
    session.pop("user", None)
    session.pop("auth_next", None)
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("games_list"))


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


@app.route("/admin/<int:game_id>/edit", methods=("GET", "POST"))
@admin_required
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
                age_options=fetch_age_categories(),
                location_options=LOCATION_OPTIONS,
                is_edit=True,
                existing_files=current_files,
                parse_multi_categories=parse_multi_categories,
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
        age_options=fetch_age_categories(),
        location_options=LOCATION_OPTIONS,
        is_edit=True,
        existing_files=existing_files,
        parse_multi_categories=parse_multi_categories,
    )


@app.post("/admin/<int:game_id>/delete")
@admin_required
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


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)


@app.context_processor
def inject_globals():
    return {
        "sortable_fields": SORTABLE_FIELDS,
        "parse_multi_categories": parse_multi_categories,
        "current_user": get_current_user(),
        "is_admin_authenticated": is_admin_authenticated(),
        "google_auth_enabled": is_google_auth_enabled(),
    }


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug)
