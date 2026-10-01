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

- `static/palette.css` — общие цвета, размеры, радиусы, тени и длительность переходов.
- `static/styles.css` — базовая типографика, контейнер и общие утилиты.
- `static/components/` — отдельный CSS-файл для каждого вида компонента:
  - `header.css`, `navigation.css`, `buttons.css`, `hero.css`, `panels.css` — шапка, навигация, кнопки и поверхности страниц;
  - `form-layout.css`, `fields.css`, `checkboxes.css`, `switches.css`, `selects.css`, `file-upload.css` — сетки форм и элементы управления;
  - `cards.css`, `dialog.css`, `tabs.css`, `tables.css`, `notices.css`, `properties.css`, `invites.css`, `empty-states.css` — карточки, диалоги и компоненты разделов.
- `static/site.js` — мобильная навигация.
- `static/game-cards.js`, `static/game-form.js`, `static/admin.js` — скрипты отдельных страниц.
- `templates/partials/game_body.html` — общие сведения, правила и файлы игры для каталога, личного раздела и полной карточки.

Стили подключаются в `templates/base.html` через `versioned_static` в порядке: палитра, базовые правила, компоненты. Адаптивные правила находятся в файле соответствующего компонента. Скрипты подключаются после содержимого страницы; общая логика загружается перед скриптом конкретной страницы.

Интерфейс использует однотонные тёмные поверхности, красный акцент, мягкие скругления и лёгкие тени. Чекбоксы сохраняют нативную семантику, но получают галочку, нарисованную CSS. Фильтр «Без оборудования» оформлен как тумблер и применяется вместе с остальными фильтрами кнопкой «Применить». У нативных выпадающих списков оформлены поле и стрелка; раскрытое меню остаётся системным. Типы игры выбираются в прокручиваемом списке чекбоксов; карточка открывается сразу, без анимации. Состояния фокуса поддерживают управление клавиатурой, переходы отключаются через `prefers-reduced-motion`, а режим `forced-colors` сохраняет различимость элементов. Дополнительный JavaScript для оформления не нужен.

## Проверка

После установки зависимостей:

```bash
python -m unittest discover -s tests -v
```

Тесты используют временную SQLite-базу и проверяют отображение игр, поиск, формы и доступ к разделам.
