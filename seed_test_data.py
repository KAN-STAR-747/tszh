"""Заполняет базу тестовыми данными для демонстрации.

Запуск: python seed_test_data.py
ВНИМАНИЕ: старая база tszh.db будет удалена.
"""

import os
from unittest import mock

from db import database
from services import address, apartments, auth, finance, requests_service
from services import validation

APARTMENTS = [
    ("1", "45", "Иванов Иван Иванович", "+79130000001", True),
    ("2", "38,5", "Петров Игорь Михайлович", "+79130000002", False),
    ("3", "52", "Кузнецов Илья Леонидович", "+79130000003", True),
    ("4", "61,2", "Сафонов Павел Дмитриевич", "+79130000004", True),
    ("5", "43", "Павлов Олег Сергеевич", "+79130000005", False),
    ("6", "55", "Романов Леонид Дмитриевич", "+79130000006", True),
    ("7", "37,7", "Низов Пётр Олегович", "+79130000007", False),
    ("8", "48", "Орлов Сергей Олегович", "+79130000008", False),
]


def fill():
    """Удаляет старую базу и создаёт новую с тестовыми данными."""
    if os.path.exists(database.DB_PATH):
        os.remove(database.DB_PATH)
    database.init_db()

    with mock.patch.object(address, "normalize", side_effect=lambda raw: raw):
        auth.register_chairman(
            {
                "full_name": "Иванов Иван Иванович",
                "phone": "+7 777 777 77 77",
                "login": "ivanov@example.com",
                "password": "ivanov123",
                "password2": "ivanov123",
                "hoa_name": 'ТСЖ "Березка"',
                "inn": "1234567890",
                "address": "Новосибирская область, город Новосибирск, улица Примерная, дом 10",
                "rate": "32,50",
            }
        )
    for number, area, owner, phone, is_member in APARTMENTS:
        apartments.save_apartment(
            {
                "number": number,
                "area": area,
                "owner_name": owner,
                "owner_phone": phone,
                "is_member": is_member,
            }
        )

    for month in ("2026-06", "2026-07", "2026-08"):
        finance.charge_month(month)
    finance.charge_target("Ремонт подъезда", "1500", "2026-08")
    rows = apartments.get_apartments()
    tariff = 3250
    for row in rows[:6]:
        if row["number"] == 2:
            continue
        amount = validation.kopecks_to_text(finance.calc_charge(row["area"], tariff))
        for date in ("10.06.2026", "12.07.2026", "15.08.2026"):
            finance.add_payment(row["apartment_id"], amount, date, "Перевод")
    for row in rows:
        if row["number"] in (1, 3, 4, 5):
            finance.add_payment(row["apartment_id"], "1500", "20.08.2026", "Ремонт подъезда")

    auth.register_resident(
        {
            "full_name": "Смирнов Олег Романович",
            "phone": "+79131112233",
            "apartment_number": "2",
            "login": "smirnov@example.com",
            "password": "smirnov123",
            "password2": "smirnov123",
        }
    )
    auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
    auth.register_resident(
        {
            "full_name": "Петров Пётр Петрович",
            "phone": "+79134445566",
            "apartment_number": "8",
            "login": "petrov@example.com",
            "password": "petrov123",
            "password2": "petrov123",
        }
    )

    chairman = auth.login_user("ivanov@example.com", "ivanov123")["users_id"]
    requests_service.create_request(
        chairman,
        None,
        "Не работает лифт",
        "Лифт во 2-м подъезде остановился между 3 и 4 этажом.",
        "Звонок",
        "ООО «ЛифтСервис»",
    )
    requests_service.create_request(
        chairman,
        rows[0]["apartment_id"],
        "Течёт кран на кухне",
        "Под мойкой капает вода.",
        "Приложение",
    )
    requests_service.create_request(
        chairman, rows[2]["apartment_id"], "Перегорела лампочка", "В подъезде на 3 этаже.", "Звонок"
    )
    print("Тестовая база создана:", database.DB_PATH)
    print("Председатель: ivanov@example.com / ivanov123")
    print("Жилец: smirnov@example.com / smirnov123 (кв. 2)")
    print("Ожидает подтверждения: petrov@example.com / petrov123")


if __name__ == "__main__":
    fill()
