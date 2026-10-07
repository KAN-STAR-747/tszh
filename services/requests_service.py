"""Заявки на ремонт: создание, поиск, смена статуса."""

from db import database as db
from services import dates
from services import validation as check
from services.errors import AppError

STATUSES = ["Новая", "В работе", "Выполнена"]
SOURCES = ["Звонок", "Приложение"]

SELECT_SQL = """
SELECT r.requests_id, r.title, r.description, r.source, r.status,
       r.executor, r.created_at, r.closed_at, r.apartment_id, r.user_id,
       a.number AS apartment_number, u.full_name AS author_name
FROM requests r
LEFT JOIN apartments a ON a.apartment_id = r.apartment_id
LEFT JOIN users u ON u.users_id = r.user_id
"""


def create_request(user_id, apartment_id, title, description, source, executor=""):
    """Создаёт заявку со статусом «Новая» и возвращает её id."""
    title = check.check_length(check.require_text(title, "Тема"), check.MAX_TITLE, "Тема")
    description = check.check_length(description, check.MAX_DESCRIPTION, "Описание")
    executor = check.check_length(executor, check.MAX_EXECUTOR, "Исполнитель")
    if source not in SOURCES:
        raise AppError("Выберите источник заявки.")
    return db.execute(
        "INSERT INTO requests (user_id, apartment_id, title, description, "
        "source, status, executor, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'Новая', ?, ?)",
        (user_id, apartment_id, title, description, source, executor, dates.now_text()),
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


def return_to_new(request_id):
    """Отменяет взятие в работу: заявка «В работе» снова становится «Новой»."""
    request = get_request(request_id)
    if request is None or request["status"] != "В работе":
        raise AppError("Отменить можно только заявку со статусом «В работе».")
    db.execute("UPDATE requests SET status = 'Новая' WHERE requests_id = ?", (request_id,))


def update_request(request_id, description, executor):
    """Изменяет описание и исполнителя заявки. Выполненную заявку менять нельзя."""
    request = get_request(request_id)
    if request is None:
        raise AppError("Заявка не найдена.")
    if request["status"] == "Выполнена":
        raise AppError("Выполненную заявку изменять нельзя.")
    description = check.check_length(description, check.MAX_DESCRIPTION, "Описание")
    executor = check.check_length(executor, check.MAX_EXECUTOR, "Исполнитель")
    db.execute(
        "UPDATE requests SET description = ?, executor = ? WHERE requests_id = ?",
        (description, executor, request_id),
    )


def delete_request(request_id):
    """Удаляет заявку."""
    db.execute("DELETE FROM requests WHERE requests_id = ?", (request_id,))


def delete_own_request(user_id, request_id):
    """Жилец удаляет свою заявку, пока у неё статус «Новая»."""
    request = get_request(request_id)
    if request is None or request["user_id"] != user_id:
        raise AppError("Можно удалить только свою заявку.")
    if request["status"] != "Новая":
        raise AppError("Удалить можно только заявку со статусом «Новая».")
    delete_request(request_id)
