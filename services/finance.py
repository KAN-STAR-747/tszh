"""Финансы: начисления, целевые сборы, оплаты, долги.

Все суммы хранятся в копейках (целые числа), чтобы не терять точность.
"""

import sqlite3

from db import database as db
from services import dates, hoa
from services import validation as check
from services.errors import AppError

MAINTENANCE = "Содержание"  # назначение ежемесячного начисления


def calc_charge(area, tariff):
    """Ежемесячное начисление в копейках: площадь * тариф (за 1 м2)."""
    return round(area * tariff)  # round округляет до целой копейки


def get_apartments_for_charge():
    """Возвращает id и площадь всех квартир."""
    return db.query_all("SELECT apartment_id, area FROM apartments")


def charge_month(month):
    """Начисляет плату за содержание всем квартирам за месяц (ГГГГ-ММ)."""
    tariff = hoa.get_tariff()
    apartments = get_apartments_for_charge()
    if not apartments:
        raise AppError("Нет ни одной квартиры для начисления.")

    # Защита от повторного начисления за тот же месяц
    already = db.query_one(
        "SELECT 1 FROM charges WHERE period = ? AND purpose = ?", (month, MAINTENANCE)
    )
    if already:
        raise AppError(
            f"Начисление «{MAINTENANCE}» за "
            f"{dates.month_to_text(month).lower()} уже создано.\n"
            "Повторное начисление невозможно."
        )

    # Все начисления записываем одной транзакцией: либо для всех квартир, либо ни для одной
    with db.transaction() as conn:
        for apartment in apartments:
            conn.execute(
                "INSERT INTO charges (apartment_id, period, purpose, amount) VALUES (?, ?, ?, ?)",
                (
                    apartment["apartment_id"],
                    month,
                    MAINTENANCE,
                    calc_charge(apartment["area"], tariff),
                ),
            )
    return len(apartments)  # сколько начислений создано


def charge_target(purpose, amount_text, month):
    """Создаёт целевой сбор для всех квартир. Возвращает (сколько начислений, общая сумма)."""
    purpose = check.require_text(purpose, "Назначение")
    if purpose.lower() == MAINTENANCE.lower():  # это назначение занято
        raise AppError(f"Назначение «{MAINTENANCE}» занято ежемесячным начислением.")
    amount = check.rubles_to_kopecks(amount_text, "Сумма с квартиры")
    apartments = get_apartments_for_charge()
    if not apartments:
        raise AppError("Нет ни одной квартиры для начисления.")

    try:
        with db.transaction() as conn:
            for apartment in apartments:
                conn.execute(
                    "INSERT INTO charges (apartment_id, period, purpose, amount) "
                    "VALUES (?, ?, ?, ?)",
                    (apartment["apartment_id"], month, purpose, amount),
                )
    except sqlite3.IntegrityError:  # сработал UNIQUE (квартира + месяц + назначение)
        raise AppError("Сбор с таким назначением за этот месяц уже начислен.") from None
    return len(apartments), amount * len(apartments)


def add_payment(apartment_id, amount_text, date_text, comment):
    """Вносит оплату по квартире (дата в формате ДД.ММ.ГГГГ)."""
    if not apartment_id:
        raise AppError("Выберите квартиру.")
    amount = check.rubles_to_kopecks(amount_text, "Сумма")
    paid_at = check.parse_date(date_text, "Дата оплаты")
    db.execute(
        "INSERT INTO payment (apartment_id, amount, paid_at, comment) VALUES (?, ?, ?, ?)",
        (apartment_id, amount, paid_at, comment.strip()),
    )


def get_month_table(month):
    """Таблица для вкладки «Финансы»: по каждой квартире начислено, оплачено, долг."""
    # В скобках - вложенные запросы: сумма начислений и сумма оплат за выбранный месяц.
    # substr(p.paid_at, 1, 7) берёт из даты оплаты только «ГГГГ-ММ».
    return db.query_all(
        "SELECT a.apartment_id, a.number, a.owner_name, "
        "COALESCE((SELECT SUM(amount) FROM charges c "
        "          WHERE c.apartment_id = a.apartment_id "
        "          AND c.period = ?), 0) AS charged, "
        "COALESCE((SELECT SUM(amount) FROM payment p "
        "          WHERE p.apartment_id = a.apartment_id "
        "          AND substr(p.paid_at, 1, 7) = ?), 0) AS paid, "
        f"{db.DEBT_SQL} AS debt "  # долг считается за всё время, а не за месяц
        "FROM apartments a ORDER BY a.number",
        (month, month),
    )


def get_resident_summary(apartment_id):
    """Данные для кабинета жильца: итоги и история операций."""
    charges = db.query_all(
        "SELECT period, purpose, amount FROM charges WHERE apartment_id = ?", (apartment_id,)
    )
    payments = db.query_all(
        "SELECT paid_at, comment, amount FROM payment WHERE apartment_id = ?", (apartment_id,)
    )
    # Складываем начисления и оплаты в один список кортежей (дата, операция, назначение, сумма)
    history = []
    for row in charges:
        history.append((row["period"], "Начисление", row["purpose"], row["amount"]))
    for row in payments:
        purpose = row["comment"] or "Оплата"  # если комментария нет - пишем «Оплата»
        history.append((row["paid_at"], "Оплата", purpose, -row["amount"]))  # оплата со знаком «-»
    history.sort(key=lambda item: item[0], reverse=True)  # свежие сверху

    charged = sum(row["amount"] for row in charges)
    paid = sum(row["amount"] for row in payments)
    return {"charged": charged, "paid": paid, "debt": charged - paid, "history": history}


def get_charges(apartment_id):
    """Возвращает начисления квартиры, самые свежие сверху."""
    return db.query_all(
        "SELECT charges_id, period, purpose, amount FROM charges "
        "WHERE apartment_id = ? ORDER BY period DESC, charges_id DESC",
        (apartment_id,),
    )


def update_charge(charge_id, amount_text):
    """Изменяет сумму начисления (например, при ошибке расчёта)."""
    amount = check.rubles_to_kopecks(amount_text, "Сумма")
    db.execute("UPDATE charges SET amount = ? WHERE charges_id = ?", (amount, charge_id))


def delete_charge(charge_id):
    """Удаляет начисление."""
    db.execute("DELETE FROM charges WHERE charges_id = ?", (charge_id,))


def get_payments(apartment_id):
    """Возвращает оплаты квартиры, самые свежие сверху."""
    return db.query_all(
        "SELECT payment_id, paid_at, amount, comment FROM payment "
        "WHERE apartment_id = ? ORDER BY paid_at DESC, payment_id DESC",
        (apartment_id,),
    )


def update_payment(payment_id, amount_text, date_text, comment):
    """Изменяет сумму, дату и комментарий оплаты."""
    amount = check.rubles_to_kopecks(amount_text, "Сумма")
    paid_at = check.parse_date(date_text, "Дата оплаты")
    db.execute(
        "UPDATE payment SET amount = ?, paid_at = ?, comment = ? WHERE payment_id = ?",
        (amount, paid_at, comment.strip(), payment_id),
    )


def delete_payment(payment_id):
    """Удаляет оплату."""
    db.execute("DELETE FROM payment WHERE payment_id = ?", (payment_id,))
