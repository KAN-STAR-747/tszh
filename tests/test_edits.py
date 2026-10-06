"""Тесты правок после макета: собственник, длина полей, изменение заявок, новые окна."""

import json
import unittest
from unittest import mock

from services import apartments, auth, finance, hoa, mailer, password_generator, requests_service
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


def resident_data(
    login="smirnov@example.com", name="Смирнов О.Р.", phone="+79991112233", number="1"
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

    # Перед каждым тестом: председатель и квартира 1 (собственник Петров П.П., +79990001122)
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))

    # Совпали фамилия и телефон: это собственник, подтверждение председателя не нужно
    def test_owner_is_approved_at_once(self):
        data = resident_data("petrov@example.com", "Петров Пётр Петрович", "+79990001122")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov@example.com", "pass1234")
        self.assertTrue(auth.is_owner(user))

    # В реестре телефон +79990001122; жилец вводит его с «8» и пробелами - это тот же номер
    def test_phone_8_and_plus7_are_same(self):
        data = resident_data("petrov@example.com", "Петров П.П.", "8 999 000 11 22")
        self.assertTrue(auth.register_resident(data))
        user = auth.login_user("petrov@example.com", "pass1234")
        self.assertEqual(user["phone"], "89990001122")  # пробелы в базе не сохраняются

    # Телефон собственника в реестре записан с «8», жилец вводит его с «+7»
    def test_plus7_matches_8(self):
        apartments.save_apartment(
            {**apartment_data("2"), "owner_name": "Сидоров С.С.", "owner_phone": "89135554433"}
        )
        data = resident_data("sidorov@example.com", "Сидоров Сергей", "+7 913 555 44 33", "2")
        self.assertTrue(auth.register_resident(data))

    # Другая фамилия: это не собственник, нужно подтверждение, а в кабинете виден собственник
    def test_other_person_waits_for_chairman(self):
        self.assertFalse(auth.register_resident(resident_data()))
        with self.assertRaises(AppError):
            auth.login_user("smirnov@example.com", "pass1234")
        user_id = auth.get_pending_residents()[0]["users_id"]
        auth.approve_resident(user_id)
        user = auth.login_user("smirnov@example.com", "pass1234")
        self.assertFalse(auth.is_owner(user))
        owner = apartments.get_apartment(user["apartment_id"])["owner_name"]
        self.assertEqual(owner, "Петров П.П.")

    # Квартиры нет в реестре: она создаётся, жилец становится собственником после подтверждения
    def test_new_apartment_owner_by_registration(self):
        self.assertFalse(auth.register_resident(resident_data(number="5")))
        apartment = apartments.get_apartment_by_number(5)
        self.assertEqual(apartment["area"], 0)
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        user = auth.login_user("smirnov@example.com", "pass1234")
        self.assertTrue(auth.is_owner(user))

    # Если председатель отклонил жильца, созданная для него квартира тоже удаляется
    def test_reject_removes_new_apartment(self):
        auth.register_resident(resident_data(number="5"))
        auth.reject_resident(auth.get_pending_residents()[0]["users_id"])
        self.assertIsNone(apartments.get_apartment_by_number(5))

    # Квартира без площади не участвует в начислениях
    def test_zero_area_apartment_not_charged(self):
        auth.register_resident(resident_data(number="5"))
        self.assertEqual(finance.charge_month("2026-09"), 1)

    # Собственник меняет телефон: он остаётся собственником, запись о квартире меняется вместе
    def test_owner_profile_change_keeps_ownership(self):
        data = resident_data("petrov@example.com", "Петров Пётр Петрович", "+79990001122")
        auth.register_resident(data)
        user = auth.login_user("petrov@example.com", "pass1234")
        auth.update_profile(user["users_id"], "Петров Пётр Петрович", "+79995556677")
        changed = auth.login_user("petrov@example.com", "pass1234")
        self.assertTrue(auth.is_owner(changed))

    # Занятый логин не оставляет следов: квартира для такой регистрации не создаётся
    def test_duplicate_login_does_not_create_apartment(self):
        auth.register_resident(resident_data(number="5"))
        with self.assertRaises(AppError):
            auth.register_resident(resident_data(number="6"))
        self.assertIsNone(apartments.get_apartment_by_number(6))

    # В окне «Жильцы» видны только подтверждённые жильцы
    def test_residents_list(self):
        auth.register_resident(resident_data("petrov@example.com", "Петров Пётр", "+79990001122"))
        auth.register_resident(resident_data("smirnov@example.com"))
        residents = auth.get_residents()
        self.assertEqual(len(residents), 1)
        self.assertEqual(residents[0]["number"], 1)

    # У жильца виден телефон председателя
    def test_chairman_contacts(self):
        chairman = auth.get_chairman()
        self.assertEqual(chairman["phone"], "+77777777777")


