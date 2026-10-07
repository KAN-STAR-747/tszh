"""Тесты правок после макета: собственник, длина полей, изменение заявок, новые окна."""

import json
import unittest
from unittest import mock

from services import apartments, auth, finance, hoa, mailer, password_generator, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


def resident_data(
    login="smirnov@example.com", name="Смирнов Олег Романович", phone="+79991112233", number="1"
):
    """Данные для регистрации жильца (по умолчанию - не собственник квартиры 1)."""
    return {
        "full_name": name,
        "phone": phone,
        "apartment_number": number,
        "login": login,
        "password": "pass1234",
        "password2": "pass1234",
    }


class OwnerTest(BaseTest):
    """Кто такой собственник и когда вход разрешается без подтверждения."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))

    def test_owner_is_approved_at_once(self):
        data = resident_data("petrov@example.com", "Петров Пётр Петрович", "+79990001122")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov@example.com", "pass1234")
        self.assertTrue(auth.is_owner(user))

    def test_phone_8_and_plus7_are_same(self):
        data = resident_data("petrov@example.com", "Петров Пётр Петрович", "8 999 000 11 22")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov@example.com", "pass1234")
        self.assertEqual(user["phone"], "89990001122")

    def test_other_person_waits_for_chairman(self):
        self.assertFalse(auth.register_resident(resident_data()))
        with self.assertRaises(AppError):
            auth.login_user("smirnov@example.com", "pass1234")
        user_id = auth.get_pending_residents()[0]["users_id"]
        auth.approve_resident(user_id)
        user = auth.login_user("smirnov@example.com", "pass1234")
        self.assertFalse(auth.is_owner(user))
        owner = apartments.get_apartment(user["apartment_id"])["owner_name"]
        self.assertEqual(owner, "Петров Пётр Петрович")


class ChairmanEditTest(BaseTest):
    """Редактирование данных председателя и ТСЖ (окно 21)."""

    def test_update_chairman(self):
        auth.register_chairman(chairman_data())
        user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        data = {
            "full_name": "Иванов Иван Павлович",
            "phone": "8 999 123 45 67",
            "hoa_name": "ТСЖ Новое",
            "inn": "0987654321",
            "address": "г. Томск, ул. Новая, 1",
            "rate": "40",
        }
        auth.update_chairman(user_id, data)
        self.assertEqual(auth.get_user(user_id)["phone"], "89991234567")
        self.assertEqual(hoa.get_hoa()["name"], 'ТСЖ "Новое"')
        self.assertEqual(hoa.get_tariff(), 4000)
        data["inn"] = "123"
        with self.assertRaises(AppError):
            auth.update_chairman(user_id, data)


class RequestEditTest(BaseTest):
    """Длина полей, изменение и удаление заявок."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        self.chairman_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        auth.register_resident(resident_data())
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        self.resident = auth.login_user("smirnov@example.com", "pass1234")

    def test_completed_request_is_read_only(self):
        request_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        requests_service.move_to_next_status(request_id)
        requests_service.move_to_next_status(request_id)
        with self.assertRaises(AppError):
            requests_service.update_request(request_id, "Другое", "Другой")


