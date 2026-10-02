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


if __name__ == "__main__":
    unittest.main()
