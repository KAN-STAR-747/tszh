"""Приведение адреса дома к полному виду через DeepSeek.

Председатель вводит коротко («Одоевского 1», возможны опечатки), нейросеть исправляет их и
возвращает полный адрес: «Новосибирская область, город Новосибирск, улица Одоевского, дом 1».

Если нейросеть недоступна (нет интернета или ключа), адрес сохраняется как введён, а запрос
встаёт в очередь: введённый текст записывается в файл address_queue.json рядом с программой
(в базу данных очередь не входит). Когда связь появится, services/hoa.py оформит адрес и
подставит его в базу автоматически.
"""

import json
import os
import re

from db.database import get_app_folder
from services import deepseek, settings

MAX_LENGTH = 200
QUEUE_NAME = "address_queue.json"


def queue_path():
    """Путь к файлу очереди (рядом с программой и базой)."""
    return os.path.join(get_app_folder(), QUEUE_NAME)


def queue_get():
    """Возвращает адрес, ожидающий оформления, или пустую строку, если очередь пуста."""
    try:
        with open(queue_path(), encoding="utf-8") as file:
            return str(json.load(file).get("address", ""))
    except (OSError, ValueError, AttributeError):  # файла нет или он испорчен - очереди нет
        return ""


def queue_set(raw):
    """Ставит адрес в очередь на оформление (старая запись заменяется)."""
    with open(queue_path(), "w", encoding="utf-8") as file:
        json.dump({"address": raw}, file, ensure_ascii=False)


def queue_clear():
    """Очищает очередь."""
    try:
        os.remove(queue_path())
    except OSError:
        pass


def make_prompt(raw, region, city):
    """Текст запроса к нейросети."""
    return (
        "Ты помогаешь оформить адрес многоквартирного дома в России. Исправь опечатки и "
        "приведи адрес к полному виду строго в формате: "
        "«<регион>, город <город>, <тип улицы> <название>, дом <номер>». "
        f"Если регион или город не указаны, считай, что дом находится в городе {city}, "
        f"{region}. Тип улицы (улица, проспект, переулок, площадь, шоссе и т. п.) определи "
        "сам; если не уверен, пиши «улица». Номер дома с корпусом или буквой сохрани как есть. "
        "Ничего не выдумывай. Ответь одной строкой: только адрес, без пояснений.\n\n"
        "Пример. Ввод: Одоевского 1\n"
        f"Ответ: {region}, город {city}, улица Одоевского, дом 1\n\n"
        f"Ввод: {raw}\nОтвет:"
    )


def is_valid(text):
    """True, если ответ похож на адрес: одна строка, не слишком длинная, есть номер дома."""
    return (
        isinstance(text, str)
        and 5 <= len(text) <= MAX_LENGTH
        and "\n" not in text
        and re.search(r"\d", text) is not None
    )


def ask_deepseek(api_key, raw, region, city):
    """Просит DeepSeek оформить адрес (температура 0 - ответ без случайности)."""
    return deepseek.ask(api_key, make_prompt(raw, region, city), temperature=0, max_tokens=120)


def normalize(raw):
    """Возвращает полный адрес от DeepSeek.

    Raises:
        OSError: нет связи с сервисом (запрос идёт в очередь).
        ValueError: ключ DeepSeek не задан или ответ не похож на адрес (тоже в очередь).
    """
    config = settings.get_settings()
    if not config["deepseek_api_key"]:
        raise ValueError("не задан ключ DeepSeek")
    answer = ask_deepseek(
        config["deepseek_api_key"], raw, config["default_region"], config["default_city"]
    )
    if not is_valid(answer):
        raise ValueError("ответ не похож на адрес")
    return answer


def resolve(raw):
    """Пробует оформить адрес сейчас. Возвращает (адрес, в_очереди).

    Не вышло - адрес остаётся таким, как введён, а запрос встаёт в очередь.
    """
    raw = raw.strip()
    try:
        full = normalize(raw)
    except (OSError, ValueError, KeyError, IndexError):
        queue_set(raw)
        return raw, True
    queue_clear()
    return full, False
