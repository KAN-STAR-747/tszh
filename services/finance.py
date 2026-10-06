"""Финансы: начисления, целевые сборы, оплаты, долги.

Все суммы хранятся в копейках (целые числа), чтобы не терять точность.
"""

import sqlite3

from db import database as db
from services import dates, hoa
from services import validation as check
from services.errors import AppError

MAINTENANCE = "Содержание"


def calc_charge(area, tariff):
    """Ежемесячное начисление в копейках: площадь * тариф (за 1 м2)."""
    return round(area * tariff)


def get_apartments_for_charge():
    """Возвращает id и площадь квартир, которым можно начислять (площадь больше нуля)."""
    return db.query_all("SELECT apartment_id, area FROM apartments WHERE area > 0")


def charge_month(month):
    """Начисляет плату за содержание всем квартирам за месяц (ГГГГ-ММ)."""
    tariff = hoa.get_tariff()
    apartments = get_apartments_for_charge()
    if not apartments:
        raise AppError("Нет ни одной квартиры для начисления.")

    already = db.query_one(
        "SELECT 1 FROM charges WHERE period = ? AND purpose = ?", (month, MAINTENANCE)
    )
    if already:
        raise AppError(
            f"Начисление «{MAINTENANCE}» за "
            f"{dates.month_to_text(month).lower()} уже создано.\n"
            "Повторное начисление невозможно."
        )

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
    return len(apartments)


def charge_target(purpose, amount_text, month):
    """Создаёт целевой сбор для всех квартир. Возвращает (сколько начислений, общая сумма)."""
    purpose = check.require_text(purpose, "Назначение")
    purpose = check.check_length(purpose, check.MAX_PURPOSE, "Назначение")
    if purpose.lower() == MAINTENANCE.lower():
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
    except sqlite3.IntegrityError:
        raise AppError("Сбор с таким назначением за этот месяц уже начислен.") from None
    return len(apartments), amount * len(apartments)


def add_payment(apartment_id, amount_text, date_text, comment):
    """Вносит оплату по квартире (дата в формате ДД.ММ.ГГГГ)."""
    if not apartment_id:
        raise AppError("Выберите квартиру.")
    amount = check.rubles_to_kopecks(amount_text, "Сумма")
    paid_at = check.parse_date(date_text, "Дата оплаты")
    comment = check.check_length(comment, check.MAX_COMMENT, "Комментарий")
    db.execute(
        "INSERT INTO payment (apartment_id, amount, paid_at, comment) VALUES (?, ?, ?, ?)",
        (apartment_id, amount, paid_at, comment),
    )


def get_month_table(month):
    """Таблица для вкладки «Финансы»: по каждой квартире начислено, оплачено, долг."""
    return db.query_all(
        "SELECT a.apartment_id, a.number, a.owner_name, "
        "COALESCE((SELECT SUM(amount) FROM charges c "
        "          WHERE c.apartment_id = a.apartment_id "
        "          AND c.period = ?), 0) AS charged, "
        "COALESCE((SELECT SUM(amount) FROM payment p "
        "          WHERE p.apartment_id = a.apartment_id "
        "          AND substr(p.paid_at, 1, 7) = ?), 0) AS paid, "
        f"{db.DEBT_SQL} AS debt "
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
    history = []
    for row in charges:
        history.append((row["period"], "Начисление", row["purpose"], row["amount"]))
    for row in payments:
        purpose = row["comment"] or "Оплата"
        history.append((row["paid_at"], "Оплата", purpose, -row["amount"]))
    history.sort(key=lambda item: item[0], reverse=True)

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
    comment = check.check_length(comment, check.MAX_COMMENT, "Комментарий")
    db.execute(
        "UPDATE payment SET amount = ?, paid_at = ?, comment = ? WHERE payment_id = ?",
        (amount, paid_at, comment, payment_id),
    )


def delete_payment(payment_id):
    """Удаляет оплату."""
    db.execute("DELETE FROM payment WHERE payment_id = ?", (payment_id,))


def get_all_payments():
    """Все оплаты по всем квартирам для окна «Оплаты», свежие сверху."""
    return db.query_all(
        "SELECT p.payment_id, a.number, p.amount, p.paid_at, p.comment "
        "FROM payment p JOIN apartments a ON a.apartment_id = p.apartment_id "
        "ORDER BY p.paid_at DESC, p.payment_id DESC"
    )


def get_target_charges():
    """Целевые сборы для окна «Все целевые сборы»: сумма с квартиры и сколько квартир оплатило.

    Считаем так: квартира гасит начисления по порядку месяцев, от старых к новым.
    Сбор считается оплаченным квартирой, если все её оплаты покрывают начисления
    до этого сбора включительно.
    """
    charges = db.query_all(
        "SELECT charges_id, apartment_id, period, purpose, amount FROM charges "
        "ORDER BY period, charges_id"
    )
    paid = {
        row["apartment_id"]: row["total"]
        for row in db.query_all(
            "SELECT apartment_id, SUM(amount) AS total FROM payment GROUP BY apartment_id"
        )
    }
    running = {}
    groups = {}
    for row in charges:
        apartment_id = row["apartment_id"]
        running[apartment_id] = running.get(apartment_id, 0) + row["amount"]
        if row["purpose"] == MAINTENANCE:
            continue
        group = groups.setdefault(
            (row["period"], row["purpose"]), {"amount": row["amount"], "paid": 0}
        )
        if running[apartment_id] <= paid.get(apartment_id, 0):
            group["paid"] += 1
    result = [
        {"period": period, "purpose": purpose, "amount": group["amount"], "paid": group["paid"]}
        for (period, purpose), group in groups.items()
    ]
    result.sort(key=lambda item: item["period"], reverse=True)
    return result