class FinanceEditTest(BaseTest):
    """Длина полей в финансах и данные для окон «Оплаты» и «Все целевые сборы»."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1", "40"))
        apartments.save_apartment(apartment_data("2", "30"))
        self.ids = [row["apartment_id"] for row in apartments.get_apartments()]

    def test_target_charges_paid_count(self):
        finance.charge_target("На лампочки", "1500", "2026-10")
        finance.add_payment(self.ids[0], "1500", "02.10.2026", "")
        rows = finance.get_target_charges()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["purpose"], rows[0]["amount"]), ("На лампочки", 150000))
        self.assertEqual(rows[0]["paid"], 1)


class RecoveryTests(BaseTest):
    """Восстановление аккаунта: новый пароль уходит на почту (логин), старый перестаёт работать."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        auth.register_resident(resident_data())
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])

    def recover(self, login, chairman):
        """Восстанавливает аккаунт с подменой генератора и почты; возвращает (пароль, письмо)."""
        with mock.patch.object(
            password_generator, "generate_password", return_value="Ab12Cd34"
        ), mock.patch.object(mailer, "send_password") as send:
            auth.recover_account(login, chairman)
        return send

    def test_chairman_gets_new_password_by_email(self):
        send = self.recover("ivanov@example.com", True)
        send.assert_called_once_with("ivanov@example.com", "Ab12Cd34")
        self.assertEqual(auth.login_user("ivanov@example.com", "Ab12Cd34")["is_participant"], 0)
        with self.assertRaises(AppError):
            auth.login_user("ivanov@example.com", "secret12")

    def test_password_unchanged_if_mail_failed(self):
        with mock.patch.object(
            password_generator, "generate_password", return_value="Ab12Cd34"
        ), mock.patch.object(mailer, "send_password", side_effect=AppError("Не отправилось")):
            with self.assertRaises(AppError):
                auth.recover_account("smirnov@example.com", False)
        self.assertEqual(auth.login_user("smirnov@example.com", "pass1234")["is_participant"], 1)
        with self.assertRaises(AppError):
            auth.login_user("smirnov@example.com", "Ab12Cd34")


class PasswordGeneratorTests(unittest.TestCase):
    """Пароль от DeepSeek проверяется; при сбое API создаётся запасной случайный пароль."""

    def settings(self, key="sk-test"):
        return mock.patch.object(
            password_generator.settings, "get_settings", return_value={"deepseek_api_key": key}
        )

    def test_valid_password_rules(self):
        self.assertTrue(password_generator.is_valid("a7K2mQ9z"))
        for wrong in ("a7K2mQ9", "a7K2mQ9zz", "abcdefgh", "12345678", "a7K2mQ9!", None):
            self.assertFalse(password_generator.is_valid(wrong))

    def test_falls_back_when_api_fails_or_answer_is_bad(self):
        for effect in (
            {"side_effect": OSError("нет сети")},
            {"return_value": "слишком длинный ответ"},
        ):
            with self.settings(), mock.patch.object(password_generator, "ask_deepseek", **effect):
                self.assertTrue(password_generator.is_valid(password_generator.generate_password()))


class MailerTests(unittest.TestCase):
    """Письмо уходит через SMTP (с запасным портом) или скрипт Google; без настроек - ошибка."""

    def settings(self, password="app-password", script=""):
        return mock.patch.object(
            mailer.settings,
            "get_settings",
            return_value={
                "smtp_host": "smtp.test",
                "smtp_port": 465,
                "smtp_user": "sender@test.com",
                "smtp_password": password,
                "apps_script_url": script,
                "apps_script_token": "secret-word",
                "sender_name": "ТСЖ",
            },
        )

    def test_smtp_falls_back_to_port_587(self):
        with self.settings(), mock.patch.object(
            mailer.smtplib, "SMTP_SSL", side_effect=TimeoutError
        ), mock.patch.object(mailer.smtplib, "SMTP") as plain:
            mailer.send_password("user@mail.ru", "Ab12Cd34")
        server = plain.return_value.__enter__.return_value
        server.starttls.assert_called_once()
        server.send_message.assert_called_once()

    def answer(self, text):
        """Подменяет ответ скрипта Google (urlopen) заданным JSON-текстом."""
        urlopen = mock.patch.object(mailer.urllib.request, "urlopen")
        started = urlopen.start()
        self.addCleanup(urlopen.stop)
        started.return_value.__enter__.return_value.read.return_value = text.encode("utf-8")
        return started

    def test_sends_password_by_google_script(self):
        urlopen = self.answer('{"ok": true}')
        with self.settings(script="https://script.test/exec"), mock.patch.object(
            mailer.smtplib, "SMTP_SSL"
        ) as smtp:
            mailer.send_password("user@mail.ru", "Ab12Cd34")
        smtp.assert_not_called()
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://script.test/exec")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual((sent["to"], sent["token"]), ("user@mail.ru", "secret-word"))
        self.assertIn("Ab12Cd34", sent["body"])

    def test_not_configured(self):
        with self.settings(""):
            with self.assertRaises(AppError):
                mailer.send_password("user@mail.ru", "Ab12Cd34")


if __name__ == "__main__":
    unittest.main()
