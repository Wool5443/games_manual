import csv
import io
import json
import sqlite3
from pathlib import Path

from .config import CSV_EXPORT_FIELDS, LOCATION_OPTIONS, REQUIRED_TABLE_COLUMNS, UPLOAD_DIR
from .db import fetch_age_categories, fetch_game_types, get_db
from .files import parse_csv_files
from .games import validate_game_form
from .helpers import join_multi_categories, normalize_email, parse_multi_categories


def sniff_csv_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def validate_csv_rows(rows: list[dict[str, str]]) -> tuple[bool, str]:
    existing_types = {name.casefold(): name for name in fetch_game_types()}
    existing_ages = {name.casefold(): name for name in fetch_age_categories()}

    for index, row in enumerate(rows, start=2):
        data = {
            "title": row.get("title", "").strip(),
            "game_type": join_multi_categories(parse_multi_categories(row.get("game_type", ""))),
            "goal": row.get("goal", "").strip(),
            "participants": row.get("participants", "").strip(),
            "age_category": row.get("age_category", "").strip(),
            "duration": row.get("duration", "").strip(),
            "location": row.get("location", "").strip(),
            "equipment": row.get("equipment", "").strip(),
            "rules": row.get("rules", "").strip(),
        }
        errors = validate_game_form(data)
        if errors:
            return False, f"Строка {index}: {errors[0]}"
        if data["location"] not in LOCATION_OPTIONS:
            return False, f"Строка {index}: недопустимое место проведения «{data['location']}»."

        game_types = parse_multi_categories(data["game_type"])
        if not game_types:
            return False, f"Строка {index}: поле «Тип» должно содержать хотя бы одну категорию."
        for game_type in game_types:
            existing_types.setdefault(game_type.casefold(), game_type)

        age_category = data["age_category"]
        existing_ages.setdefault(age_category.casefold(), age_category)

        for filename in parse_csv_files(row.get("files", "")):
            if (UPLOAD_DIR / filename).exists() or not filename:
                continue
            return False, f"Строка {index}: файл «{filename}» не найден в uploads."

        row_id = row.get("id", "").strip()
        if row_id:
            try:
                int(row_id)
            except ValueError:
                return False, f"Строка {index}: поле id должно быть целым числом."

    return True, ""


def import_games_from_csv(uploaded_file) -> tuple[bool, str]:
    raw_bytes = uploaded_file.read()
    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False, "CSV должен быть в кодировке UTF-8."

    dialect = sniff_csv_dialect(decoded[:2048])
    reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)
    if reader.fieldnames is None:
        return False, "CSV-файл пуст или не содержит заголовков."

    normalized_fieldnames = [str(name).strip() for name in reader.fieldnames]
    missing_fields = [field for field in CSV_EXPORT_FIELDS if field not in normalized_fieldnames]
    if missing_fields:
        missing = ", ".join(missing_fields)
        return False, f"В CSV отсутствуют колонки: {missing}."

    rows = []
    for row in reader:
        normalized_row = {str(key).strip(): (value or "") for key, value in row.items() if key is not None}
        if not any(str(value).strip() for value in normalized_row.values()):
            continue
        rows.append(normalized_row)

    if not rows:
        return False, "CSV не содержит строк с упражнениями."

    is_valid, error_message = validate_csv_rows(rows)
    if not is_valid:
        return False, error_message

    db = get_db()
    known_type_names = {name.casefold(): name for name in fetch_game_types()}
    known_age_names = {name.casefold(): name for name in fetch_age_categories()}

    try:
        db.execute("BEGIN")
        for row in rows:
            normalized_types = parse_multi_categories(row.get("game_type", ""))
            for game_type in normalized_types:
                if game_type.casefold() not in known_type_names:
                    db.execute("INSERT INTO game_types (name) VALUES (?)", (game_type,))
                    known_type_names[game_type.casefold()] = game_type

            age_category = row.get("age_category", "").strip()
            if age_category and age_category.casefold() not in known_age_names:
                db.execute("INSERT INTO age_categories (name) VALUES (?)", (age_category,))
                known_age_names[age_category.casefold()] = age_category

            payload = (
                row.get("title", "").strip(),
                join_multi_categories(normalized_types),
                row.get("goal", "").strip(),
                row.get("participants", "").strip(),
                age_category,
                row.get("duration", "").strip(),
                row.get("location", "").strip(),
                row.get("equipment", "").strip(),
                row.get("rules", "").strip(),
                json.dumps(parse_csv_files(row.get("files", "")), ensure_ascii=False),
                normalize_email(row.get("created_by_email", "")),
                row.get("created_by_name", "").strip(),
            )

            row_id = row.get("id", "").strip()
            if row_id:
                existing = db.execute("SELECT id FROM games WHERE id = ?", (int(row_id),)).fetchone()
                if existing:
                    db.execute(
                        """
                        UPDATE games
                        SET title = ?, game_type = ?, goal = ?, participants = ?,
                            age_category = ?, duration = ?, location = ?, equipment = ?,
                            rules = ?, files_json = ?, created_by_email = ?, created_by_name = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (*payload, int(row_id)),
                    )
                    continue

            db.execute(
                """
                INSERT INTO games (
                    title, game_type, goal, participants, age_category,
                    duration, location, equipment, rules, files_json,
                    created_by_email, created_by_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )

        db.commit()
    except sqlite3.Error:
        db.rollback()
        return False, "Не удалось импортировать упражнения из CSV."

    return True, f"Импортировано упражнений: {len(rows)}."


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
