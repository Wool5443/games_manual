from datetime import datetime

from flask import url_for

from .config import BASE_DIR


def versioned_static(filename: str) -> str:
    static_path = BASE_DIR / "static" / filename
    version = int(static_path.stat().st_mtime) if static_path.exists() else 0
    return url_for("static", filename=filename, v=version)


def normalize_email(value: str | None) -> str:
    return str(value or "").strip().casefold()


def format_datetime(value: str | None) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return "Не указано"

    normalized_value = raw_value.replace("Z", "+00:00")
    try:
        parsed_value = datetime.fromisoformat(normalized_value)
    except ValueError:
        try:
            parsed_value = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return raw_value

    return parsed_value.strftime("%d.%m.%Y %H:%M")


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


def safe_redirect_target(raw_target: str | None, fallback: str | None = None) -> str:
    if not raw_target:
        return fallback or url_for("admin_list")
    if raw_target.startswith("/") and not raw_target.startswith("//"):
        return raw_target
    return fallback or url_for("admin_list")
