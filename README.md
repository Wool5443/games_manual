# Простофиля

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
git clone https://github.com/Wool5443/games_manual.git
cd games_manual
cp .env.example .env
docker compose up -d --build
```

Приложение будет доступно на порту, указанном в `.env` через переменную `PORT`.

## Авторизация через Google

Для входа в админ-панель укажите в `.env`:

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
ADMIN_EMAILS=user1@example.com,user2@example.com
PUBLIC_BASE_URL=https://your-domain.example
```

В настройках OAuth-клиента Google добавьте redirect URI:

```text
http://127.0.0.1:5000/auth/google/callback
https://your-domain.example/auth/google/callback
```

Если приложение доступно на другом домене или порту, используйте этот адрес в redirect URI.
