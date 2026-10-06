"""Авторизация: регистрация, вход, подтверждение жильцов, данные пользователей."""

import hashlib
import os
import sqlite3

from db import database as db
from services import apartments, hoa, mailer, password_generator
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


def check_chairman_data(data):
    """Проверяет поля регистрации председателя (без базы и сети), возвращает очищенные данные."""
    return {
        "full_name": check.check_full_name(data["full_name"]),
        "phone": check.check_phone(data["phone"]),
        "login": check.check_login(data["login"]),
        "password": check.check_password(data["password"], data["password2"]),
        "hoa_name": check.check_hoa_name(data["hoa_name"]),
        "inn": check.check_inn(data["inn"]),
        "address": check.require_text(data["address"], "Адрес дома"),
        "rate": check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2"),
    }


def ensure_login_free(login):
    """Ошибка, если пользователь с такой почтой (логином) уже есть."""
    if db.query_one("SELECT 1 FROM users WHERE login = ?", (login,)) is not None:
        raise AppError("Такой логин уже занят.")


def register_chairman(data):
    """Регистрирует председателя и сохраняет данные ТСЖ (всё в одной транзакции).

    Возвращает True, если адрес ТСЖ пока не оформлен полностью (нет связи) и ждёт в очереди.
    """
    fields = check_chairman_data(data)
    full_name, phone, login = fields["full_name"], fields["phone"], fields["login"]
    password, hoa_name, inn = fields["password"], fields["hoa_name"], fields["inn"]
    rate = fields["rate"]
    address, pending = hoa.prepare_address(fields["address"])

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
    return pending


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


def check_resident_data(data):
    """Проверяет поля регистрации жильца (без базы и сети), возвращает очищенные данные."""
    return {
        "full_name": check.check_full_name(data["full_name"]),
        "phone": check.check_phone(data["phone"]),
        "login": check.check_login(data["login"]),
        "password": check.check_password(data["password"], data["password2"]),
        "number": check.parse_positive_int(data["apartment_number"], "Квартира"),
    }


def register_resident(data):
    """Регистрирует жильца. Возвращает True, если собственник и вход разрешён сразу."""
    fields = check_resident_data(data)
    full_name, phone, login = fields["full_name"], fields["phone"], fields["login"]
    password, number = fields["password"], fields["number"]
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
    row = db.query_one("SELECT * FROM users WHERE login = ?", (login.strip().lower(),))
    if row is None or not password_matches(password, row["password_hash"]):
        raise AppError("Неверный логин или пароль.")
    if not row["is_approved"]:
        raise AppError("Аккаунт ожидает подтверждения председателем.")
    return dict(row)


def recover_account(login, chairman):
    """Восстановление аккаунта: новый пароль приходит на почту, указанную при регистрации.

    Пароль придумывает DeepSeek (services/password_generator.py). В базе он меняется
    только если письмо ушло: при сбое отправки старый пароль остаётся рабочим.

    Args:
        login (str): электронная почта (логин) пользователя.
        chairman (bool): True - аккаунт председателя, False - аккаунт жильца.
    """
    login = check.check_login(login)
    row = db.query_one(
        "SELECT users_id FROM users WHERE login = ? AND is_participant = ?",
        (login, 0 if chairman else 1),
    )
    if row is None:
        raise AppError("Аккаунт с такой электронной почтой не найден.")
    password = password_generator.generate_password()
    with db.transaction() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE users_id = ?",
            (make_hash(password), row["users_id"]),
        )
        mailer.send_password(login, password)


def get_pending_residents():
    """Возвращает жильцов, которых председатель ещё не подтвердил."""
    return db.query_all(
        "SELECT u.users_id, u.full_name, u.phone, a.number, a.area "
        "FROM users u JOIN apartments a ON a.apartment_id = u.apartment_id "
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


def update_profile(user_id, full_name, phone, new_password=None):
    """Изменяет ФИО и телефон пользователя (и пароль, если передан new_password)."""
    full_name = check.check_full_name(full_name)
    phone = check.check_phone(phone)
    if new_password is not None:
        new_password = check.check_password(new_password, new_password)
    user = get_user(user_id)
    with db.transaction() as conn:
        if new_password is not None:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE users_id = ?",
                (make_hash(new_password), user_id),
            )
        if user is not None and is_owner(user):
            conn.execute(
                "UPDATE apartments SET owner_name = ?, owner_phone = ? WHERE apartment_id = ?",
                (full_name, phone, user["apartment_id"]),
            )
        conn.execute(
            "UPDATE users SET full_name = ?, phone = ? WHERE users_id = ?",
            (full_name, phone, user_id),
        )


def update_chairman(user_id, data, new_password=None):
    """Изменяет данные председателя и данные ТСЖ (и пароль, если передан new_password).

    Всё сохраняется в одной транзакции: неверный пароль не оставляет частичных изменений.
    """
    full_name = check.check_full_name(data["full_name"])
    phone = check.check_phone(data["phone"])
    hoa_name = check.check_hoa_name(data["hoa_name"])
    inn = check.check_inn(data["inn"])
    address, _ = hoa.prepare_address(data["address"])
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")
    if new_password is not None:
        new_password = check.check_password(new_password, new_password)
    with db.transaction() as conn:
        if new_password is not None:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE users_id = ?",
                (make_hash(new_password), user_id),
            )
        conn.execute(
            "UPDATE users SET full_name = ?, phone = ? WHERE users_id = ?",
            (full_name, phone, user_id),
        )
        conn.execute(
            "UPDATE hoa SET name = ?, inn = ?, address = ?, rate_per_m2 = ?",
            (hoa_name, inn, address, rate),
        )
