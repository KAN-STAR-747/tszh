"""Работа с базой данных SQLite.

Здесь подключение к БД, создание таблиц и функции-помощники для запросов.
Остальные модули обращаются к базе только через эти функции.
"""

import os  # os нужен, чтобы собирать пути к файлам
import sqlite3  # встроенная в Python библиотека для работы с SQLite
import sys  # sys нужен, чтобы понять, запущен ли обычный скрипт или exe
from contextlib import contextmanager  # позволяет сделать свою конструкцию "with ..."

DB_NAME = "tszh.db"  # имя файла, в котором будет лежать вся база

# Долг квартиры = сумма всех начислений минус сумма всех оплат.
# Этот кусок SQL нужен в нескольких запросах, поэтому вынесен в константу.
# В запросе таблица квартир обязана называться "a" (apartments AS a).
# COALESCE(..., 0) заменяет пустой результат (NULL) нулём, если начислений ещё нет.
DEBT_SQL = """(
    COALESCE((SELECT SUM(amount) FROM charges
              WHERE charges.apartment_id = a.apartment_id), 0)
    - COALESCE((SELECT SUM(amount) FROM payment
                WHERE payment.apartment_id = a.apartment_id), 0)
)"""

# Текст запроса, который создаёт все 6 таблиц из ER-диаграммы.
# IF NOT EXISTS - если таблица уже есть, повторно её не создаём.
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS hoa (
    hoa_id INTEGER PRIMARY KEY AUTOINCREMENT,   -- PK: номер записи, растёт сам
    name TEXT NOT NULL,                         -- NOT NULL: поле нельзя оставить пустым
    inn TEXT NOT NULL,
    address TEXT NOT NULL,
    rate_per_m2 INTEGER NOT NULL CHECK (rate_per_m2 > 0)  -- тариф в копейках, больше нуля
);

CREATE TABLE IF NOT EXISTS apartments (
    apartment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,             -- UNIQUE: двух одинаковых номеров не будет
    area REAL NOT NULL CHECK (area > 0),        -- площадь, м2 (REAL - дробное число)
    owner_name TEXT NOT NULL,
    owner_phone TEXT NOT NULL,
    is_member INTEGER NOT NULL DEFAULT 0        -- член ТСЖ: 1 - да, 0 - нет
);

CREATE TABLE IF NOT EXISTS users (
    users_id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,                -- пароль храним только в виде хеша
    -- is_participant: 1 - жилец (участник), 0 - председатель
    is_participant INTEGER NOT NULL DEFAULT 1 CHECK (is_participant IN (0, 1)),
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    apartment_id INTEGER REFERENCES apartments (apartment_id),  -- FK: связь с квартирой
    is_approved INTEGER NOT NULL DEFAULT 0      -- подтвердил ли председатель: 1 - да
);

CREATE TABLE IF NOT EXISTS charges (
    charges_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartments (apartment_id),
    period TEXT NOT NULL,                       -- месяц в виде 'ГГГГ-ММ'
    purpose TEXT NOT NULL,                      -- за что начислено
    amount INTEGER NOT NULL CHECK (amount > 0), -- сумма в копейках
    UNIQUE (apartment_id, period, purpose)      -- одно и то же начисление нельзя дублировать
);

CREATE TABLE IF NOT EXISTS payment (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartments (apartment_id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    paid_at TEXT NOT NULL,                      -- дата оплаты 'ГГГГ-ММ-ДД ЧЧ:ММ'
    comment TEXT
);

CREATE TABLE IF NOT EXISTS requests (
    requests_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users (users_id),
    apartment_id INTEGER REFERENCES apartments (apartment_id),
    title TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL CHECK (source IN ('Звонок', 'Приложение')),
    status TEXT NOT NULL DEFAULT 'Новая'
        CHECK (status IN ('Новая', 'В работе', 'Выполнена')),
    executor TEXT,                              -- исполнитель (пока может быть пустым)
    created_at TEXT NOT NULL,
    closed_at TEXT                              -- дата закрытия, пока заявка открыта - пусто
);
"""


def get_app_folder():
    """Возвращает папку, где лежит программа (рядом с ней будет файл базы)."""
    # Когда программа собрана в exe, у sys появляется атрибут frozen
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)  # папка, в которой лежит exe
    # Иначе берём папку проекта: на два уровня выше этого файла (db/database.py)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Полный путь к файлу базы данных
DB_PATH = os.path.join(get_app_folder(), DB_NAME)


def connect():
    """Открывает соединение с БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # к полям строки можно обращаться по имени: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")  # без этого SQLite не проверяет связи между таблицами
    return conn


def init_db():
    """Создаёт таблицы, если их ещё нет. Вызывается при запуске программы."""
    conn = connect()
    try:
        conn.executescript(CREATE_TABLES_SQL)  # executescript умеет выполнять сразу много команд
    finally:
        conn.close()  # соединение закрываем в любом случае, даже при ошибке


def query_all(sql, params=()):
    """Выполняет SELECT и возвращает все найденные строки списком."""
    conn = connect()
    try:
        # Значения передаём отдельно в params, а в тексте запроса ставим "?".
        # Так нельзя сломать запрос вводом пользователя (защита от SQL-инъекций).
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    """Выполняет SELECT и возвращает одну строку (или None, если ничего не найдено)."""
    conn = connect()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def execute(sql, params=()):
    """Выполняет INSERT, UPDATE или DELETE и возвращает id добавленной записи."""
    with transaction() as conn:  # транзакция сама сделает commit или rollback
        cursor = conn.execute(sql, params)
        return cursor.lastrowid  # id новой записи (нужен после INSERT)


@contextmanager
def transaction():
    """Транзакция: либо сохраняются все изменения, либо ни одно.

    Пример:
        with transaction() as conn:
            conn.execute("INSERT ...", (...))
            conn.execute("INSERT ...", (...))
    """
    conn = connect()
    try:
        yield conn  # здесь выполняется код из блока with
        conn.commit()  # ошибок не было - сохраняем всё сразу
    except Exception:
        conn.rollback()  # ошибка - отменяем все изменения блока
        raise  # и передаём ошибку дальше
    finally:
        conn.close()
