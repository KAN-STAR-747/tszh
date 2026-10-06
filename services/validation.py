"""Проверка данных, которые вводит пользователь."""

import re
from datetime import datetime

from services.errors import AppError

MIN_PASSWORD_LENGTH = 8

MAX_TITLE = 50
MAX_DESCRIPTION = 250
MAX_EXECUTOR = 25
MAX_PURPOSE = 50
MAX_COMMENT = 50


def require_text(value, field_name):
    """Проверяет, что поле не пустое, и возвращает текст без пробелов по краям."""
    value = value.strip()
    if not value:
        raise AppError(f"Поле «{field_name}» не может быть пустым.")
    return value


# одно слово ФИО: буквы (кириллица или латиница), части через дефис («Салтыков-Щедрин»)
NAME_WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{2,}(-[A-Za-zА-Яа-яЁё]{2,})*")
FULL_NAME_HINT = (
    "Укажите ФИО полностью: фамилию, имя и отчество (если оно есть), "
    "например: Талаев Владислав Анатольевич или Талаев Владислав."
)


def check_full_name(value):
    """Проверяет ФИО (фамилия, имя, отчество по желанию; без инициалов), исправляет регистр."""
    words = value.split()
    if not 2 <= len(words) <= 3 or not all(NAME_WORD.fullmatch(word) for word in words):
        raise AppError(FULL_NAME_HINT)
    # каждое слово (и каждая часть через дефис) с большой буквы, остальное строчными
    return " ".join("-".join(part.capitalize() for part in word.split("-")) for word in words)


# кавычки и скобки, которые пользователь мог напечатать вокруг названия ТСЖ
HOA_MARKS = re.compile(r"[\"'`«»“”„‟()\[\]{}<>]")
MAX_HOA_NAME_LENGTH = 50


def check_hoa_name(value):
    """Приводит название к виду ТСЖ "Название".

    Лишние кавычки, скобки и повторное «ТСЖ» убираются: из ТСЖ"ТСЖ(Березка)", тсж березка и
    просто Березка получится ТСЖ "Березка".
    """
    text = require_text(value, "Наименование ТСЖ")
    core = HOA_MARKS.sub(" ", text)
    core = re.sub(r"\bтсж\b", " ", core, flags=re.I)  # слово ТСЖ (в том числе повторное)
    core = re.sub(r"^ТСЖ(?=[А-ЯЁA-Z])", "", core.strip())  # слитно: ТСЖБерезка
    core = " ".join(core.split()).strip(" .,;:_-–—")
    if not core:
        raise AppError("Укажите название ТСЖ, например: Березка.")
    if len(core) > MAX_HOA_NAME_LENGTH:
        raise AppError(f"Название ТСЖ не длиннее {MAX_HOA_NAME_LENGTH} символов.")
    return f'ТСЖ "{core[0].upper()}{core[1:]}"'


def check_inn(value):
    """Проверяет ИНН: ровно 10 цифр."""
    value = value.strip()
    if not (value.isdigit() and len(value) == 10):
        raise AppError("ИНН должен состоять ровно из 10 цифр.")
    return value


def check_length(value, max_length, field_name):
    """Проверяет, что текст не длиннее допустимого, и возвращает его без пробелов по краям."""
    value = value.strip()
    if len(value) > max_length:
        raise AppError(f"Поле «{field_name}» не должно быть длиннее {max_length} символов.")
    return value


def check_phone(value):
    """Проверяет телефон: необязательный «+» и от 10 до 11 цифр."""
    phone = value.replace(" ", "")
    if not re.fullmatch(r"\+?\d{10,11}", phone):
        raise AppError(
            "Телефон может начинаться с «+», дальше только цифры (не больше 11), "
            "например +79991234567 или 89991234567."
        )
    return phone


def normalize_phone(value):
    """Приводит телефон к виду для сравнения: только цифры, начало «8» заменено на «7»."""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    return digits


def same_surname(full_name_a, full_name_b):
    """True, если фамилии (первое слово ФИО) совпадают без учёта регистра."""
    first_a = full_name_a.split()[0].lower() if full_name_a.split() else ""
    first_b = full_name_b.split()[0].lower() if full_name_b.split() else ""
    return first_a != "" and first_a == first_b


MAX_EMAIL_LENGTH = 254  # предел длины адреса электронной почты

# адрес вида имя@домен.зона: латиница, цифры и знаки . _ % + - в имени
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def check_login(value):
    """Проверяет логин: это адрес электронной почты. Возвращает его в нижнем регистре."""
    login = require_text(value, "Электронная почта")
    if len(login) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.fullmatch(login):
        raise AppError("Логином должен быть адрес электронной почты, например name@mail.ru.")
    return login.lower()  # почта не зависит от регистра: хранится строчными буквами


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
