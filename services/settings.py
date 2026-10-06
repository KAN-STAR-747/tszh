"""Настройки почты и ключ DeepSeek.

Значения берутся из переменных окружения или из файла mail_config.json, который лежит
рядом с программой (рядом с exe). Файл с секретами в git не попадает (см. .gitignore),
образец без секретов - mail_config.example.json.
"""

import json
import os

from db.database import get_app_folder

CONFIG_NAME = "mail_config.json"

# ключ -> значение по умолчанию; переменная окружения называется так же большими буквами
DEFAULTS = {
    "deepseek_api_key": "",
    "apps_script_url": "",  # если задан, письма идут через скрипт Google (HTTPS) - основной способ
    "apps_script_token": "",
    "brevo_api_key": "",  # если задан, письма идут через Brevo по HTTPS, а не через SMTP
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "smtp_user": "",
    "smtp_password": "",
    "sender_name": "Система управления ТСЖ",
}


def get_settings():
    """Возвращает словарь настроек: файл перекрывает умолчания, окружение перекрывает файл."""
    values = dict(DEFAULTS)
    try:
        with open(os.path.join(get_app_folder(), CONFIG_NAME), encoding="utf-8") as file:
            values.update(json.load(file))
    except (OSError, ValueError):  # файла нет или он испорчен - работаем с умолчаниями
        pass
    for key in DEFAULTS:
        from_env = os.environ.get(key.upper())
        if from_env:
            values[key] = from_env
    return values
