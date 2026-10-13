"""Настройки почты и ключ DeepSeek (секреты).

Значения берутся из переменных окружения или из файла .env, который лежит рядом с программой
(рядом с exe). В файле по одной строке КЛЮЧ=значение. Файл с секретами в git не попадает
(см. .gitignore), образец без секретов - .env.example.
"""

import os

from db.database import get_app_folder

ENV_NAME = ".env"

DEFAULTS = {
    "deepseek_api_key": "",
    "apps_script_url": "",
    "apps_script_token": "",
    "default_region": "Новосибирская область",
    "default_city": "Новосибирск",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 465,
    "smtp_user": "",
    "smtp_password": "",
    "sender_name": "Система управления ТСЖ",
}


def read_env_file():
    """Читает файл .env рядом с программой: словарь {КЛЮЧ: значение} (нет файла - пустой)."""
    values = {}
    try:
        with open(os.path.join(get_app_folder(), ENV_NAME), encoding="utf-8-sig") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key.strip().removeprefix("export ").strip().upper()] = value
    except OSError:
        pass
    return values


def get_settings():
    """Возвращает словарь настроек: .env перекрывает умолчания, переменные окружения - .env."""
    values = dict(DEFAULTS)
    from_file = read_env_file()
    for key in DEFAULTS:
        name = key.upper()
        value = os.environ.get(name) or from_file.get(name)
        if value:
            values[key] = value
    return values
