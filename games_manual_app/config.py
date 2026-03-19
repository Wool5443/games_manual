import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
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

ACCESS_ROLE_LABELS = {
    "admin": "Администратор",
    "editor": "Добавление игр",
}

ADMIN_GAMES_ORDER_OPTIONS = {
    "desc": "Сначала новые",
    "asc": "Сначала старые",
}

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
    "created_at": "Дата добавления",
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
    created_by_email TEXT NOT NULL DEFAULT '',
    created_by_name TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS access_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invite_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('admin', 'editor')),
    created_by_email TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

IMPORTABLE_DB_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
IMPORTABLE_CSV_EXTENSIONS = {".csv"}

CSV_EXPORT_FIELDS = (
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
    "files",
    "created_by_email",
    "created_by_name",
)

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

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
MAX_CONTENT_LENGTH = 32 * 1024 * 1024

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
ADMIN_EMAILS = {email.strip().casefold() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()}
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
