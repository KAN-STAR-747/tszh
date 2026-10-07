"""Тесты реестра квартир (день 7)."""

import unittest

from services import apartments
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data


class ApartmentsTest(BaseTest):
    def test_duplicate_number_is_rejected(self):
        apartments.save_apartment(apartment_data("5"))
        with self.assertRaises(AppError):
            apartments.save_apartment(apartment_data("5"))
        self.assertEqual(len(apartments.get_apartments()), 1)

    def test_search_by_name_ignores_case(self):
        apartments.save_apartment(apartment_data("1"))
        self.assertEqual(len(apartments.get_apartments(search="петров")), 1)
        self.assertEqual(len(apartments.get_apartments(search="сидоров")), 0)

    def test_search_by_phone_accepts_8_and_plus7(self):
        apartments.save_apartment(apartment_data("1"))
        for query in ("8999", "+7999", "89990001122", "8 (999) 000-11-22"):
            self.assertEqual(len(apartments.get_apartments(search=query)), 1, query)
        self.assertEqual(len(apartments.get_apartments(search="8123")), 0)

    def test_search_does_not_match_apartment_number(self):
        apartments.save_apartment(apartment_data("77"))
        self.assertEqual(len(apartments.get_apartments(search="77")), 0)

    def test_number_and_area_limits(self):
        with self.assertRaises(AppError):
            apartments.save_apartment(apartment_data("10000"))
        with self.assertRaises(AppError):
            apartments.save_apartment(apartment_data("5", "5000"))


if __name__ == "__main__":
    unittest.main()
