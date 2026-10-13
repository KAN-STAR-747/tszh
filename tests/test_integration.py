"""Интеграционные тесты: взаимодействие модулей, базы данных, файлов Excel и окон Tkinter."""

import os
import sqlite3
import tempfile
import tkinter as tk
import unittest
from unittest import mock

import openpyxl

import seed_test_data
from db import database
from services import apartments, auth, dates, finance, hoa, reports, requests_service, settings
from services.errors import AppError
from tests.helpers import BaseTest, apartment_data, chairman_data


def resident_data(number="1", login="resident@example.com"):
    return {
        "full_name": "Смирнов Олег Романович",
        "phone": "+79131112233",
        "apartment_number": number,
        "login": login,
        "password": "resident1",
        "password2": "resident1",
    }


class WorkflowTest(BaseTest):
    """Полный путь данных: регистрация -> заявка -> начисление -> оплата -> отчёт в Excel."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())
        self.chairman = auth.login_user("ivanov@example.com", "secret12")
        apartments.save_apartment(apartment_data("1", "40"))
        apartments.save_apartment(apartment_data("2", "50"))
        self.folder = tempfile.mkdtemp()

    def sheet(self, name):
        return list(openpyxl.load_workbook(os.path.join(self.folder, name)).active.values)

    def test_resident_request_payment_and_reports(self):
        self.assertFalse(auth.register_resident(resident_data("1")))
        with self.assertRaises(AppError):
            auth.login_user("resident@example.com", "resident1")
        auth.approve_resident(auth.get_pending_residents()[0]["users_id"])
        resident = auth.login_user("resident@example.com", "resident1")

        request_id = requests_service.create_request(
            resident["users_id"], resident["apartment_id"], "Течёт крыша", "", "Приложение"
        )
        requests_service.move_to_next_status(request_id)
        requests_service.move_to_next_status(request_id)
        self.assertIsNotNone(requests_service.get_request(request_id)["closed_at"])

        finance.charge_month("2026-09")
        finance.add_payment(resident["apartment_id"], "500", "05.09.2026", "Наличные")
        summary = finance.get_resident_summary(resident["apartment_id"])
        self.assertEqual(summary["debt"], 130000 - 50000)

        today = dates.today_text()
        self.assertEqual(reports.export_debtors(os.path.join(self.folder, "d.xlsx")), 2)
        rows = self.sheet("d.xlsx")
        self.assertEqual(rows[0][0], "Квартира")
        self.assertEqual(rows[1][3], 800.0)
        self.assertEqual(rows[2][3], 1625.0)

        count = reports.export_requests(os.path.join(self.folder, "r.xlsx"), "01.01.2026", today)
        self.assertEqual(count, 1)
        self.assertEqual(self.sheet("r.xlsx")[1][:4], ("Течёт крыша", 1, "Приложение", "Выполнена"))

        self.assertEqual(reports.export_members(os.path.join(self.folder, "m.xlsx")), 2)

    def test_report_period_is_checked(self):
        path = os.path.join(self.folder, "r.xlsx")
        with self.assertRaises(AppError):
            reports.export_requests(path, "10.09.2026", "01.09.2026")
        with self.assertRaises(AppError):
            reports.export_requests(path, "2026-09-01", "01.10.2026")
        self.assertFalse(os.path.exists(path))

    def test_deleting_apartment_with_data_is_forbidden(self):
        finance.charge_month("2026-09")
        apartment_id = apartments.get_apartments()[0]["apartment_id"]
        with self.assertRaises(AppError):
            apartments.delete_apartment(apartment_id)
        self.assertEqual(len(apartments.get_apartments()), 2)

    def test_tariff_change_affects_next_charge_only(self):
        finance.charge_month("2026-09")
        hoa.update_hoa({**chairman_data(), "rate": "40"})
        finance.charge_month("2026-10")
        debts = {r["number"]: r["debt"] for r in apartments.get_apartments()}
        self.assertEqual(debts[1], 40 * 3250 + 40 * 4000)

    def test_failed_transaction_is_rolled_back(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with database.transaction() as conn:
                conn.execute("DELETE FROM apartments")
                conn.execute("INSERT INTO apartments (number) VALUES (NULL)")
        self.assertEqual(len(apartments.get_apartments()), 2)


class RecoveryTest(BaseTest):
    """Восстановление пароля: письмо и база изменяются вместе или не изменяются вовсе."""

    def setUp(self):
        super().setUp()
        auth.register_chairman(chairman_data())

    def test_password_changes_when_mail_is_sent(self):
        with mock.patch("services.mailer.send_password") as send:
            auth.recover_account("ivanov@example.com", True)
        new_password = send.call_args[0][1]
        self.assertEqual(send.call_args[0][0], "ivanov@example.com")
        auth.login_user("ivanov@example.com", new_password)
        with self.assertRaises(AppError):
            auth.login_user("ivanov@example.com", "secret12")

    def test_old_password_stays_when_mail_fails(self):
        with mock.patch("services.mailer.send_password", side_effect=AppError("нет связи")):
            with self.assertRaises(AppError):
                auth.recover_account("ivanov@example.com", True)
        auth.login_user("ivanov@example.com", "secret12")

    def test_unknown_account_and_wrong_role(self):
        with self.assertRaises(AppError):
            auth.recover_account("nobody@example.com", True)
        with self.assertRaises(AppError):
            auth.recover_account("ivanov@example.com", False)


class SettingsAndDatesTest(unittest.TestCase):
    def test_env_file_and_environment(self):
        text = "\n".join(
            [
                "# комментарий",
                "SMTP_USER=a@b.ru",
                'export SMTP_PASSWORD="p w"',
                "SMTP_PORT=587",
                "мусор",
            ]
        )
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, ".env"), "w", encoding="utf-8") as file:
                file.write(text)
            with mock.patch.object(settings, "get_app_folder", return_value=folder):
                with mock.patch.dict(os.environ, clear=False):
                    os.environ.pop("SMTP_USER", None)
                    found = settings.get_settings()
                    self.assertEqual(found["smtp_user"], "a@b.ru")
                    self.assertEqual(found["smtp_password"], "p w")
                    self.assertEqual(found["smtp_port"], "587")
                with mock.patch.dict(os.environ, {"SMTP_USER": "env@b.ru"}):
                    self.assertEqual(settings.get_settings()["smtp_user"], "env@b.ru")
                self.assertEqual(settings.get_settings()["smtp_host"], "smtp.gmail.com")

    def test_missing_env_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(settings, "get_app_folder", return_value=folder):
                with mock.patch.dict(os.environ, clear=False):
                    os.environ.pop("SMTP_PORT", None)
                    self.assertEqual(settings.get_settings()["smtp_port"], 465)

    def test_russian_plural_and_months(self):
        self.assertEqual(
            [dates.plural(n, "квартира", "квартиры", "квартир") for n in (1, 3, 5, 11, 21)],
            ["квартира", "квартиры", "квартир", "квартир", "квартира"],
        )
        self.assertEqual(dates.month_to_text("2026-09"), "Сентябрь 2026")
        months = dates.get_month_list(before=2, after=1)
        self.assertEqual(len(months), 4)
        self.assertIn(dates.current_month(), months)


class DatabaseUnavailableTest(unittest.TestCase):
    def test_connection_error_is_raised_not_hidden(self):
        folder = tempfile.mkdtemp()
        old_path = database.DB_PATH
        database.DB_PATH = os.path.join(folder, "нет такой папки", "tszh.db")
        try:
            with self.assertRaises(sqlite3.OperationalError):
                database.query_all("SELECT 1")
        finally:
            database.DB_PATH = old_path


def has_display():
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True


@unittest.skipUnless(has_display(), "нужен графический экран")
class WindowsTest(unittest.TestCase):
    """Окна Tkinter вместе с настоящей базой: что видно на экране, то лежит в БД."""

    @classmethod
    def setUpClass(cls):
        from ui import kit
        from ui.app import App

        handle, cls.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        cls.old_path = database.DB_PATH
        database.DB_PATH = cls.path
        with mock.patch("builtins.print"):
            seed_test_data.fill()
        kit.load_fonts()
        cls.root = tk.Tk()
        cls.app = App(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        database.DB_PATH = cls.old_path
        os.remove(cls.path)

    def test_chairman_tabs_show_database_rows(self):
        chairman = auth.login_user("ivanov@example.com", "ivanov123")
        self.app.show_main(chairman, 0)
        tab = self.app.screen.tab
        self.assertEqual(len(tab.table.rows), len(apartments.get_apartments()))
        tab.search.set("8914")
        tab.refresh_table()
        self.assertEqual(len(tab.table.rows), 0)
        tab.search.set("8913000000")
        tab.refresh_table()
        self.assertEqual(len(tab.table.rows), 8)
        tab.search.set("+7913000000")
        tab.refresh_table()
        self.assertEqual(len(tab.table.rows), 8)
        tab.search.set("кузнецов")
        tab.refresh_table()
        self.assertEqual([row[1][0] for row in tab.table.rows], [3])

        self.app.screen.show_tab(1)
        self.assertEqual(len(self.app.screen.tab.table.rows), len(requests_service.get_requests()))
        self.app.screen.show_tab(2)
        self.assertEqual(len(self.app.screen.tab.table.rows), len(apartments.get_apartments()))
        self.app.screen.show_tab(3)

    def test_status_button_changes_database(self):
        chairman = auth.login_user("ivanov@example.com", "ivanov123")
        self.app.show_main(chairman, 1)
        tab = self.app.screen.tab
        request_id = tab.table.rows[-1][0]
        tab.table.select(request_id)
        tab.show_details(request_id)
        before = requests_service.get_request(request_id)["status"]
        tab.change_status()
        after = requests_service.get_request(request_id)["status"]
        self.assertNotEqual(before, after)
        requests_service.return_to_new(request_id)
        self.assertEqual(requests_service.get_request(request_id)["status"], "Новая")

    def test_resident_sees_only_own_apartment(self):
        resident = auth.login_user("smirnov@example.com", "smirnov123")
        self.app.show_main(resident)
        screen = self.app.screen
        self.assertEqual(screen.apartment["number"], 2)

    def test_unexpected_error_does_not_close_program(self):
        with mock.patch("ui.dialogs.show_error") as show:
            self.app.handle_error(RuntimeError, RuntimeError("сбой базы"), None)
        self.assertIn("сбой базы", show.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
