"""Тесты заявок (день 8)."""

import unittest

from services import auth, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, chairman_data


class RequestsTest(BaseTest):
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        self.user_id = auth.login_user("ivanov", "secret1")["users_id"]

    def test_status_flow_and_closed_date(self):
        request_id = requests_service.create_request(
            self.user_id, None, "Не работает лифт", "", "Звонок"
        )
        request = requests_service.get_request(request_id)
        self.assertEqual(request["status"], "Новая")
        self.assertIsNone(request["closed_at"])

        requests_service.move_to_next_status(request_id)
        requests_service.move_to_next_status(request_id)
        request = requests_service.get_request(request_id)
        self.assertEqual(request["status"], "Выполнена")
        self.assertIsNotNone(request["closed_at"])

        with self.assertRaises(AppError):
            requests_service.move_to_next_status(request_id)

    def test_empty_title_is_rejected(self):
        with self.assertRaises(AppError):
            requests_service.create_request(self.user_id, None, " ", "", "Звонок")


if __name__ == "__main__":
    unittest.main()
