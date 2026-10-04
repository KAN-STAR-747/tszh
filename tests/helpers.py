"""Общие помощники для тестов: чистая временная база и тестовые данные."""

import os
import tempfile

import unittest

from db import database


def chairman_data():
    """Данные для регистрации председателя."""
    return {
        "full_name": "Иванов Иван Иванович",
        "phone": "+7 777 777 77 77",
        "login": "ivanov",
        "password": "secret12",
        "password2": "secret12",
        "hoa_name": "ТСЖ Березка",
        "inn": "1234567890",
        "address": "г. Новосибирск, ул. Примерная, 10",
        "rate": "32,50",
    }


def apartment_data(number="1", area="40"):
    """Данные для добавления квартиры."""
    return {
        "number": number,
        "area": area,
        "owner_name": "Петров П.П.",
        "owner_phone": "+79990001122",
        "is_member": True,
    }


class BaseTest(unittest.TestCase):
    """Перед каждым тестом создаёт чистую временную базу."""

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        database.DB_PATH = self.path
        database.init_db()

    def tearDown(self):
        os.remove(self.path)
