# База игр и упражнений

Flask-приложение для просмотра, добавления и администрирования базы игр и упражнений на SQLite.

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

После запуска приложение будет доступно на `http://127.0.0.1:5000`.

## Запуск через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

Приложение будет доступно на порту, указанном в `.env` через переменную `PORT`.
