"""Работа с базой данных SQLite.

Здесь подключение к БД, создание таблиц и функции-помощники для запросов.
Остальные модули обращаются к базе только через эти функции.
"""

import os
import sqlite3
import sys
from contextlib import contextmanager

DB_NAME = "tszh.db"

# COALESCE(..., 0) заменяет пустой результат (NULL) нулём, если начислений ещё нет.
DEBT_SQL = """(
    COALESCE((SELECT SUM(amount) FROM charges
              WHERE charges.apartment_id = a.apartment_id), 0)
    - COALESCE((SELECT SUM(amount) FROM payment
                WHERE payment.apartment_id = a.apartment_id), 0)
)"""

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS hoa (
    hoa_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    inn TEXT NOT NULL,
    address TEXT NOT NULL,
    rate_per_m2 INTEGER NOT NULL CHECK (rate_per_m2 > 0)
);

CREATE TABLE IF NOT EXISTS apartments (
    apartment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    number INTEGER NOT NULL UNIQUE,
    area REAL NOT NULL CHECK (area > 0),
    owner_name TEXT NOT NULL,
    owner_phone TEXT NOT NULL,
    is_member INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS users (
    users_id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_participant INTEGER NOT NULL DEFAULT 1 CHECK (is_participant IN (0, 1)),
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    apartment_id INTEGER REFERENCES apartments (apartment_id),
    is_approved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS charges (
    charges_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartments (apartment_id),
    period TEXT NOT NULL,
    purpose TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0),
    UNIQUE (apartment_id, period, purpose)
);

CREATE TABLE IF NOT EXISTS payment (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartments (apartment_id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    paid_at TEXT NOT NULL,
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
    executor TEXT,
    created_at TEXT NOT NULL,
    closed_at TEXT
);
"""


def get_app_folder():
    """Возвращает папку, где лежит программа (рядом с ней будет файл базы)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DB_PATH = os.path.join(get_app_folder(), DB_NAME)


def connect():
    """Открывает соединение с БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Создаёт таблицы, если их ещё нет. Вызывается при запуске программы."""
    conn = connect()
    try:
        conn.executescript(CREATE_TABLES_SQL)
    finally:
        conn.close()


def query_all(sql, params=()):
    """Выполняет SELECT и возвращает все найденные строки списком."""
    conn = connect()
    try:
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
    with transaction() as conn:
        cursor = conn.execute(sql, params)
        return cursor.lastrowid


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
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
