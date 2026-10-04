"""Тесты правок после макета: собственник, длина полей, изменение заявок, новые окна."""

import unittest

from services import apartments, auth, finance, hoa, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


def resident_data(login="smirnov", name="Смирнов О.Р.", phone="+79991112233", number="1"):
    """Данные для регистрации жильца (по умолчанию - не собственник квартиры 1)."""
    return {
        "full_name": name,
        "phone": phone,
        "apartment_number": number,
        "login": login,
        "password": "pass1234",
        "password2": "pass1234",
    }


class OwnerTest(BaseTest):
    """Кто такой собственник и когда вход разрешается без подтверждения."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))

    def test_owner_is_approved_at_once(self):
        data = resident_data("petrov", "Петров Пётр Петрович", "+79990001122")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov", "pass1234")
        self.assertTrue(auth.is_owner(user))

    def test_phone_8_and_plus7_are_same(self):
        data = resident_data("petrov", "Петров П.П.", "8 999 000 11 22")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov", "pass1234")
        self.assertEqual(user["phone"], "89990001122")

    def test_plus7_matches_8(self):
        apartments.save_apartment(
            {**apartment_data("2"), "owner_name": "Сидоров С.С.", "owner_phone": "89135554433"}
        )
        data = resident_data("sidorov", "Сидоров Сергей", "+7 913 555 44 33", "2")
        self.assertTrue(auth.register_resident(data))

    def test_other_person_waits_for_chairman(self):
        self.assertFalse(auth.register_resident(resident_data()))
        with self.assertRaises(AppError):
            auth.login_user("smirnov", "pass1234")
        user_id = auth.get_pending_residents()[0]["users_id"]
        auth.approve_resident(user_id)
        user = auth.login_user("smirnov", "pass1234")
        self.assertFalse(auth.is_owner(user))
        owner = apartments.get_apartment(user["apartment_id"])["owner_name"]
        self.assertEqual(owner, "Петров П.П.")

    def test_new_apartment_owner_by_registration(self):
        self.assertFalse(auth.register_resident(resident_data(number="5")))
        apartment = apartments.get_apartment_by_number(5)
        self.assertEqual(apartment["area"], 0)
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        user = auth.login_user("smirnov", "pass1234")
        self.assertTrue(auth.is_owner(user))

    def test_reject_removes_new_apartment(self):
        auth.register_resident(resident_data(number="5"))
        auth.reject_resident(auth.get_pending_residents()[0]["users_id"])
        self.assertIsNone(apartments.get_apartment_by_number(5))

    def test_zero_area_apartment_not_charged(self):
        auth.register_resident(resident_data(number="5"))
        self.assertEqual(finance.charge_month("2026-09"), 1)

    def test_owner_profile_change_keeps_ownership(self):
        data = resident_data("petrov", "Петров Пётр Петрович", "+79990001122")
        auth.register_resident(data)
        user = auth.login_user("petrov", "pass1234")
        auth.update_profile(user["users_id"], "Петров Пётр Петрович", "+79995556677")
        changed = auth.login_user("petrov", "pass1234")
        self.assertTrue(auth.is_owner(changed))

    def test_duplicate_login_does_not_create_apartment(self):
        auth.register_resident(resident_data(number="5"))
        with self.assertRaises(AppError):
            auth.register_resident(resident_data(number="6"))
        self.assertIsNone(apartments.get_apartment_by_number(6))

    def test_residents_list(self):
        auth.register_resident(resident_data("petrov", "Петров Пётр", "+79990001122"))
        auth.register_resident(resident_data("smirnov"))
        residents = auth.get_residents()
        self.assertEqual(len(residents), 1)
        self.assertEqual(residents[0]["number"], 1)

    def test_chairman_contacts(self):
        chairman = auth.get_chairman()
        self.assertEqual(chairman["phone"], "+77777777777")


class ChairmanEditTest(BaseTest):
    """Редактирование данных председателя и ТСЖ (окно 21)."""

    def test_update_chairman(self):
        auth.register_chairman(chairman_data())
        user_id = auth.login_user("ivanov", "secret12")["users_id"]
        data = {
            "full_name": "Иванов И.П.",
            "phone": "8 999 123 45 67",
            "hoa_name": "ТСЖ Новое",
            "inn": "0987654321",
            "address": "г. Томск, ул. Новая, 1",
            "rate": "40",
        }
        auth.update_chairman(user_id, data)
        self.assertEqual(auth.get_user(user_id)["phone"], "89991234567")
        self.assertEqual(hoa.get_hoa()["name"], "ТСЖ Новое")
        self.assertEqual(hoa.get_tariff(), 4000)
        data["inn"] = "123"
        with self.assertRaises(AppError):
            auth.update_chairman(user_id, data)


class RequestEditTest(BaseTest):
    """Длина полей, изменение и удаление заявок."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        self.chairman_id = auth.login_user("ivanov", "secret12")["users_id"]
        auth.register_resident(resident_data())
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        self.resident = auth.login_user("smirnov", "pass1234")

    def test_length_limits(self):
        create = requests_service.create_request
        create(self.chairman_id, None, "т" * 50, "о" * 250, "Звонок", "и" * 25)  # ровно по границе
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "т" * 51, "", "Звонок")
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "Тема", "о" * 251, "Звонок")
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "Тема", "", "Звонок", "и" * 26)

    def test_update_request(self):
        request_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        requests_service.update_request(request_id, "Новое описание", "ООО Сервис")
        request = requests_service.get_request(request_id)
        self.assertEqual(request["description"], "Новое описание")
        self.assertEqual(request["executor"], "ООО Сервис")

    def test_completed_request_is_read_only(self):
        request_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        requests_service.move_to_next_status(request_id)
        requests_service.move_to_next_status(request_id)
        with self.assertRaises(AppError):
            requests_service.update_request(request_id, "Другое", "Другой")

    def test_resident_deletes_new_request(self):
        apartment_id = self.resident["apartment_id"]
        request_id = requests_service.create_request(
            self.resident["users_id"], apartment_id, "Кран", "", "Приложение"
        )
        requests_service.delete_own_request(self.resident["users_id"], request_id)
        self.assertIsNone(requests_service.get_request(request_id))

    def test_resident_cannot_delete_foreign_or_taken_request(self):
        request_id = requests_service.create_request(
            self.resident["users_id"], None, "Кран", "", "Приложение"
        )
        requests_service.move_to_next_status(request_id)
        with self.assertRaises(AppError):
            requests_service.delete_own_request(self.resident["users_id"], request_id)
        foreign_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        with self.assertRaises(AppError):
            requests_service.delete_own_request(self.resident["users_id"], foreign_id)


