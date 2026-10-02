"""Авторизация: регистрация, вход, подтверждение жильцов."""

import hashlib  # встроенная библиотека хеширования (SHA-256)
import os  # os.urandom даёт случайные байты для соли
import sqlite3

from db import database as db
from services import apartments
from services import validation as check
from services.errors import AppError


def make_hash(password, salt=None):
    """Считает хеш пароля SHA-256 с солью, возвращает строку «соль$хеш»."""
    if salt is None:  # при регистрации соли ещё нет - создаём случайную
        salt = os.urandom(16).hex()  # 16 случайных байт, записанных буквами и цифрами
    # Соль приписываем к паролю: одинаковые пароли получат разные хеши
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"  # храним вместе, чтобы потом знать соль


def password_matches(password, stored_hash):
    """Проверяет пароль по хешу из базы."""
    salt = stored_hash.split("$")[0]  # соль - часть до знака "$"
    return make_hash(password, salt) == stored_hash  # считаем хеш заново и сравниваем


def chairman_exists():
    """True, если председатель уже зарегистрирован (is_participant = 0)."""
    row = db.query_one("SELECT 1 FROM users WHERE is_participant = 0")
    return row is not None


def register_chairman(data):
    """Регистрирует председателя и сохраняет данные ТСЖ (всё в одной транзакции)."""
    # Проверяем все поля. Любая ошибка сразу прервёт функцию
    full_name = check.require_text(data["full_name"], "ФИО")
    phone = check.check_phone(data["phone"])
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    hoa_name = check.require_text(data["hoa_name"], "Наименование ТСЖ")
    inn = check.check_inn(data["inn"])
    address = check.require_text(data["address"], "Адрес дома")
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")

    try:
        # Две записи (ТСЖ и председатель) сохраняются вместе: или обе, или ни одной
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO hoa (name, inn, address, rate_per_m2) VALUES (?, ?, ?, ?)",
                (hoa_name, inn, address, rate),
            )
            # В запросе 0 - это председатель (is_participant), 1 - подтверждён (is_approved)
            conn.execute(
                "INSERT INTO users (login, password_hash, is_participant, full_name, "
                "phone, is_approved) VALUES (?, ?, 0, ?, ?, 1)",
                (login, make_hash(password), full_name, phone),
            )
    except sqlite3.IntegrityError:  # сработал UNIQUE по логину
        raise AppError("Такой логин уже занят.") from None


def register_resident(data):
    """Регистрирует жильца. Аккаунт создаётся неподтверждённым."""
    full_name = check.require_text(data["full_name"], "ФИО")
    phone = check.check_phone(data["phone"])
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    # Номер квартиры жилец вводит сам, а мы ищем такую квартиру в реестре
    apartment_id = apartments.find_apartment_id(data["apartment_number"])

    try:
        db.execute(
            "INSERT INTO users (login, password_hash, is_participant, full_name, "
            "phone, apartment_id, is_approved) "
            "VALUES (?, ?, 1, ?, ?, ?, 0)",  # 1 - жилец, 0 - ещё не подтверждён
            (login, make_hash(password), full_name, phone, apartment_id),
        )
    except sqlite3.IntegrityError:
        raise AppError("Такой логин уже занят.") from None


def login_user(login, password):
    """Проверяет логин и пароль, возвращает данные пользователя словарём."""
    row = db.query_one("SELECT * FROM users WHERE login = ?", (login.strip(),))
    # Одно и то же сообщение для неверного логина и пароля: так безопаснее
    if row is None or not password_matches(password, row["password_hash"]):
        raise AppError("Неверный логин или пароль.")
    if not row["is_approved"]:  # жилец ещё не подтверждён
        raise AppError("Аккаунт ожидает подтверждения председателем.")
    return dict(row)


def get_pending_residents():
    """Возвращает жильцов, которых председатель ещё не подтвердил."""
    return db.query_all(
        "SELECT u.users_id, u.full_name, u.phone, a.number "
        "FROM users u JOIN apartments a ON a.apartment_id = u.apartment_id "  # JOIN: берём номер
        "WHERE u.is_participant = 1 AND u.is_approved = 0 "
        "ORDER BY u.users_id"
    )


def approve_resident(user_id):
    """Подтверждает аккаунт жильца."""
    db.execute("UPDATE users SET is_approved = 1 WHERE users_id = ?", (user_id,))


def reject_resident(user_id):
    """Отклоняет заявку жильца: неподтверждённый аккаунт удаляется."""
    db.execute("DELETE FROM users WHERE users_id = ? AND is_approved = 0", (user_id,))


def update_profile(user_id, full_name, phone):
    """Изменяет ФИО и телефон пользователя."""
    full_name = check.require_text(full_name, "ФИО")
    phone = check.check_phone(phone)
    db.execute(
        "UPDATE users SET full_name = ?, phone = ? WHERE users_id = ?", (full_name, phone, user_id)
    )
