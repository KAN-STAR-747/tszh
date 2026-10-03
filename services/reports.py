"""Отчёты: выгрузка данных в файлы Excel (.xlsx)."""

from openpyxl import Workbook

from db import database as db
from services import dates
from services import requests_service
from services import validation as check
from services.errors import AppError


def default_file_name(prefix):
    """Имя файла по умолчанию, например «Должники_2026-09-28.xlsx»."""
    day, month, year = dates.today_text().split(".")
    return f"{prefix}_{year}-{month}-{day}.xlsx"


def save_table(file_path, sheet_title, headers, rows):
    """Записывает таблицу в файл Excel (если файл открыт в Excel, будет PermissionError)."""
    book = Workbook()
    sheet = book.active
    sheet.title = sheet_title
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for column in sheet.columns:
        longest = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = longest + 3
    book.save(file_path)


def export_debtors(file_path):
    """Отчёт «Должники»: квартиры с долгом. Возвращает число выгруженных строк."""
    rows = db.query_all(
        "SELECT a.number, a.owner_name, a.owner_phone, "
        f"{db.DEBT_SQL} AS debt "
        f"FROM apartments a WHERE {db.DEBT_SQL} > 0 ORDER BY a.number"
    )
    table = [[r["number"], r["owner_name"], r["owner_phone"], r["debt"] / 100] for r in rows]
    save_table(file_path, "Должники", ["Квартира", "Собственник", "Телефон", "Долг, руб."], table)
    return len(table)


def export_requests(file_path, date_from_text, date_to_text):
    """Отчёт «Заявки за период» (даты в формате ДД.ММ.ГГГГ)."""
    date_from = check.parse_date(date_from_text, "с")
    date_to = check.parse_date(date_to_text, "по")
    if date_from > date_to:
        raise AppError("Дата «с» не может быть позже даты «по».")

    rows = requests_service.get_requests(date_from=date_from, date_to=date_to)
    table = [
        [
            r["title"],
            r["apartment_number"] or "Общедомовое",
            r["source"],
            r["status"],
            r["executor"] or "",
            r["created_at"],
            r["closed_at"] or "",
        ]
        for r in rows
    ]
    save_table(
        file_path,
        "Заявки",
        ["Тема", "Квартира", "Источник", "Статус", "Исполнитель", "Создана", "Закрыта"],
        table,
    )
    return len(table)


def export_members(file_path):
    """Отчёт «Реестр членов ТСЖ»."""
    rows = db.query_all(
        "SELECT number, owner_name, owner_phone, area FROM apartments "
        "WHERE is_member = 1 ORDER BY number"
    )
    table = [[r["number"], r["owner_name"], r["owner_phone"], r["area"]] for r in rows]
    save_table(file_path, "Члены ТСЖ", ["Квартира", "ФИО", "Телефон", "Площадь, м2"], table)
    return len(table)
