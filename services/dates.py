"""Функции для работы с датами и месяцами начислений."""

from datetime import date, datetime

# Названия месяцев по порядку (индекс 0 - январь)
MONTH_NAMES = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def plural(number, one, few, many):
    """Выбирает форму слова по числу: 1 начисление, 2 начисления, 5 начислений."""
    rest = abs(number) % 100  # смотрим на последние две цифры
    if 11 <= rest <= 14:  # 11-14 - особый случай: «11 начислений»
        return many
    last = rest % 10  # последняя цифра
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def month_to_text(month):
    """Переводит «2026-09» в «Сентябрь 2026»."""
    year, number = month.split("-")  # split делит строку по дефису на две части
    return f"{MONTH_NAMES[int(number) - 1]} {year}"  # -1, потому что список с нуля


def get_month_list(before=12, after=3):
    """Возвращает список месяцев ГГГГ-ММ вокруг текущего."""
    today = date.today()
    # Считаем месяцы одним числом: год * 12 + номер месяца, так проще шагать по месяцам
    current = today.year * 12 + today.month - 1
    months = []
    for value in range(current - before, current + after + 1):
        months.append(f"{value // 12}-{value % 12 + 1:02d}")  # обратно в «ГГГГ-ММ»
    return months


def current_month():
    """Текущий месяц в формате ГГГГ-ММ."""
    return date.today().strftime("%Y-%m")


def today_text():
    """Сегодняшняя дата в формате ДД.ММ.ГГГГ."""
    return date.today().strftime("%d.%m.%Y")


def month_start_text():
    """Первое число текущего месяца в формате ДД.ММ.ГГГГ."""
    return date.today().replace(day=1).strftime("%d.%m.%Y")


def now_text():
    """Текущие дата и время в формате базы ГГГГ-ММ-ДД ЧЧ:ММ."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
