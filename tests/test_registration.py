"""Тесты регистрации: ФИО полностью, название ТСЖ, подтверждение почты кодом из 4 цифр."""

import unittest
from unittest import mock

from services import auth, mailer, validation, verification
from services.errors import AppError
from tests.helpers import BaseTest, chairman_data


class FullNameTests(unittest.TestCase):
    def test_full_name_with_and_without_patronymic(self):
        self.assertEqual(
            validation.check_full_name("Талаев Владислав Анатольевич"),
            "Талаев Владислав Анатольевич",
        )
        self.assertEqual(validation.check_full_name("Талаев Владислав"), "Талаев Владислав")

    def test_incomplete_or_wrong_name_is_rejected(self):
        for wrong in (
            "",
            "Талаев",
            "Талаев В. А.",
            "Талаев В.А.",
            "Талаев Владислав Анатольевич Иванович",
            "Талаев Влад1слав",
            "Талаев Владислав@",
        ):
            with self.assertRaises(AppError, msg=wrong):
                validation.check_full_name(wrong)


class HoaNameTests(unittest.TestCase):
    def test_any_form_becomes_hoa_with_quotes(self):
        for raw in (
            "Березка",
            "ТСЖ Березка",
            'ТСЖ "Березка"',
            "тсж березка",
            'ТСЖ"ТСЖ(Березка)"',
            "ТСЖ «Березка»",
            "ТСЖ ((Березка))  ",
            "'Березка'",
            "ТСЖБерезка",
        ):
            self.assertEqual(validation.check_hoa_name(raw), 'ТСЖ "Березка"', raw)

    def test_empty_name_is_rejected(self):
        for wrong in ("", "   ", "ТСЖ", 'ТСЖ""', "ТСЖ(())"):
            with self.assertRaises(AppError, msg=wrong):
                validation.check_hoa_name(wrong)


class CodeTests(unittest.TestCase):
    def test_code_is_four_random_digits(self):
        codes = {verification.make_code() for _ in range(200)}
        self.assertTrue(all(len(code) == 4 and code.isdigit() for code in codes))
        self.assertGreater(len(codes), 100)


def resident_form(**changes):
    """Форма регистрации жильца."""
    form = {
        "full_name": "Смирнов Олег Романович",
        "phone": "+79991112233",
        "apartment_number": "1",
        "login": "smirnov@example.com",
        "password": "pass1234",
        "password2": "pass1234",
    }
    form.update(changes)
    return form


class VerificationTests(BaseTest):
    """Аккаунт создаётся только после ввода кода, который пришёл на почту."""

    def setUp(self):
        super().setUp()
        verification._pending.clear()
        self.addCleanup(verification._pending.clear)
        self.clock = 1000.0
        for patcher in (
            mock.patch.object(verification, "now", side_effect=lambda: self.clock),
            mock.patch.object(verification, "make_code", return_value="4821"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        sender = mock.patch.object(mailer, "send_code")
        self.send = sender.start()
        self.addCleanup(sender.stop)

    def start_chairman(self):
        return verification.start(verification.CHAIRMAN, chairman_data())

    def test_correct_code_creates_chairman(self):
        login = self.start_chairman()
        verification.confirm(login, " 4821 ")
        self.assertTrue(auth.chairman_exists())
        self.assertEqual(auth.login_user("ivanov@example.com", "secret12")["is_participant"], 0)

    def test_wrong_code_is_rejected_and_attempts_are_limited(self):
        login = self.start_chairman()
        for left in (4, 3, 2, 1):
            with self.assertRaises(AppError) as error:
                verification.confirm(login, "0000")
            self.assertIn(f"Осталось попыток: {left}", str(error.exception))
        with self.assertRaises(AppError):
            verification.confirm(login, "0000")
        with self.assertRaises(AppError):
            verification.confirm(login, "4821")
        self.assertFalse(auth.chairman_exists())

    def test_code_expires(self):
        login = self.start_chairman()
        self.clock += verification.LIFETIME_SECONDS + 1
        with self.assertRaises(AppError):
            verification.confirm(login, "4821")
        self.assertFalse(auth.chairman_exists())


class PasswordChangeTests(BaseTest):
    """В настройках можно сменить пароль; неверный новый пароль ничего не меняет."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        auth.register_resident(resident_form())
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        self.chairman = auth.login_user("ivanov@example.com", "secret12")
        self.resident = auth.login_user("smirnov@example.com", "pass1234")

    def chairman_data(self, **changes):
        data = {
            "full_name": "Иванов Иван Иванович",
            "phone": "+77777777777",
            "hoa_name": "Березка",
            "inn": "1234567890",
            "address": "Одоевского 1",
            "rate": "32,50",
        }
        data.update(changes)
        return data

    def test_chairman_changes_password(self):
        auth.update_chairman(self.chairman["users_id"], self.chairman_data(), "newpass99")
        self.assertEqual(auth.login_user("ivanov@example.com", "newpass99")["is_participant"], 0)
        with self.assertRaises(AppError):
            auth.login_user("ivanov@example.com", "secret12")


if __name__ == "__main__":
    unittest.main()