class FinanceEditTest(BaseTest):
    """Длина полей в финансах и данные для окон «Оплаты» и «Все целевые сборы»."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1", "40"))
        apartments.save_apartment(apartment_data("2", "30"))
        self.ids = [row["apartment_id"] for row in apartments.get_apartments()]

    def test_length_limits(self):
        finance.charge_target("н" * 50, "100", "2026-10")
        with self.assertRaises(AppError):
            finance.charge_target("н" * 51, "100", "2026-11")
        finance.add_payment(self.ids[0], "10", "01.10.2026", "к" * 50)
        with self.assertRaises(AppError):
            finance.add_payment(self.ids[0], "10", "01.10.2026", "к" * 51)

    def test_all_payments(self):
        finance.add_payment(self.ids[0], "100", "01.10.2026", "Первая")
        finance.add_payment(self.ids[1], "200", "05.10.2026", "Вторая")
        payments = finance.get_all_payments()
        self.assertEqual([p["comment"] for p in payments], ["Вторая", "Первая"])
        self.assertEqual(payments[0]["number"], 2)

    def test_target_charges_paid_count(self):
        finance.charge_target("На лампочки", "1500", "2026-10")
        finance.add_payment(self.ids[0], "1500", "02.10.2026", "")
        rows = finance.get_target_charges()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["purpose"], rows[0]["amount"]), ("На лампочки", 150000))
        self.assertEqual(rows[0]["paid"], 1)

    def test_maintenance_is_not_target_charge(self):
        finance.charge_month("2026-09")
        self.assertEqual(finance.get_target_charges(), [])


if __name__ == "__main__":
    unittest.main()
