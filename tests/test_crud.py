"""Тесты изменения и удаления записей (день 10)."""

import unittest

from services import apartments, auth, finance, hoa, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


class CrudTest(BaseTest):
    """Проверка изменения и удаления записей (полный набор CRUD)."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1", "40"))
        self.apartment_id = apartments.get_apartments()[0]["apartment_id"]

    def test_update_hoa(self):
        data = chairman_data()
        data.update({"hoa_name": "ТСЖ Новое", "rate": "40"})
        hoa.update_hoa(data)
        self.assertEqual(hoa.get_hoa()["name"], 'ТСЖ "Новое"')
        self.assertEqual(hoa.get_tariff(), 4000)

    def test_delete_hoa_only_without_apartments(self):
        with self.assertRaises(AppError):
            hoa.delete_hoa()
        apartments.delete_apartment(self.apartment_id)
        hoa.delete_hoa()
        self.assertIsNone(hoa.get_hoa())

    def test_update_profile(self):
        user = auth.login_user("ivanov@example.com", "secret12")
        auth.update_profile(user["users_id"], "Иванов Иван Павлович", "+79991234567")
        changed = auth.login_user("ivanov@example.com", "secret12")
        self.assertEqual(changed["full_name"], "Иванов Иван Павлович")
        self.assertEqual(changed["phone"], "+79991234567")

    def test_update_and_delete_charge(self):
        finance.charge_month("2026-09")
        charge = finance.get_charges(self.apartment_id)[0]
        finance.update_charge(charge["charges_id"], "100")
        self.assertEqual(finance.get_charges(self.apartment_id)[0]["amount"], 10000)
        finance.delete_charge(charge["charges_id"])
        self.assertEqual(finance.get_charges(self.apartment_id), [])

    def test_update_and_delete_payment(self):
        finance.add_payment(self.apartment_id, "500", "01.09.2026", "Перевод")
        payment = finance.get_payments(self.apartment_id)[0]
        finance.update_payment(payment["payment_id"], "700", "02.09.2026", "Наличные")
        changed = finance.get_payments(self.apartment_id)[0]
        self.assertEqual((changed["amount"], changed["paid_at"]), (70000, "2026-09-02"))
        finance.delete_payment(payment["payment_id"])
        self.assertEqual(finance.get_payments(self.apartment_id), [])

    def test_delete_request(self):
        user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        request_id = requests_service.create_request(user_id, None, "Тест", "", "Звонок")
        requests_service.delete_request(request_id)
        self.assertIsNone(requests_service.get_request(request_id))


if __name__ == "__main__":
    unittest.main()
