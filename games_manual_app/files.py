import json
import secrets

from flask import flash
from werkzeug.utils import secure_filename

from .config import ALLOWED_EXTENSIONS, UPLOAD_DIR


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


def serialize_csv_files(value: str | None) -> str:
    return " | ".join(parse_files_json(value))


def parse_csv_files(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]
