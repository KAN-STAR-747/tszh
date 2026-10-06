"""Создание нового пароля для восстановления аккаунта.

Пароль придумывает нейросеть DeepSeek (через API). Если сервис недоступен или вернул
неподходящий ответ, пароль создаётся на компьютере случайным образом, чтобы восстановление
всё равно работало.
"""

import re
import secrets
import string

from services import deepseek, settings

PASSWORD_LENGTH = 8
PROMPT = (
    f"Придумай случайный пароль ровно из {PASSWORD_LENGTH} символов: только латинские буквы "
    "(большие и маленькие) и цифры, хотя бы одна буква и хотя бы одна цифра. "
    "В ответе напиши только сам пароль, без кавычек и пояснений."
)


def is_valid(password):
    """True, если пароль ровно из 8 латинских букв и цифр, среди них есть и буква, и цифра."""
    return (
        isinstance(password, str)
        and re.fullmatch(f"[A-Za-z0-9]{{{PASSWORD_LENGTH}}}", password) is not None
        and re.search(r"[A-Za-z]", password) is not None
        and re.search(r"[0-9]", password) is not None
    )


def random_password():
    """Запасной вариант: случайный пароль без нейросети (модуль secrets - для паролей)."""
    letters_and_digits = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(letters_and_digits) for _ in range(PASSWORD_LENGTH))
        if is_valid(password):
            return password


def ask_deepseek(api_key):
    """Просит DeepSeek придумать пароль. Возвращает строку ответа без лишних символов."""
    return deepseek.ask(api_key, PROMPT, temperature=1.5, max_tokens=30)


def generate_password():
    """Возвращает новый 8-значный пароль: от DeepSeek или (если не вышло) случайный."""
    api_key = settings.get_settings()["deepseek_api_key"]
    if api_key:
        try:
            password = ask_deepseek(api_key)
        except (OSError, ValueError, KeyError, IndexError):
            password = None
        if is_valid(password):
            return password
    return random_password()
