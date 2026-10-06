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
    except (OSError, ValueError, AttributeError):
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
        "Ты оформляешь адрес многоквартирного дома. Исправь опечатки и запиши адрес полностью, "
        "от большего к меньшему, через запятую: страна (только если это не Россия), область или "
        "регион (если он есть в этой стране), город, тип улицы и название, дом с номером "
        "(корпус и букву сохрани как есть).\n"
        "Страну, регион и город определяй по тому, что написал пользователь. Если он указал "
        "город или страну (например, Алматы, Москва, Минск), используй именно их и никогда не "
        "заменяй на другие. "
        f"Только если в вводе нет никакого города, считай, что дом находится в городе {city}, "
        f"{region}. Тип улицы (улица, проспект, переулок, площадь, шоссе и т. п.) определи "
        "сам; если не уверен, пиши «улица». Ничего не выдумывай. "
        "Если ввод совсем не похож на адрес, ответь одним словом: НЕТ. "
        "Ответ - одна строка: только адрес, без пояснений.\n\n"
        f"Ввод: Одоевского 1\nОтвет: {region}, город {city}, улица Одоевского, дом 1\n"
        "Ввод: Алматы Рыскулова 1\nОтвет: Казахстан, город Алматы, улица Рыскулова, дом 1\n"
        "Ввод: москва тверская 7\nОтвет: город Москва, улица Тверская, дом 7\n\n"
        f"Ввод: {raw}\nОтвет:"
    )


def is_valid(text):
    """True, если ответ похож на адрес: одна строка, без пояснений, есть номер дома."""
    return (
        isinstance(text, str)
        and 5 <= len(text) <= MAX_LENGTH
        and "\n" not in text
        and "—" not in text
        and re.search(r"(дом|д\.)\s*\d", text, re.I) is not None
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
