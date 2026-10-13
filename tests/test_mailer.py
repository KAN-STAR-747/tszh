"""Тесты отправки писем и кодов подтверждения (сеть подменена)."""

import io
import json
import smtplib
import socket
import ssl
import unittest
import urllib.error
from unittest import mock

from services import auth, hoa, mailer, verification
from services.errors import AppError
from tests.helpers import BaseTest, chairman_data

SCRIPT = {
    "apps_script_url": "https://script.example/exec",
    "apps_script_token": "t",
    "sender_name": "ТСЖ",
    "smtp_user": "",
    "smtp_password": "",
}


class MailerTest(unittest.TestCase):
    def send(self, config, **kwargs):
        with mock.patch.object(mailer.settings, "get_settings", return_value=config):
            return mailer.send_mail("a@b.ru", "Тема", "Текст")

    def test_not_configured(self):
        with self.assertRaises(AppError) as error:
            self.send({**SCRIPT, "apps_script_url": ""})
        self.assertIn(".env", str(error.exception))

    def test_script_answer_ok_and_refused(self):
        for answer, fails in (({"ok": True}, False), ({"ok": False, "error": "token"}, True)):
            response = io.BytesIO(json.dumps(answer).encode())
            with mock.patch("urllib.request.urlopen", return_value=response):
                if fails:
                    with self.assertRaises(AppError) as error:
                        self.send(SCRIPT)
                    self.assertIn("token", str(error.exception))
                else:
                    self.send(SCRIPT)

    def test_network_errors_get_clear_messages(self):
        http = urllib.error.HTTPError("u", 403, "no", {}, None)
        cases = [
            (http, "403"),
            (ssl.SSLError("bad"), "сертификат"),
            (socket.gaierror("dns"), "DNS"),
            (OSError("down"), "VPN"),
        ]
        for error, word in cases:
            with mock.patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(AppError) as raised:
                    self.send(SCRIPT)
            self.assertIn(word, str(raised.exception))

    def test_smtp_login_refused_and_unreachable(self):
        config = {**SCRIPT, "apps_script_url": "", "smtp_user": "u", "smtp_password": "p"}
        config.update(smtp_host="h", smtp_port=465)
        with mock.patch.object(
            mailer, "send_by_smtp", side_effect=smtplib.SMTPAuthenticationError(535, b"x")
        ):
            with self.assertRaises(AppError) as raised:
                self.send(config)
        self.assertIn("Gmail", str(raised.exception))
        with mock.patch.object(mailer, "send_by_smtp", side_effect=OSError("closed")):
            with self.assertRaises(AppError) as raised:
                self.send(config)
        self.assertIn("порты", str(raised.exception))

    def test_letters_contain_code_and_password(self):
        self.assertIn("1234", mailer.code_letter("1234")[1])
        self.assertIn("Pass9", mailer.password_letter("Pass9")[1])


class CodeTest(BaseTest):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.mailer.send_code")
        self.send = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(verification.cancel, "ivanov@example.com")
        self.clock = [1000.0]
        clock = mock.patch.object(verification, "now", lambda: self.clock[0])
        clock.start()
        self.addCleanup(clock.stop)

    def code(self):
        return self.send.call_args[0][1]

    def test_chairman_registered_after_right_code(self):
        login = verification.start(verification.CHAIRMAN, chairman_data())
        verification.confirm(login, self.code())
        self.assertTrue(auth.chairman_exists())
        with self.assertRaises(AppError):
            verification.confirm(login, self.code())

    def test_nothing_is_created_before_code(self):
        verification.start(verification.CHAIRMAN, chairman_data())
        self.assertFalse(auth.chairman_exists())

    def test_expired_code_and_attempt_limit(self):
        login = verification.start(verification.CHAIRMAN, chairman_data())
        self.clock[0] += verification.LIFETIME_SECONDS + 1
        with self.assertRaises(AppError) as raised:
            verification.confirm(login, self.code())
        self.assertIn("устарел", str(raised.exception))

        login = verification.start(verification.CHAIRMAN, chairman_data())
        for _ in range(verification.MAX_ATTEMPTS):
            with self.assertRaises(AppError):
                verification.confirm(login, "0000" if self.code() != "0000" else "1111")
        with self.assertRaises(AppError) as raised:
            verification.confirm(login, self.code())
        self.assertIn("заново", str(raised.exception))

    def test_resend_waits_and_replaces_code(self):
        login = verification.start(verification.CHAIRMAN, chairman_data())
        with self.assertRaises(AppError):
            verification.resend(login)
        self.clock[0] += verification.RESEND_SECONDS + 1
        verification.resend(login)
        self.assertEqual(self.send.call_count, 2)
        with self.assertRaises(AppError):
            verification.resend("nobody@example.com")

    def test_busy_login_is_rejected_before_sending(self):
        auth.register_chairman(chairman_data())
        with self.assertRaises(AppError):
            verification.start(verification.CHAIRMAN, chairman_data())
        self.send.assert_not_called()


class ChairmanEditLimitsTest(BaseTest):
    """Найдено при тестировании: при правке данных ТСЖ тариф и адрес не ограничивались."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        self.user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]

    def test_tariff_and_address_limits_on_edit(self):
        too_big = {**chairman_data(), "rate": "501"}
        with self.assertRaises(AppError):
            auth.update_chairman(self.user_id, too_big)
        with self.assertRaises(AppError):
            hoa.update_hoa(too_big)
        long_address = {**chairman_data(), "address": "ул. Длинная, " * 30}
        with self.assertRaises(AppError):
            auth.update_chairman(self.user_id, long_address)
        self.assertEqual(hoa.get_tariff(), 3250)


if __name__ == "__main__":
    unittest.main()
