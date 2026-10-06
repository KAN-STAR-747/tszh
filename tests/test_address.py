"""Тесты оформления адреса дома: DeepSeek, очередь без интернета и автоподстановка."""

import os
import unittest
from unittest import mock

from db import database
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

    def test_prompt_has_input_and_defaults(self):
        prompt = address.make_prompt("Одоевского 1", "Новосибирская область", "Новосибирск")
        self.assertTrue(prompt.endswith("Ввод: Одоевского 1\nОтвет:"))
        self.assertIn("город Новосибирск", prompt)
        self.assertIn("Новосибирская область", prompt)
        self.assertIn("Алматы", prompt)  # пример с другой страной: умолчания не навязываются

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

    def test_normalize_returns_answer(self):
        with self.settings(), mock.patch.object(address, "ask_deepseek", return_value=FULL) as ask:
            self.assertEqual(address.normalize("Одоевского 1"), FULL)
        ask.assert_called_once_with(
            "sk-test", "Одоевского 1", "Новосибирская область", "Новосибирск"
        )

    def test_normalize_refuses_bad_answer_and_missing_key(self):
        with self.settings(), mock.patch.object(address, "ask_deepseek", return_value="не знаю"):
            with self.assertRaises(ValueError):
                address.normalize("Одоевского 1")
        with self.settings(""), mock.patch.object(address, "ask_deepseek") as ask:
            with self.assertRaises(ValueError):
                address.normalize("Одоевского 1")
        ask.assert_not_called()


class AddressQueueTests(BaseTest):
    """Регистрация председателя: адрес оформляется сразу или ждёт интернета в очереди."""

    # BaseTest подменяет normalize тождественной функцией; здесь нужна настоящая подмена
    def online(self, answer=FULL):
        return mock.patch.object(address, "normalize", side_effect=lambda raw: answer)

    def offline(self):
        return mock.patch.object(address, "normalize", side_effect=OSError("нет интернета"))

    def test_short_address_becomes_full(self):
        with self.online():
            queued = auth.register_chairman(with_address("Одоевского 1"))
        self.assertFalse(queued)
        self.assertEqual(hoa.get_hoa()["address"], FULL)
        self.assertFalse(hoa.has_pending_address())
        self.assertFalse(os.path.exists(self.queue_file))

    def test_without_internet_address_waits_in_queue(self):
        with self.offline():
            queued = auth.register_chairman(with_address("Одоевского 1"))
        self.assertTrue(queued)
        # пока интернета нет, в базе лежит введённый текст, очередь запомнила его
        self.assertEqual(hoa.get_hoa()["address"], "Одоевского 1")
        self.assertTrue(hoa.has_pending_address())
        with self.offline():
            self.assertFalse(hoa.resolve_pending_address())  # связи всё ещё нет
        self.assertEqual(hoa.get_hoa()["address"], "Одоевского 1")

    def test_full_address_is_substituted_when_internet_appears(self):
        with self.offline():
            auth.register_chairman(with_address("Одоевского 1"))
        with self.online():
            self.assertTrue(hoa.resolve_pending_address())
        self.assertEqual(hoa.get_hoa()["address"], FULL)
        self.assertFalse(hoa.has_pending_address())
        self.assertFalse(os.path.exists(self.queue_file))

    def test_queue_survives_restart(self):
        with self.offline():
            auth.register_chairman(with_address("Одоевского 1"))
        # «перезапуск»: очередь хранится в файле, поэтому адрес по-прежнему ждёт
        self.assertTrue(os.path.exists(self.queue_file))
        self.assertEqual(address.queue_get(), "Одоевского 1")

    def test_changed_address_is_not_overwritten_by_old_queue(self):
        with self.offline():
            auth.register_chairman(with_address("Одоевского 1"))
        # председатель успел сам изменить адрес: старый запрос ничего не затирает
        with self.online("Другой адрес, дом 5"):
            hoa.update_hoa(
                {
                    "hoa_name": "ТСЖ Березка",
                    "inn": "1234567890",
                    "address": "Ленина 5",
                    "rate": "32,50",
                }
            )
            self.assertFalse(hoa.resolve_pending_address())
        self.assertEqual(hoa.get_hoa()["address"], "Другой адрес, дом 5")

    def test_unchanged_address_does_not_call_deepseek(self):
        with self.online():
            auth.register_chairman(with_address("Одоевского 1"))
        with mock.patch.object(address, "normalize") as normalize:
            hoa.update_hoa(
                {"hoa_name": "ТСЖ Новое", "inn": "1234567890", "address": FULL, "rate": "40"}
            )
        normalize.assert_not_called()
        self.assertEqual(hoa.get_hoa()["name"], 'ТСЖ "Новое"')

    def test_database_schema_is_unchanged(self):
        columns = [row["name"] for row in database.query_all("PRAGMA table_info(hoa)")]
        self.assertEqual(columns, ["hoa_id", "name", "inn", "address", "rate_per_m2"])


if __name__ == "__main__":
    unittest.main()
