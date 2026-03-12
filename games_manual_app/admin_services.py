import sqlite3

from .config import ACCESS_ROLE_LABELS, ADMIN_EMAILS
from .db import fetch_access_rows, get_db
from .helpers import join_multi_categories, normalize_email, parse_multi_categories


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


def apply_bulk_access_updates(form) -> tuple[bool, str]:
    db = get_db()
    existing_rows = fetch_access_rows()
    existing_by_id = {
        str(row["id"]): {
            "email": row["email"],
            "role": row["role"],
        }
        for row in existing_rows
    }
    submitted_ids = form.getlist("item_id")
    submitted_emails = form.getlist("item_email")
    submitted_roles = form.getlist("item_role")
    delete_ids = set(form.getlist("delete_item"))
    new_admins = [normalize_email(item) for item in form.get("new_admins", "").splitlines() if normalize_email(item)]
    new_editors = [normalize_email(item) for item in form.get("new_editors", "").splitlines() if normalize_email(item)]

    if len(submitted_ids) != len(submitted_emails) or len(submitted_ids) != len(submitted_roles):
        return False, "Некорректные данные формы доступа."

    final_entries: list[tuple[str, str]] = []
    updates: list[tuple[str, str, str]] = []
    delete_row_ids: list[int] = []

    for item_id, raw_email, role in zip(submitted_ids, submitted_emails, submitted_roles):
        current = existing_by_id.get(item_id)
        if current is None:
            return False, "Один из пользователей доступа не найден."
        if role not in ACCESS_ROLE_LABELS:
            return False, "Указана неизвестная роль доступа."

        if item_id in delete_ids:
            delete_row_ids.append(int(item_id))
            continue

        normalized_email = normalize_email(raw_email)
        if not normalized_email:
            return False, "Email пользователя доступа не может быть пустым."

        final_entries.append((normalized_email, role))
        if normalized_email != current["email"] or role != current["role"]:
            updates.append((normalized_email, role, item_id))

    final_entries.extend((email, "admin") for email in new_admins)
    final_entries.extend((email, "editor") for email in new_editors)

    final_emails = [email for email, _role in final_entries]
    if len(final_emails) != len(set(final_emails)):
        return False, "В списке доступа найдены повторяющиеся email."

    admin_count = sum(1 for _email, role in final_entries if role == "admin")
    if admin_count == 0 and not ADMIN_EMAILS:
        return False, "Нельзя сохранить доступ без хотя бы одного администратора."

    try:
        db.execute("BEGIN")

        for normalized_email, role, item_id in updates:
            db.execute(
                "UPDATE access_users SET email = ?, role = ? WHERE id = ?",
                (normalized_email, role, item_id),
            )

        for row_id in delete_row_ids:
            db.execute("DELETE FROM access_users WHERE id = ?", (row_id,))

        for email in new_admins:
            db.execute("INSERT INTO access_users (email, role) VALUES (?, 'admin')", (email,))

        for email in new_editors:
            db.execute("INSERT INTO access_users (email, role) VALUES (?, 'editor')", (email,))

        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return False, "Не удалось сохранить доступ: найдено дублирующееся значение."

    return True, "Список пользователей с доступом обновлён."
