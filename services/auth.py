"""Авторизация: регистрация, вход, подтверждение жильцов, данные пользователей."""

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


def is_owner_data(apartment, full_name, phone):
    """True, если ФИО и телефон совпадают с собственником квартиры из реестра."""
    # Совпасть должны фамилия и телефон; в телефоне «+7» и «8» в начале считаются одним и тем же
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
    # Номер квартиры жилец вводит сам; сначала проверяем, что это число
    number = check.parse_positive_int(data["apartment_number"], "Квартира")
    apartment = apartments.get_apartment_by_number(number)

    try:
        with db.transaction() as conn:
            if apartment is None:
                # Квартиры нет в реестре: создаём её, жилец становится собственником.
                # Площадь пока 0: председатель внесёт её, когда подтвердит жильца.
                cursor = conn.execute(
                    "INSERT INTO apartments (number, area, owner_name, owner_phone, is_member) "
                    "VALUES (?, 0, ?, ?, 0)",
                    (number, full_name, phone),
                )
                apartment_id = cursor.lastrowid
                approved = 0  # подтверждает председатель
            else:
                apartment_id = apartment["apartment_id"]
                # Собственник из реестра (совпали телефон и фамилия) входит без подтверждения
                approved = 1 if is_owner_data(apartment, full_name, phone) else 0
            conn.execute(
                "INSERT INTO users (login, password_hash, is_participant, full_name, "
                "phone, apartment_id, is_approved) "
                "VALUES (?, ?, 1, ?, ?, ?, ?)",  # 1 - жилец
                (login, make_hash(password), full_name, phone, apartment_id, approved),
            )
    except sqlite3.IntegrityError:
        # Откатилась вся транзакция, в том числе созданная квартира
        raise AppError("Такой логин уже занят.") from None
    return bool(approved)


def login_user(login, password):
    """Проверяет логин и пароль, возвращает данные пользователя словарём."""
    row = db.query_one("SELECT * FROM users WHERE login = ?", (login.strip(),))
    # Одно и то же сообщение для неверного логина и пароля: так безопаснее
    if row is None or not password_matches(password, row["password_hash"]):
        raise AppError("Неверный логин или пароль.")
    if not row["is_approved"]:  # жилец ещё не подтверждён
        raise AppError("Аккаунт ожидает подтверждения председателем.")
    return dict(row)


def same_person(user, full_name, phone):
    """True, если ФИО и телефон совпали с данными пользователя из базы.

    ФИО сравнивается без учёта регистра и лишних пробелов, телефон - по цифрам («+7» = «8»).
    """
    same_name = " ".join(full_name.lower().split()) == " ".join(user["full_name"].lower().split())
    return same_name and check.normalize_phone(phone) == check.normalize_phone(user["phone"])


def change_credentials(user_id, login, password):
    """Записывает новый логин и новый хеш пароля. Занятый чужой логин - ошибка."""
    try:
        db.execute(
            "UPDATE users SET login = ?, password_hash = ? WHERE users_id = ?",
            (login, make_hash(password), user_id),
        )
    except sqlite3.IntegrityError:  # сработал UNIQUE по логину
        raise AppError("Такой логин уже занят.") from None


def recover_chairman(data):
    """Восстановление аккаунта председателя: ФИО, телефон и ИНН ТСЖ -> новый логин и пароль."""
    # Новые логин и пароль проверяем сразу: об их ошибках можно сказать честно
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    row = db.query_one("SELECT * FROM users WHERE is_participant = 0 LIMIT 1")
    info = db.query_one("SELECT inn FROM hoa LIMIT 1")
    # Одно сообщение на любую неверную комбинацию: так нельзя подобрать данные по частям
    if row is None or info is None or not same_person(row, data["full_name"], data["phone"]):
        raise AppError("Данные указаны неверно")
    if info["inn"] != data["inn"].strip():
        raise AppError("Данные указаны неверно")
    change_credentials(row["users_id"], login, password)


def recover_resident(data):
    """Восстановление аккаунта жильца: ФИО, телефон и номер квартиры -> новый логин и пароль."""
    login = check.check_login(data["login"])
    password = check.check_password(data["password"], data["password2"])
    number = check.parse_positive_int(data["apartment_number"], "Квартира")
    rows = db.query_all(
        "SELECT u.* FROM users u JOIN apartments a ON a.apartment_id = u.apartment_id "
        "WHERE u.is_participant = 1 AND a.number = ?",
        (number,),
    )
    for row in rows:
        if same_person(row, data["full_name"], data["phone"]):
            change_credentials(row["users_id"], login, password)
            return
    raise AppError("Данные указаны неверно")


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
            # Квартира, созданная при регистрации (площадь 0), без жильцов, оплат и заявок не нужна
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
        # Собственник остаётся собственником и после смены данных: правим и запись о квартире
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
