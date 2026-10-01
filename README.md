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

## Структура интерфейса

- `static/palette.css` — цвета и общие переменные оформления.
- `static/styles.css` — основной макет, навигация, кнопки и админ-панель.
- `static/forms.css` — поля форм, выпадающие списки, загрузка файлов и переключатели.
- `static/cards.css` — карточки игр и модальное окно.
- `static/site.js` — общая навигация и единая логика выпадающих списков.
- `static/game-cards.js`, `static/game-form.js`, `static/admin.js` — скрипты отдельных страниц.
- `templates/partials/game_body.html` — общие сведения, правила и файлы игры для каталога, личного раздела и полной карточки.

Стили подключаются в `templates/base.html` в порядке: палитра, основной макет, формы, карточки. Каждый файл содержит собственные адаптивные правила. Скрипты подключаются после содержимого страницы; общая логика загружается перед скриптом конкретной страницы.

## Проверка

После установки зависимостей:

```bash
python -m unittest discover -s tests -v
```

Тесты используют временную SQLite-базу и проверяют отображение игр, поиск, формы и доступ к разделам.
