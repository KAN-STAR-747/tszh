"""Замер отклика и памяти на доме из 500 квартир (ТЗ: отклик до 2 с, отчёт до 5 с).

Запуск: python -m tests.performance_check
Работает на временной базе, рабочая база tszh.db не затрагивается.
"""

import ctypes
import os
import tempfile
import time
import tkinter as tk
from ctypes import wintypes
from unittest import mock

from db import database
from services import address, apartments, auth, finance, reports, requests_service
from tests.helpers import chairman_data

SURNAMES = [
    "Иванов",
    "Петров",
    "Сидоров",
    "Кузнецов",
    "Смирнов",
    "Попов",
    "Васильев",
    "Соколов",
    "Михайлов",
    "Новиков",
    "Фёдоров",
    "Морозов",
    "Волков",
    "Алексеев",
    "Лебедев",
    "Семёнов",
    "Егоров",
    "Павлов",
    "Козлов",
    "Степанов",
    "Николаев",
    "Орлов",
    "Андреев",
    "Макаров",
    "Никитин",
]
NAMES = [
    "Алексей",
    "Борис",
    "Виктор",
    "Глеб",
    "Денис",
    "Егор",
    "Иван",
    "Кирилл",
    "Леонид",
    "Максим",
    "Никита",
    "Олег",
    "Павел",
    "Роман",
    "Сергей",
    "Тимур",
    "Фёдор",
    "Артём",
    "Игорь",
    "Юрий",
]
APARTMENTS = 500
MONTHS = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
REQUESTS = 600
LIMITS = {"отчёт": 5.0, "действие": 2.0}


def memory_mb():
    """Память процесса (рабочий набор) в мегабайтах."""

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.WorkingSetSize / 1024 / 1024


def timed(title, kind, action, results):
    start = time.perf_counter()
    action()
    seconds = time.perf_counter() - start
    verdict = "норма" if seconds <= LIMITS[kind] else "ПРЕВЫШЕНО"
    results.append((title, seconds, LIMITS[kind], verdict))
    print(
        f"{title:<48}{seconds * 1000:>9.1f} мс   (допустимо {LIMITS[kind] * 1000:.0f} мс) {verdict}"
    )


def fill_database():
    with mock.patch.object(address, "normalize", side_effect=lambda raw: raw):
        auth.register_chairman(chairman_data())
    for number in range(1, APARTMENTS + 1):
        apartments.save_apartment(
            {
                "number": str(number),
                "area": str(30 + number % 60),
                "owner_name": f"{SURNAMES[number % 25]} {NAMES[number // 25 % 20]}",
                "owner_phone": f"+7913{number:07d}",
                "is_member": number % 2 == 0,
            }
        )
    for month in MONTHS:
        finance.charge_month(month)
    rows = apartments.get_apartments()
    for row in rows[::2]:
        finance.add_payment(row["apartment_id"], "1500", "10.03.2026", "Оплата")
    user_id = auth.login_user("ivanov@example.com", "secret12")["users_id"]
    for index in range(REQUESTS):
        requests_service.create_request(
            user_id, rows[index % APARTMENTS]["apartment_id"], f"Заявка {index}", "", "Звонок"
        )


def main():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    database.DB_PATH = path
    database.init_db()
    folder = tempfile.mkdtemp()
    results = []
    print(f"Дом: {APARTMENTS} квартир, {len(MONTHS)} месяцев начислений, {REQUESTS} заявок")

    start = time.perf_counter()
    fill_database()
    print(f"Подготовка данных: {time.perf_counter() - start:.1f} с")
    print(f"Размер файла базы данных: {os.path.getsize(path) / 1024:.0f} КБ")
    base_memory = memory_mb()
    print(f"Память до замеров: {base_memory:.1f} МБ\n")

    timed("Список квартир с долгами", "действие", apartments.get_apartments, results)
    timed("Поиск по телефону", "действие", lambda: apartments.get_apartments("8913005"), results)
    timed("Поиск по ФИО", "действие", lambda: apartments.get_apartments("кузнецов"), results)
    timed("Список заявок", "действие", requests_service.get_requests, results)
    timed(
        "Таблица «Финансы» за месяц",
        "действие",
        lambda: finance.get_month_table("2026-03"),
        results,
    )
    timed(
        "Ежемесячное начисление всем квартирам",
        "действие",
        lambda: finance.charge_month("2026-07"),
        results,
    )
    first = apartments.get_apartments()[0]["apartment_id"]
    timed(
        "Внесение оплаты",
        "действие",
        lambda: finance.add_payment(first, "100", "11.03.2026", ""),
        results,
    )
    timed(
        "Отчёт «Должники» в Excel",
        "отчёт",
        lambda: reports.export_debtors(os.path.join(folder, "d.xlsx")),
        results,
    )
    timed(
        "Отчёт «Заявки за период» в Excel",
        "отчёт",
        lambda: reports.export_requests(os.path.join(folder, "r.xlsx"), "01.01.2026", "31.12.2026"),
        results,
    )
    timed(
        "Отчёт «Реестр членов ТСЖ» в Excel",
        "отчёт",
        lambda: reports.export_members(os.path.join(folder, "m.xlsx")),
        results,
    )

    try:
        from ui import kit
        from ui.app import App

        kit.load_fonts()
        root = tk.Tk()
        app = App(root)
        chairman = auth.login_user("ivanov@example.com", "secret12")
        timed(
            "Открытие окна председателя (вкладка «Квартиры»)",
            "действие",
            lambda: app.show_main(chairman, 0),
            results,
        )
        for index, name in enumerate(["Заявки", "Финансы", "Отчёты"], start=1):
            timed(
                f"Переход на вкладку «{name}»",
                "действие",
                lambda i=index: (app.screen.show_tab(i), root.update()),
                results,
            )
        peak_ui = memory_mb()
        print(f"\nПамять с открытым окном программы: {peak_ui:.1f} МБ")
        root.destroy()
    except tk.TclError:
        print("Нет графического экрана: замеры окон пропущены")

    slowest = max(results, key=lambda r: r[1])
    print(f"\nСамое долгое действие: {slowest[0]} - {slowest[1] * 1000:.0f} мс")
    print(
        "Вывод:",
        (
            "все действия укладываются в требования ТЗ"
            if all(r[3] == "норма" for r in results)
            else "есть превышение"
        ),
    )
    os.remove(path)


if __name__ == "__main__":
    main()