class ChairmanEditTest(BaseTest):
    """Редактирование данных председателя и ТСЖ (окно 21)."""

    def test_update_chairman(self):
        auth.register_chairman(chairman_data())
        user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        data = {
            "full_name": "Иванов И.П.",
            "phone": "8 999 123 45 67",
            "hoa_name": "ТСЖ Новое",
            "inn": "0987654321",
            "address": "г. Томск, ул. Новая, 1",
            "rate": "40",
        }
        auth.update_chairman(user_id, data)
        self.assertEqual(auth.get_user(user_id)["phone"], "89991234567")  # пробелы убраны
        self.assertEqual(hoa.get_hoa()["name"], "ТСЖ Новое")
        self.assertEqual(hoa.get_tariff(), 4000)
        data["inn"] = "123"  # неверный ИНН - ничего не сохраняется
        with self.assertRaises(AppError):
            auth.update_chairman(user_id, data)


class RequestEditTest(BaseTest):
    """Длина полей, изменение и удаление заявок."""

    # Перед каждым тестом: председатель, квартира 1 и жилец в ней
    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1"))
        self.chairman_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
        auth.register_resident(resident_data())
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        self.resident = auth.login_user("smirnov@example.com", "pass1234")

    # Тема - до 50 символов, описание - до 250, исполнитель - до 25
    def test_length_limits(self):
        create = requests_service.create_request
        create(self.chairman_id, None, "т" * 50, "о" * 250, "Звонок", "и" * 25)  # ровно по границе
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "т" * 51, "", "Звонок")
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "Тема", "о" * 251, "Звонок")
        with self.assertRaises(AppError):
            create(self.chairman_id, None, "Тема", "", "Звонок", "и" * 26)

    # Председатель меняет описание и исполнителя
    def test_update_request(self):
        request_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        requests_service.update_request(request_id, "Новое описание", "ООО Сервис")
        request = requests_service.get_request(request_id)
        self.assertEqual(request["description"], "Новое описание")
        self.assertEqual(request["executor"], "ООО Сервис")

    # Выполненную заявку изменять нельзя
    def test_completed_request_is_read_only(self):
        request_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        requests_service.move_to_next_status(request_id)
        requests_service.move_to_next_status(request_id)
        with self.assertRaises(AppError):
            requests_service.update_request(request_id, "Другое", "Другой")

    # Жилец удаляет свою новую заявку
    def test_resident_deletes_new_request(self):
        apartment_id = self.resident["apartment_id"]
        request_id = requests_service.create_request(
            self.resident["users_id"], apartment_id, "Кран", "", "Приложение"
        )
        requests_service.delete_own_request(self.resident["users_id"], request_id)
        self.assertIsNone(requests_service.get_request(request_id))

    # Заявку «В работе» жилец удалить не может, как и чужую
    def test_resident_cannot_delete_foreign_or_taken_request(self):
        request_id = requests_service.create_request(
            self.resident["users_id"], None, "Кран", "", "Приложение"
        )
        requests_service.move_to_next_status(request_id)  # теперь «В работе»
        with self.assertRaises(AppError):
            requests_service.delete_own_request(self.resident["users_id"], request_id)
        foreign_id = requests_service.create_request(self.chairman_id, None, "Лифт", "", "Звонок")
        with self.assertRaises(AppError):
            requests_service.delete_own_request(self.resident["users_id"], foreign_id)


