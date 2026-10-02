"""Заявки на ремонт: создание, поиск, смена статуса."""

from db import database as db
from services import dates
from services import validation as check
from services.errors import AppError

STATUSES = ["Новая", "В работе", "Выполнена"]
SOURCES = ["Звонок", "Приложение"]

SELECT_SQL = """
SELECT r.requests_id, r.title, r.description, r.source, r.status,
       r.executor, r.created_at, r.closed_at, r.apartment_id,
       a.number AS apartment_number, u.full_name AS author_name
FROM requests r
LEFT JOIN apartments a ON a.apartment_id = r.apartment_id
LEFT JOIN users u ON u.users_id = r.user_id
"""


def create_request(user_id, apartment_id, title, description, source, executor=""):
    """Создаёт заявку со статусом «Новая» и возвращает её id."""
    title = check.require_text(title, "Тема")
    if source not in SOURCES:
        raise AppError("Выберите источник заявки.")
    return db.execute(
        "INSERT INTO requests (user_id, apartment_id, title, description, "
        "source, status, executor, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'Новая', ?, ?)",
        (
            user_id,
            apartment_id,
            title,
            description.strip(),
            source,
            executor.strip(),
            dates.now_text(),
        ),
    )


def get_requests(status=None, apartment_id=None, date_from=None, date_to=None):
    """Возвращает заявки (свежие сверху). Все фильтры необязательные."""
    conditions = []
    params = []
    if status:
        conditions.append("r.status = ?")
        params.append(status)
    if apartment_id:
        conditions.append("r.apartment_id = ?")
        params.append(apartment_id)
    if date_from:
        conditions.append("substr(r.created_at, 1, 10) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("substr(r.created_at, 1, 10) <= ?")
        params.append(date_to)

    sql = SELECT_SQL
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY r.created_at DESC, r.requests_id DESC"
    return db.query_all(sql, tuple(params))


def get_request(request_id):
    """Возвращает одну заявку или None."""
    return db.query_one(SELECT_SQL + " WHERE r.requests_id = ?", (request_id,))


def get_next_status(status):
    """Возвращает следующий статус или None, если заявка уже выполнена."""
    index = STATUSES.index(status)
    if index + 1 < len(STATUSES):
        return STATUSES[index + 1]
    return None


def move_to_next_status(request_id):
    """Переводит заявку в следующий статус. При «Выполнена» ставит дату закрытия."""
    request = get_request(request_id)
    new_status = get_next_status(request["status"])
    if new_status is None:
        raise AppError("Заявка уже выполнена.")
    closed_at = dates.now_text() if new_status == "Выполнена" else None
    db.execute(
        "UPDATE requests SET status = ?, closed_at = ? WHERE requests_id = ?",
        (new_status, closed_at, request_id),
    )


def set_executor(request_id, executor):
    """Записывает имя исполнителя в заявку."""
    db.execute(
        "UPDATE requests SET executor = ? WHERE requests_id = ?", (executor.strip(), request_id)
    )


def delete_request(request_id):
    """Удаляет заявку."""
    db.execute("DELETE FROM requests WHERE requests_id = ?", (request_id,))
