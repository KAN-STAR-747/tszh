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

    def test_case_and_spaces_are_fixed(self):
        self.assertEqual(
            validation.check_full_name("  талаев   ВЛАДИСЛАВ анатольевич "),
            "Талаев Владислав Анатольевич",
        )
        self.assertEqual(
            validation.check_full_name("салтыков-щедрин михаил"), "Салтыков-Щедрин Михаил"
        )

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

    def test_registration_and_profile_require_full_name(self):
        data = {**chairman_data(), "full_name": "Иванов И.И."}
        with self.assertRaises(AppError):
            auth.check_chairman_data(data)


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

    def test_first_letter_is_capital_and_rest_kept(self):
        self.assertEqual(validation.check_hoa_name("тсж берёзка-2"), 'ТСЖ "Берёзка-2"')
        self.assertEqual(validation.check_hoa_name("Дом на Ленина 5"), 'ТСЖ "Дом на Ленина 5"')

    def test_empty_name_is_rejected(self):
        for wrong in ("", "   ", "ТСЖ", 'ТСЖ""', "ТСЖ(())"):
            with self.assertRaises(AppError, msg=wrong):
                validation.check_hoa_name(wrong)

    def test_name_is_saved_in_standard_form(self):
        data = {**chairman_data(), "hoa_name": 'ТСЖ"ТСЖ(Березка)"'}
        self.assertEqual(auth.check_chairman_data(data)["hoa_name"], 'ТСЖ "Березка"')


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

    def test_code_is_sent_but_account_not_created_yet(self):
        login = self.start_chairman()
        self.assertEqual(login, "ivanov@example.com")
        self.send.assert_called_once_with("ivanov@example.com", "4821")
        self.assertFalse(auth.chairman_exists())

    def test_correct_code_creates_chairman(self):
        login = self.start_chairman()
        verification.confirm(login, " 4821 ")
        self.assertTrue(auth.chairman_exists())
        self.assertEqual(auth.login_user("ivanov@example.com", "secret12")["is_participant"], 0)

    def test_correct_code_creates_resident(self):
        auth.register_chairman(chairman_data())
        login = verification.start(verification.RESIDENT, resident_form())
        self.assertEqual(auth.get_pending_residents(), [])
        verification.confirm(login, "4821")
        self.assertEqual(len(auth.get_pending_residents()), 1)

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

    def test_resend_has_cooldown_and_replaces_code(self):
        login = self.start_chairman()
        with self.assertRaises(AppError):
            verification.resend(login)
        self.clock += verification.RESEND_SECONDS + 1
        with mock.patch.object(verification, "make_code", return_value="1357"):
            verification.resend(login)
        self.assertEqual(self.send.call_count, 2)
        with self.assertRaises(AppError):
            verification.confirm(login, "4821")
        verification.confirm(login, "1357")
        self.assertTrue(auth.chairman_exists())

    def test_mail_failure_means_no_pending_registration(self):
        self.send.side_effect = AppError("Не удалось отправить письмо")
        with self.assertRaises(AppError):
            self.start_chairman()
        with self.assertRaises(AppError):
            verification.confirm("ivanov@example.com", "4821")

    def test_bad_form_or_taken_email_sends_no_code(self):
        auth.register_chairman(chairman_data())
        for form in (
            resident_form(full_name="Смирнов О.Р."),
            resident_form(login="не-почта"),
            resident_form(login="ivanov@example.com"),
        ):
            with self.assertRaises(AppError):
                verification.start(verification.RESIDENT, form)
        self.send.assert_not_called()

    def test_code_letter_contains_code(self):
        subject, text = mailer.code_letter("4821")
        self.assertIn("4821", text)
        self.assertIn("подтверждения", subject)


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

    def test_resident_changes_password(self):
        auth.update_profile(
            self.resident["users_id"], "Смирнов Олег Романович", "+79991112233", "newpass99"
        )
        self.assertEqual(auth.login_user("smirnov@example.com", "newpass99")["is_participant"], 1)
        with self.assertRaises(AppError):
            auth.login_user("smirnov@example.com", "pass1234")

    def test_without_new_password_old_one_stays(self):
        auth.update_profile(self.resident["users_id"], "Смирнов Олег Игоревич", "+79991112233")
        user = auth.login_user("smirnov@example.com", "pass1234")
        self.assertEqual(user["full_name"], "Смирнов Олег Игоревич")

    def test_short_password_changes_nothing(self):
        with self.assertRaises(AppError):
            auth.update_profile(
                self.resident["users_id"], "Смирнов Олег Игоревич", "+79991112233", "123"
            )
        user = auth.login_user("smirnov@example.com", "pass1234")
        self.assertEqual(user["full_name"], "Смирнов Олег Романович")
        with self.assertRaises(AppError):
            auth.update_chairman(self.chairman["users_id"], self.chairman_data(), "short")
        self.assertEqual(
            auth.login_user("ivanov@example.com", "secret12")["login"], "ivanov@example.com"
        )

    def test_login_cannot_be_changed(self):
        auth.update_profile(
            self.resident["users_id"], "Смирнов Олег Романович", "+79991112233", "newpass99"
        )
        self.assertEqual(auth.get_user(self.resident["users_id"])["login"], "smirnov@example.com")


if __name__ == "__main__":
    unittest.main()
