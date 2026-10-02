"""Данные ТСЖ: название, адрес, тариф."""

from db import database as db  # короткое имя db, чтобы писать db.query_one(...)
from services import validation as check  # проверки ввода
from services.errors import AppError


def get_hoa():
    """Возвращает данные ТСЖ словарём или None, если они не заполнены."""
    row = db.query_one("SELECT * FROM hoa LIMIT 1")  # в таблице всегда одна запись
    return dict(row) if row else None  # dict(row) превращает строку БД в обычный словарь


def get_tariff():
    """Возвращает тариф за 1 м2 в копейках."""
    hoa = get_hoa()
    if hoa is None:
        raise AppError("Данные ТСЖ не заполнены.")
    return hoa["rate_per_m2"]


def update_hoa(data):
    """Изменяет данные ТСЖ. data - словарь: hoa_name, inn, address, rate (рубли)."""
    # Сначала проверяем каждое поле. Если что-то неверно - сразу выйдет AppError
    name = check.require_text(data["hoa_name"], "Наименование ТСЖ")
    inn = check.check_inn(data["inn"])
    address = check.require_text(data["address"], "Адрес дома")
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")
    if get_hoa() is None:
        raise AppError("Данные ТСЖ не заполнены.")
    # Знаки "?" заменятся значениями из кортежа по порядку
    db.execute(
        "UPDATE hoa SET name = ?, inn = ?, address = ?, rate_per_m2 = ?", (name, inn, address, rate)
    )


def delete_hoa():
    """Удаляет данные ТСЖ, если в реестре нет квартир."""
    if db.query_one("SELECT 1 FROM apartments") is not None:
        raise AppError("Нельзя удалить данные ТСЖ: в реестре есть квартиры.")
    db.execute("DELETE FROM hoa")
