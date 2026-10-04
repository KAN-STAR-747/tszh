"""Авторизация: регистрация, вход, подтверждение жильцов, данные пользователей."""

import hashlib
import os
import sqlite3

from db import database as db
from services import apartments
from services import validation as check
from services.errors import AppError


def make_hash(password, salt=None):
    """Считает хеш пароля SHA-256 с солью, возвращает строку «соль$хеш»."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def password_matches(password, stored_hash):
    """Проверяет пароль по хешу из базы."""
    salt = stored_hash.split("$")[0]
    return make_hash(password, salt) == stored_hash


def chairman_exists():
    """True, если председатель уже зарегистрирован (is_participant = 0)."""
    row = db.query_one("SELECT 1 FROM users WHERE is_participant = 0")
    return row is not None


def get_user(user_id):
    """Возвращает данные пользователя словарём или None."""
    row = db.query_one("SELECT * FROM users WHERE users_id = ?", (user_id,))
    return dict(row) if row else None


def get_chairman():
    """Возвращает ФИО и телефон председателя (или None, если его нет)."""
    row = db.query_one("SELECT full_name, phone FROM users WHERE is_participant = 0 LIMIT 1")
    return dict(row) if row else None


def register_chairman(data):
    """Регистрирует председателя и сохраняет данные ТСЖ (всё в одной транзакции)."""
    full_name = check.require_text(data["full_name"], "ФИО")
    phone = check.check_phone(data["phone"])
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    hoa_name = check.require_text(data["hoa_name"], "Наименование ТСЖ")
    inn = check.check_inn(data["inn"])
    address = check.require_text(data["address"], "Адрес дома")
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")

    try:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO hoa (name, inn, address, rate_per_m2) VALUES (?, ?, ?, ?)",
                (hoa_name, inn, address, rate),
            )
            conn.execute(
                "INSERT INTO users (login, password_hash, is_participant, full_name, "
                "phone, is_approved) VALUES (?, ?, 0, ?, ?, 1)",
                (login, make_hash(password), full_name, phone),
            )
    except sqlite3.IntegrityError:
        raise AppError("Такой логин уже занят.") from None


def is_owner_data(apartment, full_name, phone):
    """True, если ФИО и телефон совпадают с собственником квартиры из реестра."""
    same_phone = check.normalize_phone(phone) == check.normalize_phone(apartment["owner_phone"])
    return same_phone and check.same_surname(full_name, apartment["owner_name"])


def is_owner(user):
    """True, если пользователь (словарь из login_user) - собственник своей квартиры."""
    if not user.get("apartment_id"):
        return False
    apartment = apartments.get_apartment(user["apartment_id"])
    return apartment is not None and is_owner_data(apartment, user["full_name"], user["phone"])


def register_resident(data):
    """Регистрирует жильца. Возвращает True, если собственник и вход разрешён сразу."""
    full_name = check.require_text(data["full_name"], "ФИО")
    phone = check.check_phone(data["phone"])
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    number = check.parse_positive_int(data["apartment_number"], "Квартира")
    apartment = apartments.get_apartment_by_number(number)

    try:
        with db.transaction() as conn:
            if apartment is None:
                cursor = conn.execute(
                    "INSERT INTO apartments (number, area, owner_name, owner_phone, is_member) "
                    "VALUES (?, 0, ?, ?, 0)",
                    (number, full_name, phone),
                )
                apartment_id = cursor.lastrowid
                approved = 0
            else:
                apartment_id = apartment["apartment_id"]
                approved = 1 if is_owner_data(apartment, full_name, phone) else 0
            conn.execute(
                "INSERT INTO users (login, password_hash, is_participant, full_name, "
                "phone, apartment_id, is_approved) "
                "VALUES (?, ?, 1, ?, ?, ?, ?)",
                (login, make_hash(password), full_name, phone, apartment_id, approved),
            )
    except sqlite3.IntegrityError:
        raise AppError("Такой логин уже занят.") from None
    return bool(approved)


def login_user(login, password):
    """Проверяет логин и пароль, возвращает данные пользователя словарём."""
    row = db.query_one("SELECT * FROM users WHERE login = ?", (login.strip(),))
    if row is None or not password_matches(password, row["password_hash"]):
        raise AppError("Неверный логин или пароль.")
    if not row["is_approved"]:
        raise AppError("Аккаунт ожидает подтверждения председателем.")
    return dict(row)


def get_pending_residents():
    """Возвращает жильцов, которых председатель ещё не подтвердил."""
    return db.query_all(
        "SELECT u.users_id, u.full_name, u.phone, a.number, a.area "
        "FROM users u JOIN apartments a ON a.apartment_id = u.apartment_id "  # JOIN: берём номер
        "WHERE u.is_participant = 1 AND u.is_approved = 0 "
        "ORDER BY u.users_id"
    )


def get_residents():
    """Возвращает подтверждённых жильцов с данными их квартир (для окна «Жильцы»)."""
    return db.query_all(
        "SELECT a.number, u.full_name, a.is_member, a.area "
        "FROM users u JOIN apartments a ON a.apartment_id = u.apartment_id "
        "WHERE u.is_participant = 1 AND u.is_approved = 1 "
        "ORDER BY a.number, u.users_id"
    )


def approve_resident(user_id):
    """Подтверждает аккаунт жильца."""
    db.execute("UPDATE users SET is_approved = 1 WHERE users_id = ?", (user_id,))


def reject_resident(user_id):
    """Отклоняет заявку жильца: неподтверждённый аккаунт удаляется."""
    user = get_user(user_id)
    with db.transaction() as conn:
        conn.execute("DELETE FROM users WHERE users_id = ? AND is_approved = 0", (user_id,))
        if user is not None and user["apartment_id"] is not None:
            conn.execute(
                "DELETE FROM apartments WHERE apartment_id = ? AND area = 0 "
                "AND NOT EXISTS (SELECT 1 FROM users WHERE apartment_id = ?) "
                "AND NOT EXISTS (SELECT 1 FROM payment WHERE apartment_id = ?) "
                "AND NOT EXISTS (SELECT 1 FROM requests WHERE apartment_id = ?)",
                (user["apartment_id"],) * 4,
            )


def update_profile(user_id, full_name, phone):
    """Изменяет ФИО и телефон пользователя."""
    full_name = check.require_text(full_name, "ФИО")
    phone = check.check_phone(phone)
    user = get_user(user_id)
    with db.transaction() as conn:
        if user is not None and is_owner(user):
            conn.execute(
                "UPDATE apartments SET owner_name = ?, owner_phone = ? WHERE apartment_id = ?",
                (full_name, phone, user["apartment_id"]),
            )
        conn.execute(
            "UPDATE users SET full_name = ?, phone = ? WHERE users_id = ?",
            (full_name, phone, user_id),
        )


def update_chairman(user_id, data):
    """Изменяет данные председателя и данные ТСЖ (всё в одной транзакции)."""
    full_name = check.require_text(data["full_name"], "ФИО")
    phone = check.check_phone(data["phone"])
    hoa_name = check.require_text(data["hoa_name"], "Наименование ТСЖ")
    inn = check.check_inn(data["inn"])
    address = check.require_text(data["address"], "Адрес дома")
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")
    with db.transaction() as conn:
        conn.execute(
            "UPDATE users SET full_name = ?, phone = ? WHERE users_id = ?",
            (full_name, phone, user_id),
        )
        conn.execute(
            "UPDATE hoa SET name = ?, inn = ?, address = ?, rate_per_m2 = ?",
            (hoa_name, inn, address, rate),
        )
