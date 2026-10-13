"""Тесты безопасности: SQL-инъекции, хранение паролей, права жильца."""

import unittest

from db import database
from services import apartments, auth, finance, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data

PAYLOADS = [
    "'; DROP TABLE apartments; --",
    "' OR '1'='1",
    "x'); DELETE FROM users; --",
    '" OR ""="',
]
TABLES = ["hoa", "users", "apartments", "requests", "charges", "payment"]


class SqlInjectionTest(BaseTest):
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        self.user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        apartments.save_apartment(apartment_data("1"))

    def table_counts(self):
        return {t: len(database.query_all(f"SELECT * FROM {t}")) for t in TABLES}

    def test_login_with_injection_is_rejected(self):
        for payload in PAYLOADS:
            with self.assertRaises(AppError):
                auth.login_user(payload, payload)
            with self.assertRaises(AppError):
                auth.login_user("ivanov@example.com", payload)
        self.assertEqual(self.table_counts()["users"], 1)

    def test_search_with_injection_changes_nothing(self):
        before = self.table_counts()
        for payload in PAYLOADS:
            self.assertEqual(apartments.get_apartments(search=payload), [])
        self.assertEqual(self.table_counts(), before)

    def test_text_fields_are_stored_as_plain_text(self):
        apartment_id = apartments.get_apartments()[0]["apartment_id"]
        for payload in PAYLOADS:
            request_id = requests_service.create_request(
                self.user_id, apartment_id, payload[:50], payload, "Звонок", payload[:25]
            )
            saved = requests_service.get_request(request_id)
            self.assertEqual(saved["title"], payload.strip()[:50])
            self.assertEqual(saved["description"], payload.strip())
            finance.add_payment(apartment_id, "100", "01.09.2026", payload)
        self.assertEqual(self.table_counts()["requests"], len(PAYLOADS))
        self.assertEqual(self.table_counts()["apartments"], 1)
        self.assertEqual(self.table_counts()["users"], 1)

    def test_name_and_phone_fields_reject_sql_symbols(self):
        for payload in PAYLOADS:
            data = apartment_data("2")
            data["owner_name"] = payload
            with self.assertRaises(AppError):
                apartments.save_apartment(data)
            data = apartment_data("2")
            data["owner_phone"] = payload
            with self.assertRaises(AppError):
                apartments.save_apartment(data)
        self.assertEqual(self.table_counts()["apartments"], 1)


class PasswordAndAccessTest(BaseTest):
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())

    def test_password_is_stored_only_as_salted_hash(self):
        row = database.query_one("SELECT password_hash FROM users")
        self.assertNotIn("secret12", row["password_hash"])
        self.assertNotEqual(auth.make_hash("secret12"), auth.make_hash("secret12"))
        self.assertTrue(auth.password_matches("secret12", row["password_hash"]))
        self.assertFalse(auth.password_matches("Secret12", row["password_hash"]))

    def test_resident_cannot_delete_foreign_or_taken_request(self):
        apartments.save_apartment(apartment_data("1"))
        auth.register_resident(
            {
                "full_name": "Петров Пётр Петрович",
                "phone": "+79990001122",
                "apartment_number": "1",
                "login": "resident@example.com",
                "password": "resident1",
                "password2": "resident1",
            }
        )
        resident = auth.login_user("resident@example.com", "resident1")
        chairman = auth.login_user("ivanov@example.com", "secret12")
        foreign = requests_service.create_request(chairman["users_id"], None, "Лифт", "", "Звонок")
        own = requests_service.create_request(
            resident["users_id"], resident["apartment_id"], "Кран", "", "Приложение"
        )
        with self.assertRaises(AppError):
            requests_service.delete_own_request(resident["users_id"], foreign)
        requests_service.move_to_next_status(own)
        with self.assertRaises(AppError):
            requests_service.delete_own_request(resident["users_id"], own)
        self.assertIsNotNone(requests_service.get_request(foreign))
        self.assertIsNotNone(requests_service.get_request(own))

    def test_unapproved_resident_cannot_log_in(self):
        apartments.save_apartment(apartment_data("1"))
        auth.register_resident(
            {
                "full_name": "Смирнов Олег Романович",
                "phone": "+79131112233",
                "apartment_number": "1",
                "login": "new@example.com",
                "password": "resident1",
                "password2": "resident1",
            }
        )
        with self.assertRaises(AppError):
            auth.login_user("new@example.com", "resident1")


if __name__ == "__main__":
    unittest.main()
