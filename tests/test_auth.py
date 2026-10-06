"""Тесты проверки данных и авторизации (день 7)."""

import unittest

from db import database
from services import apartments, auth, validation
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


class ValidationTest(unittest.TestCase):
    def test_inn_must_have_ten_digits(self):
        with self.assertRaises(AppError):
            validation.check_inn("123456789")
        self.assertEqual(validation.check_inn("1234567890"), "1234567890")

    def test_phone_spaces_are_removed(self):
        self.assertEqual(validation.check_phone("+7 777 777 77 77"), "+77777777777")
        with self.assertRaises(AppError):
            validation.check_phone("abc")

    def test_money_conversion(self):
        self.assertEqual(validation.rubles_to_kopecks("1894,34", "Сумма"), 189434)
        self.assertEqual(validation.kopecks_to_text(189434), "1894.34")
        self.assertEqual(validation.kopecks_to_text(-5), "-0.05")

    def test_phone_length_and_plus(self):
        self.assertEqual(validation.check_phone("89991234567"), "89991234567")
        self.assertEqual(validation.check_phone("+7 999 123 45 67"), "+79991234567")
        with self.assertRaises(AppError):
            validation.check_phone("+799912345678")

    def test_login_must_be_email(self):
        self.assertEqual(validation.check_login("Ivan.Petrov+77@Mail.ru"), "ivan.petrov+77@mail.ru")
        for wrong in ("ivan_77", "иван@mail.ru", "ivan@mail", "ivan @mail.ru", "@mail.ru"):
            with self.assertRaises(AppError):
                validation.check_login(wrong)

    def test_password_min_length(self):
        with self.assertRaises(AppError):
            validation.check_password("1234567", "1234567")
        self.assertEqual(validation.check_password("12345678", "12345678"), "12345678")

    def test_negative_area_is_rejected(self):
        with self.assertRaises(AppError):
            validation.parse_positive_number("-3", "Площадь")


class AuthTest(BaseTest):
    def test_first_launch_has_no_chairman(self):
        self.assertFalse(auth.chairman_exists())
        auth.register_chairman(chairman_data())
        self.assertTrue(auth.chairman_exists())

    def test_chairman_can_login(self):
        auth.register_chairman(chairman_data())
        user = auth.login_user("ivanov@example.com", "secret12")
        self.assertEqual(user["is_participant"], 0)

    def test_wrong_password(self):
        auth.register_chairman(chairman_data())
        with self.assertRaises(AppError):
            auth.login_user("ivanov@example.com", "wrong")

    def test_password_is_not_stored_as_plain_text(self):
        auth.register_chairman(chairman_data())
        stored = database.query_one("SELECT password_hash FROM users")
        self.assertNotIn("secret12", stored["password_hash"])

    def test_unapproved_resident_cannot_login(self):
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data())
        auth.register_resident(
            {
                "full_name": "Смирнов Олег Романович",
                "phone": "+79991112233",
                "apartment_number": "1",
                "login": "smirnov@example.com",
                "password": "pass1234",
                "password2": "pass1234",
            }
        )
        with self.assertRaises(AppError) as error:
            auth.login_user("smirnov@example.com", "pass1234")
        self.assertIn("ожидает подтверждения", str(error.exception))

        user_id = auth.get_pending_residents()[0]["users_id"]
        auth.approve_resident(user_id)
        self.assertEqual(auth.login_user("smirnov@example.com", "pass1234")["is_participant"], 1)

    def test_resident_with_unknown_apartment(self):
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        data = {
            "full_name": "Смирнов Олег Романович",
            "phone": "+79991112233",
            "apartment_number": "77",
            "login": "smirnov@example.com",
            "password": "pass1234",
            "password2": "pass1234",
        }
        self.assertFalse(auth.register_resident(data))
        apartment = apartments.get_apartment_by_number(77)
        self.assertEqual(apartment["owner_name"], "Смирнов Олег Романович")
        data["apartment_number"] = " "
        data["login"] = "smirnov2@example.com"
        with self.assertRaises(AppError):
            auth.register_resident(data)

    def test_duplicate_login(self):
        auth.register_chairman(chairman_data())
        with self.assertRaises(AppError):
            auth.register_chairman(chairman_data())


if __name__ == "__main__":
    unittest.main()
