"""Данные ТСЖ: название, адрес, тариф."""

from db import database as db
from services import address as address_service
from services import validation as check
from services.errors import AppError


def get_hoa():
    """Возвращает данные ТСЖ словарём или None, если они не заполнены."""
    row = db.query_one("SELECT * FROM hoa LIMIT 1")
    return dict(row) if row else None


def get_tariff():
    """Возвращает тариф за 1 м2 в копейках."""
    hoa = get_hoa()
    if hoa is None:
        raise AppError("Данные ТСЖ не заполнены.")
    return hoa["rate_per_m2"]


def prepare_address(raw):
    """Готовит адрес к сохранению. Возвращает (адрес, в_очереди).

    Не изменился - остаётся как есть. Изменился - его оформляет DeepSeek; без связи адрес
    сохраняется как введён, а запрос встаёт в очередь (файл address_queue.json).
    """
    raw = check.require_text(raw, "Адрес дома")
    current = get_hoa()
    if current is not None and raw == current["address"]:
        return raw, has_pending_address()
    return address_service.resolve(raw)


def has_pending_address():
    """True, если адрес ТСЖ в базе ещё ждёт оформления нейросетью."""
    queued = address_service.queue_get()
    current = get_hoa()
    return bool(queued) and current is not None and current["address"] == queued


def resolve_pending_address():
    """Оформляет адрес из очереди. Возвращает True, если адрес заменён на полный."""
    if not has_pending_address():
        address_service.queue_clear()  # очередь устарела (адрес уже изменили) - убираем
        return False
    queued = address_service.queue_get()
    try:
        full = address_service.normalize(queued)
    except (OSError, ValueError, KeyError, IndexError):  # связи всё ещё нет - ждём дальше
        return False
    # условие по старому тексту: адрес, который председатель успел изменить, не затираем
    db.execute("UPDATE hoa SET address = ? WHERE address = ?", (full, queued))
    address_service.queue_clear()
    return True


def update_hoa(data):
    """Изменяет данные ТСЖ. data - словарь: hoa_name, inn, address, rate (рубли)."""
    name = check.require_text(data["hoa_name"], "Наименование ТСЖ")
    inn = check.check_inn(data["inn"])
    rate = check.rubles_to_kopecks(data["rate"], "Тариф за 1 м2")
    if get_hoa() is None:
        raise AppError("Данные ТСЖ не заполнены.")
    address, _ = prepare_address(data["address"])
    db.execute(
        "UPDATE hoa SET name = ?, inn = ?, address = ?, rate_per_m2 = ?", (name, inn, address, rate)
    )


def delete_hoa():
    """Удаляет данные ТСЖ, если в реестре нет квартир."""
    if db.query_one("SELECT 1 FROM apartments") is not None:
        raise AppError("Нельзя удалить данные ТСЖ: в реестре есть квартиры.")
    db.execute("DELETE FROM hoa")