class FinanceEditTest(BaseTest):
    """Длина полей в финансах и данные для окон «Оплаты» и «Все целевые сборы»."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        apartments.save_apartment(apartment_data("1", "40"))
        apartments.save_apartment(apartment_data("2", "30"))
        self.ids = [row["apartment_id"] for row in apartments.get_apartments()]

    # Назначение сбора - до 50 символов, комментарий оплаты - до 50
    def test_length_limits(self):
        finance.charge_target("н" * 50, "100", "2026-10")
        with self.assertRaises(AppError):
            finance.charge_target("н" * 51, "100", "2026-11")
        finance.add_payment(self.ids[0], "10", "01.10.2026", "к" * 50)
        with self.assertRaises(AppError):
            finance.add_payment(self.ids[0], "10", "01.10.2026", "к" * 51)

    # В окне «Оплаты» видны оплаты всех квартир, свежие сверху
    def test_all_payments(self):
        finance.add_payment(self.ids[0], "100", "01.10.2026", "Первая")
        finance.add_payment(self.ids[1], "200", "05.10.2026", "Вторая")
        payments = finance.get_all_payments()
        self.assertEqual([p["comment"] for p in payments], ["Вторая", "Первая"])
        self.assertEqual(payments[0]["number"], 2)

    # В окне «Все целевые сборы» считаем, сколько квартир оплатило сбор
    def test_target_charges_paid_count(self):
        finance.charge_target("На лампочки", "1500", "2026-10")
        finance.add_payment(self.ids[0], "1500", "02.10.2026", "")  # квартира 1 оплатила
        rows = finance.get_target_charges()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["purpose"], rows[0]["amount"]), ("На лампочки", 150000))
        self.assertEqual(rows[0]["paid"], 1)  # из двух квартир оплатила одна

    # Ежемесячное начисление «Содержание» в целевые сборы не попадает
    def test_maintenance_is_not_target_charge(self):
        finance.charge_month("2026-09")
        self.assertEqual(finance.get_target_charges(), [])


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

    def test_resident_gets_new_password_by_email(self):
        send = self.recover("Smirnov@Example.com", False)  # регистр почты не важен
        send.assert_called_once_with("smirnov@example.com", "Ab12Cd34")
        self.assertEqual(auth.login_user("smirnov@example.com", "Ab12Cd34")["is_participant"], 1)
        with self.assertRaises(AppError):
            auth.login_user("smirnov@example.com", "pass1234")

    def test_unknown_or_wrong_role_is_rejected(self):
        # такой почты нет; почта жильца при выборе «председатель»; почта председателя у «жильца»
        for login, chairman in (
            ("nobody@example.com", False),
            ("smirnov@example.com", True),
            ("ivanov@example.com", False),
            ("не почта", True),
        ):
            with mock.patch.object(mailer, "send_password") as send:
                with self.assertRaises(AppError):
                    auth.recover_account(login, chairman)
            send.assert_not_called()
        self.assertEqual(
            auth.login_user("ivanov@example.com", "secret12")["login"], "ivanov@example.com"
        )

    def test_password_unchanged_if_mail_failed(self):
        with mock.patch.object(
            password_generator, "generate_password", return_value="Ab12Cd34"
        ), mock.patch.object(mailer, "send_password", side_effect=AppError("Не отправилось")):
            with self.assertRaises(AppError):
                auth.recover_account("smirnov@example.com", False)
        # письмо не ушло, поэтому старый пароль остался рабочим, а новый - нет
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

    def test_random_password_is_valid(self):
        for _ in range(20):
            self.assertTrue(password_generator.is_valid(password_generator.random_password()))

    def test_uses_deepseek_answer(self):
        with self.settings(), mock.patch.object(
            password_generator, "ask_deepseek", return_value="a7K2mQ9z"
        ) as ask:
            self.assertEqual(password_generator.generate_password(), "a7K2mQ9z")
        ask.assert_called_once_with("sk-test")

    def test_falls_back_when_api_fails_or_answer_is_bad(self):
        for effect in (
            {"side_effect": OSError("нет сети")},
            {"return_value": "слишком длинный ответ"},
        ):
            with self.settings(), mock.patch.object(password_generator, "ask_deepseek", **effect):
                self.assertTrue(password_generator.is_valid(password_generator.generate_password()))

    def test_no_key_means_no_request(self):
        with self.settings(""), mock.patch.object(password_generator, "ask_deepseek") as ask:
            self.assertTrue(password_generator.is_valid(password_generator.generate_password()))
        ask.assert_not_called()


class MailerTests(unittest.TestCase):
    """Письмо уходит через SMTP (с запасным портом) или через Brevo; без настроек - ошибка."""

    def settings(self, password="app-password", brevo="", script=""):
        return mock.patch.object(
            mailer.settings,
            "get_settings",
            return_value={
                "smtp_host": "smtp.test",
                "smtp_port": 465,
                "smtp_user": "sender@test.com",
                "smtp_password": password,
                "brevo_api_key": brevo,
                "apps_script_url": script,
                "apps_script_token": "secret-word",
                "sender_name": "ТСЖ",
            },
        )

    def test_sends_password_by_smtp(self):
        with self.settings(), mock.patch.object(mailer.smtplib, "SMTP_SSL") as smtp:
            mailer.send_password("user@mail.ru", "Ab12Cd34")
        server = smtp.return_value.__enter__.return_value
        server.login.assert_called_once_with("sender@test.com", "app-password")
        message = server.send_message.call_args[0][0]
        self.assertEqual(message["To"], "user@mail.ru")
        self.assertIn("Ab12Cd34", message.get_content())

    def test_smtp_falls_back_to_port_587(self):
        with self.settings(), mock.patch.object(
            mailer.smtplib, "SMTP_SSL", side_effect=TimeoutError
        ), mock.patch.object(mailer.smtplib, "SMTP") as plain:
            mailer.send_password("user@mail.ru", "Ab12Cd34")
        server = plain.return_value.__enter__.return_value
        server.starttls.assert_called_once()
        server.send_message.assert_called_once()

    def test_sends_password_by_brevo_over_https(self):
        with self.settings(brevo="key-123"), mock.patch.object(
            mailer.urllib.request, "urlopen"
        ) as urlopen, mock.patch.object(mailer.smtplib, "SMTP_SSL") as smtp:
            mailer.send_password("user@mail.ru", "Ab12Cd34")
        smtp.assert_not_called()  # с ключом Brevo SMTP не нужен
        request = urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Api-key"), "key-123")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["to"], [{"email": "user@mail.ru"}])
        self.assertEqual(sent["sender"]["email"], "sender@test.com")
        self.assertIn("Ab12Cd34", sent["textContent"])

    def test_brevo_refusal_becomes_app_error(self):
        refusal = mailer.urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
        with self.settings(brevo="bad"), mock.patch.object(
            mailer.urllib.request, "urlopen", side_effect=refusal
        ):
            with self.assertRaises(AppError) as error:
                mailer.send_password("user@mail.ru", "Ab12Cd34")
        self.assertIn("401", str(error.exception))

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

    def test_google_script_refusal_becomes_app_error(self):
        self.answer('{"ok": false, "error": "неверный токен"}')
        with self.settings(script="https://script.test/exec"):
            with self.assertRaises(AppError) as error:
                mailer.send_password("user@mail.ru", "Ab12Cd34")
        self.assertIn("неверный токен", str(error.exception))

    def test_not_configured(self):
        with self.settings(""):
            with self.assertRaises(AppError):
                mailer.send_password("user@mail.ru", "Ab12Cd34")

    def test_send_failure_becomes_app_error(self):
        with self.settings(), mock.patch.object(
            mailer.smtplib, "SMTP_SSL", side_effect=OSError
        ), mock.patch.object(mailer.smtplib, "SMTP", side_effect=OSError):
            with self.assertRaises(AppError):
                mailer.send_password("user@mail.ru", "Ab12Cd34")


if __name__ == "__main__":
    unittest.main()
