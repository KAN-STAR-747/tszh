"""Подтверждение почты кодом из 4 цифр при регистрации.

Порядок: человек заполняет форму -> start() проверяет данные и отправляет код на его почту ->
человек вводит код -> confirm() создаёт аккаунт. Пока код не введён, в базе ничего нет:
ожидающие регистрации лежат только в памяти программы (в базу данных ничего не добавляется).
"""

import secrets
import string
import time

from services import auth, mailer
from services.errors import AppError

CODE_LENGTH = 4
LIFETIME_SECONDS = 600  # код действует 10 минут
MAX_ATTEMPTS = 5  # неверных вводов до сброса регистрации
RESEND_SECONDS = 30  # как часто можно просить новый код

CHAIRMAN = "chairman"
RESIDENT = "resident"

# почта -> {"kind", "data", "code", "expires", "sent", "attempts"}
_pending = {}


def now():
    """Текущее время в секундах (отдельная функция, чтобы тесты могли его подменить)."""
    return time.monotonic()


def make_code():
    """Случайный код из 4 цифр (модуль secrets - для секретных значений)."""
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def reset():
    """Забывает все ожидающие регистрации (для тестов)."""
    _pending.clear()


def _issue(login, kind, data):
    """Создаёт код, отправляет его и запоминает регистрацию (не отправилось - не запоминает)."""
    code = make_code()
    mailer.send_code(login, code)
    moment = now()
    _pending[login] = {
        "kind": kind,
        "data": dict(data),
        "code": code,
        "expires": moment + LIFETIME_SECONDS,
        "sent": moment,
        "attempts": 0,
    }


def start(kind, data):
    """Проверяет данные формы и отправляет код на почту. Возвращает почту (она же логин).

    Args:
        kind: CHAIRMAN или RESIDENT.
        data (dict): поля формы регистрации.
    """
    if kind == CHAIRMAN:
        fields = auth.check_chairman_data(data)
    elif kind == RESIDENT:
        fields = auth.check_resident_data(data)
    else:
        raise ValueError(kind)
    login = fields["login"]
    auth.ensure_login_free(login)  # о занятой почте скажем сразу, а не после ввода кода
    _issue(login, kind, data)
    return login


def resend(login):
    """Отправляет новый код (старый перестаёт действовать)."""
    entry = _pending.get(login)
    if entry is None:
        raise AppError("Регистрация не найдена. Заполните форму заново.")
    wait = RESEND_SECONDS - (now() - entry["sent"])
    if wait > 0:
        raise AppError(f"Новый код можно запросить через {int(wait) + 1} с.")
    _issue(login, entry["kind"], entry["data"])


def cancel(login):
    """Отменяет ожидающую регистрацию."""
    _pending.pop(login, None)


def confirm(login, code):
    """Проверяет код и создаёт аккаунт. Возвращает результат auth.register_chairman/resident."""
    entry = _pending.get(login)
    if entry is None:
        raise AppError("Регистрация не найдена. Заполните форму заново.")
    if now() > entry["expires"]:
        del _pending[login]
        raise AppError("Код устарел. Заполните форму и получите новый код.")
    if not secrets.compare_digest(code.strip(), entry["code"]):
        entry["attempts"] += 1
        left = MAX_ATTEMPTS - entry["attempts"]
        if left <= 0:
            del _pending[login]
            raise AppError("Слишком много неверных попыток. Заполните форму заново.")
        raise AppError(f"Неверный код. Осталось попыток: {left}.")
    del _pending[login]
    if entry["kind"] == CHAIRMAN:
        return auth.register_chairman(entry["data"])
    return auth.register_resident(entry["data"])
