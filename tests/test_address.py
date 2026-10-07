"""Тесты оформления адреса дома: DeepSeek, очередь без интернета и автоподстановка."""

import os
import unittest
from unittest import mock

from services import address, auth, hoa
from tests.helpers import BaseTest, chairman_data

FULL = "Новосибирская область, город Новосибирск, улица Одоевского, дом 1"


def with_address(text):
    """Данные председателя с заданным адресом."""
    return {**chairman_data(), "address": text}


class AddressServiceTests(unittest.TestCase):
    """Сама нейросеть подменена: проверяем запрос, проверку ответа и очередь."""

    def settings(self, key="sk-test"):
        return mock.patch.object(
            address.settings,
            "get_settings",
            return_value={
                "deepseek_api_key": key,
                "default_region": "Новосибирская область",
                "default_city": "Новосибирск",
            },
        )

    def test_answer_validation(self):
        self.assertTrue(address.is_valid(FULL))
        self.assertTrue(address.is_valid("Казахстан, город Алматы, улица Рыскулова, дом 1"))
        for wrong in (
            "",
            "дом",
            "НЕТ",
            "Не могу определить адрес 1",
            "строка\nвторая, дом 1",
            "а" * 300 + ", дом 1",
            "Алматы — это не Россия, поэтому: город Новосибирск, дом 1",
        ):
            self.assertFalse(address.is_valid(wrong), wrong)


class AddressQueueTests(BaseTest):
    """Регистрация председателя: адрес оформляется сразу или ждёт интернета в очереди."""

    def online(self, answer=FULL):
        return mock.patch.object(address, "normalize", side_effect=lambda raw: answer)

    def offline(self):
        return mock.patch.object(address, "normalize", side_effect=OSError("нет интернета"))

    def test_without_internet_address_waits_in_queue(self):
        with self.offline():
            queued = auth.register_chairman(with_address("Одоевского 1"))
        self.assertTrue(queued)
        self.assertEqual(hoa.get_hoa()["address"], "Одоевского 1")
        self.assertTrue(hoa.has_pending_address())
        with self.offline():
            self.assertFalse(hoa.resolve_pending_address())
        self.assertEqual(hoa.get_hoa()["address"], "Одоевского 1")

    def test_full_address_is_substituted_when_internet_appears(self):
        with self.offline():
            auth.register_chairman(with_address("Одоевского 1"))
        with self.online():
            self.assertTrue(hoa.resolve_pending_address())
        self.assertEqual(hoa.get_hoa()["address"], FULL)
        self.assertFalse(hoa.has_pending_address())
        self.assertFalse(os.path.exists(self.queue_file))


if __name__ == "__main__":
    unittest.main()
