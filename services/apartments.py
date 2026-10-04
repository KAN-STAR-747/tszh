"""Квартиры: реестр квартир, собственников и членов ТСЖ."""

import sqlite3

from db import database as db
from services import validation as check
from services.errors import AppError


def get_apartments(search="", only_members=False):
    """Возвращает список квартир с текущим долгом (можно искать и фильтровать)."""
    sql = (
        "SELECT a.apartment_id, a.number, a.area, a.owner_name, "
        f"a.owner_phone, a.is_member, {db.DEBT_SQL} AS debt "
        "FROM apartments a"
    )
    if only_members:
        sql += " WHERE a.is_member = 1"
    sql += " ORDER BY a.number"
    rows = db.query_all(sql)

    search = search.strip().lower()
    if search:
        rows = [
            row
            for row in rows
            if search == str(row["number"]) or search in row["owner_name"].lower()
        ]
    return rows


def get_apartment(apartment_id):
    """Возвращает одну квартиру по id или None."""
    return db.query_one("SELECT * FROM apartments WHERE apartment_id = ?", (apartment_id,))


def get_apartment_by_number(number):
    """Возвращает квартиру по её номеру (число) или None, если такой нет в реестре."""
    return db.query_one("SELECT * FROM apartments WHERE number = ?", (number,))


def get_summary():
    """Возвращает пару (всего квартир, из них членов ТСЖ)."""
    row = db.query_one(
        "SELECT COUNT(*) AS total, COALESCE(SUM(is_member), 0) AS members FROM apartments"
    )
    return row["total"], row["members"]


def save_apartment(data, apartment_id=None):
    """Добавляет квартиру (apartment_id=None) или изменяет существующую."""
    number = check.parse_positive_int(data["number"], "Номер квартиры")
    area = check.parse_positive_number(data["area"], "Площадь")
    owner_name = check.require_text(data["owner_name"], "ФИО собственника")
    owner_phone = check.check_phone(data["owner_phone"])
    is_member = 1 if data["is_member"] else 0
    try:
        if apartment_id is None:
            db.execute(
                "INSERT INTO apartments (number, area, owner_name, "
                "owner_phone, is_member) VALUES (?, ?, ?, ?, ?)",
                (number, area, owner_name, owner_phone, is_member),
            )
        else:
            db.execute(
                "UPDATE apartments SET number = ?, area = ?, owner_name = ?, "
                "owner_phone = ?, is_member = ? WHERE apartment_id = ?",
                (number, area, owner_name, owner_phone, is_member, apartment_id),
            )
    except sqlite3.IntegrityError:
        raise AppError(f"Квартира с номером {number} уже существует.") from None


def delete_apartment(apartment_id):
    """Удаляет квартиру, если к ней ничего не привязано."""
    apartment = get_apartment(apartment_id)
    try:
        db.execute("DELETE FROM apartments WHERE apartment_id = ?", (apartment_id,))
    except sqlite3.IntegrityError:
        raise AppError(
            f"Нельзя удалить квартиру {apartment['number']}: "
            "к ней привязаны начисления, оплаты или другие данные."
        ) from None
