"""Тесты проверки данных и авторизации (день 7)."""

import unittest

from db import database
from services import apartments, auth, validation
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


# Тесты проверки данных: база не нужна, поэтому обычный TestCase
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

    def test_negative_area_is_rejected(self):
        with self.assertRaises(AppError):
            validation.parse_positive_number("-3", "Площадь")


# Тесты входа и регистрации (нужна база, поэтому BaseTest)
class AuthTest(BaseTest):
    # При первом запуске председателя нет, после регистрации он есть
    def test_first_launch_has_no_chairman(self):
        self.assertFalse(auth.chairman_exists())
        auth.register_chairman(chairman_data())
        self.assertTrue(auth.chairman_exists())

    def test_chairman_can_login(self):
        auth.register_chairman(chairman_data())
        user = auth.login_user("ivanov", "secret1")
        self.assertEqual(user["is_participant"], 0)

    def test_wrong_password(self):
        auth.register_chairman(chairman_data())
        with self.assertRaises(AppError):
            auth.login_user("ivanov", "wrong")

    # В базе не должно лежать пароля в открытом виде
    def test_password_is_not_stored_as_plain_text(self):
        auth.register_chairman(chairman_data())
        stored = database.query_one("SELECT password_hash FROM users")
        self.assertNotIn("secret1", stored["password_hash"])

    # Неподтверждённый жилец не может войти, после подтверждения - может
    def test_unapproved_resident_cannot_login(self):
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data())
        auth.register_resident(
            {
                "full_name": "Смирнов О.Р.",
                "phone": "+79991112233",
                "apartment_number": "1",
                "login": "smirnov",
                "password": "pass123",
                "password2": "pass123",
            }
        )
        # ловим ошибку и сохраняем её в error, чтобы проверить текст
        with self.assertRaises(AppError) as error:
            auth.login_user("smirnov", "pass123")
        self.assertIn("ожидает подтверждения", str(error.exception))

        # берём id жильца из списка ожидающих и подтверждаем
        user_id = auth.get_pending_residents()[0]["users_id"]
        auth.approve_resident(user_id)
        self.assertEqual(auth.login_user("smirnov", "pass123")["is_participant"], 1)

    # Жилец вводит номер квартиры сам, но такой квартиры в реестре может не быть
    def test_resident_with_unknown_apartment(self):
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        data = {
            "full_name": "Смирнов О.Р.",
            "phone": "+79991112233",
            "apartment_number": "77",
            "login": "smirnov",
            "password": "pass123",
            "password2": "pass123",
        }
        with self.assertRaises(AppError) as error:
            auth.register_resident(data)
        self.assertIn("не найдена", str(error.exception))
        data["apartment_number"] = " "
        with self.assertRaises(AppError):
            auth.register_resident(data)

    def test_duplicate_login(self):
        auth.register_chairman(chairman_data())
        with self.assertRaises(AppError):
            auth.register_chairman(chairman_data())


if __name__ == "__main__":
    unittest.main()
