"""Тесты финансов: начисления, оплаты, долги (день 9)."""

import unittest

from db import database
from services import apartments, auth, finance
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


class FinanceTest(BaseTest):
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1", "40"))
        apartments.save_apartment(apartment_data("2", "37,7"))

    def test_monthly_charge_is_area_times_tariff(self):
        self.assertEqual(finance.charge_month("2026-09"), 2)
        rows = apartments.get_apartments()
        self.assertEqual(rows[0]["debt"], 130000)
        self.assertEqual(rows[1]["debt"], 122525)

    def test_repeat_charge_is_rejected(self):
        finance.charge_month("2026-09")
        with self.assertRaises(AppError):
            finance.charge_month("2026-09")
        self.assertEqual(len(database.query_all("SELECT * FROM charges")), 2)

    def test_payment_reduces_debt(self):
        finance.charge_month("2026-09")
        apartment_id = apartments.get_apartments()[0]["apartment_id"]
        finance.add_payment(apartment_id, "1000", "28.09.2026", "Перевод")
        self.assertEqual(apartments.get_apartments()[0]["debt"], 30000)

    def test_target_charge(self):
        count, total = finance.charge_target("Ремонт подъезда", "1500", "2026-10")
        self.assertEqual((count, total), (2, 300000))
        with self.assertRaises(AppError):
            finance.charge_target("Ремонт подъезда", "1500", "2026-10")

    def test_resident_summary(self):
        finance.charge_month("2026-09")
        apartment_id = apartments.get_apartments()[0]["apartment_id"]
        finance.add_payment(apartment_id, "300", "01.09.2026", "")
        summary = finance.get_resident_summary(apartment_id)
        self.assertEqual(summary["debt"], 100000)
        self.assertEqual(len(summary["history"]), 2)


class DeleteApartmentTest(BaseTest):
    """Квартиру с начислениями удалять нельзя (п. 4.1.4 ТЗ)."""

    def test_cannot_delete_apartment_with_charges(self):
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("2"))
        finance.charge_month("2026-09")
        apartment_id = apartments.get_apartments()[0]["apartment_id"]
        with self.assertRaises(AppError):
            apartments.delete_apartment(apartment_id)
        self.assertEqual(len(apartments.get_apartments()), 1)


if __name__ == "__main__":
    unittest.main()
