"""Проверка данных, которые вводит пользователь."""

import re
from datetime import datetime

from services.errors import AppError

MIN_PASSWORD_LENGTH = 6


def require_text(value, field_name):
    """Проверяет, что поле не пустое, и возвращает текст без пробелов по краям."""
    value = value.strip()
    if not value:
        raise AppError(f"Поле «{field_name}» не может быть пустым.")
    return value


def check_inn(value):
    """Проверяет ИНН: ровно 10 цифр."""
    value = value.strip()
    if not (value.isdigit() and len(value) == 10):
        raise AppError("ИНН должен состоять ровно из 10 цифр.")
    return value


def check_phone(value):
    """Проверяет телефон: цифры и необязательный «+» в начале."""
    phone = value.replace(" ", "")
    if not re.fullmatch(r"\+?\d{10,15}", phone):
        raise AppError("Телефон может содержать только цифры и знак «+».")
    return phone


def check_login(value):
    """Проверяет логин: не пустой и без пробелов."""
    login = require_text(value, "Логин")
    if " " in login:
        raise AppError("Логин не должен содержать пробелов.")
    return login


def check_password(password, repeat):
    """Проверяет длину пароля и совпадение с повтором."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов.")
    if password != repeat:
        raise AppError("Пароли не совпадают.")
    return password


def parse_positive_int(text, field_name):
    """Переводит текст в целое положительное число."""
    text = text.strip()
    if not text.isdigit() or int(text) <= 0:
        raise AppError(f"Поле «{field_name}» должно быть целым положительным числом.")
    return int(text)


def parse_positive_number(text, field_name):
    """Переводит текст в положительное число (допускается запятая)."""
    text = text.strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        raise AppError(f"Поле «{field_name}» должно быть числом.") from None
    if number <= 0:
        raise AppError(f"Поле «{field_name}» должно быть больше нуля.")
    return number


def rubles_to_kopecks(text, field_name):
    """Переводит рубли из текста в копейки (целое число)."""
    return round(parse_positive_number(text, field_name) * 100)


def kopecks_to_text(kopecks):
    """Переводит копейки в текст вида «1894.74»."""
    sign = "-" if kopecks < 0 else ""
    rubles, rest = divmod(abs(kopecks), 100)
    return f"{sign}{rubles}.{rest:02d}"


def parse_date(text, field_name):
    """Переводит дату ДД.ММ.ГГГГ в формат базы ГГГГ-ММ-ДД."""
    try:
        date = datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        raise AppError(f"Поле «{field_name}»: дата должна быть в формате ДД.ММ.ГГГГ.") from None
    return date.strftime("%Y-%m-%d")
