"""Всплывающие окна: сообщения и формы (кадры M1-M6 макета Figma)."""

import tkinter as tk

from services import apartments, auth, dates, finance, requests_service
from services import validation as check
from services.errors import AppError

from ui import kit


class Modal(tk.Toplevel):
    """Основа всплывающего окна: холст размером с кадр макета,
    расположение по центру главного окна, блокировка остальных окон."""

    def __init__(self, parent, title, width, height):
        """
        Args:
            parent: виджет, из которого открыто окно.
            title (str): заголовок окна.
            width (int): ширина кадра макета.
            height (int): высота кадра макета.
        """
        super().__init__(parent)
        self.title(title)
        self.configure(bg=kit.WHITE)
        self.resizable(False, False)
        self.board = kit.Board(self, width, height)
        self.board.pack()
        main = parent.winfo_toplevel()
        self.transient(main)
        self.update_idletasks()
        w, h = kit.S(width), kit.S(height)
        x = main.winfo_rootx() + (main.winfo_width() - w) // 2
        y = main.winfo_rooty() + (main.winfo_height() - h) // 3
        x = min(max(x, 0), self.winfo_screenwidth() - w - 20)
        y = min(max(y, 0), self.winfo_screenheight() - h - 90)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.bind("<Escape>", lambda event: self.destroy())


def _message(parent, title, text, icon, buttons):
    """Окно сообщения в стиле макета (кадры M4, M5, M6).

    Args:
        buttons (list[tuple]): (надпись, результат, главная ли кнопка).

    Returns:
        Результат нажатой кнопки или None, если окно закрыли крестиком.
    """
    dialog = Modal(parent, title, 521, 307)
    board = dialog.board
    dialog.result = None
    board.label(16, 13, 269, title, "Medium", 16, align="left")
    board.hline(0, 52, 521)
    board.label(16, 74, 30, icon, "Regular", 36)
    board.label(100, 73, 353, text, "Regular", 16, wrap=True)

    def finish(result):
        dialog.result = result
        dialog.destroy()

    positions = {1: [(368, 131)], 2: [(230, 119), (368, 131)]}[len(buttons)]

    for (caption, result, primary), (x, w) in zip(buttons, positions):
        kit.Button(
            board,
            x,
            249,
            w,
            35,
            caption,
            lambda r=result: finish(r),
            "primary" if primary else "plain",
        )

    parent.wait_window(dialog)

    return dialog.result


def show_error(parent, text, title="Ошибка"):
    """Окно с сообщением об ошибке и кнопкой OK."""
    _message(parent, title, text, "!", [("OK", True, True)])


def show_info(parent, text, title="Сообщение"):
    """Информационное окно с кнопкой OK."""
    _message(parent, title, text, "i", [("OK", True, True)])


def ask_yes_no(parent, text, title="Подтверждение"):
    """Окно с вопросом и кнопками «Нет» / «Да». Возвращает True при «Да»."""
    return bool(_message(parent, title, text, "?", [("Нет", False, False), ("Да", True, True)]))


def charges_word(count):
    """Слово «начисление» в нужной форме для числа count."""
    return dates.plural(count, "начисление", "начисления", "начислений")


def comma(kopecks):
    """Сумма в копейках -> текст с запятой, как в макете («1500,00»)."""
    return check.kopecks_to_text(kopecks).replace(".", ",")


def add_field(
    board, label_x, label_y, label_w, caption, x, y, w, show="", text="", max_length=None
):
    """Подпись (шрифт 16) и поле ввода под ней - как в макете. max_length - предел длины."""
    board.label(label_x, label_y, label_w, caption, "Regular", 16)
    return kit.EntryBox(board, x, y, w, 42, show=show, text=text, max_length=max_length)


class ApartmentDialog(Modal):
    """Окно «Новая квартира» / «Изменение квартиры» (кадр M1)."""

    def __init__(self, parent, on_saved, apartment_id=None):
        """
        Args:
            parent: вкладка, из которой открыто окно.
            on_saved: функция, вызываемая после сохранения.
            apartment_id (int): id квартиры при изменении, иначе None.
        """
        title = "Новая квартира" if apartment_id is None else "Изменение квартиры"
        super().__init__(parent, title, 521, 731)
        self.on_saved = on_saved
        self.apartment_id = apartment_id
        board = self.board

        board.label(3, 42, 335, title, "Bold", 32)
        self.number = add_field(board, 19, 113, 203, "Номер квартиры", 51, 142, 403)
        self.area = add_field(board, 19, 197, 173, "Площадь, м2", 51, 226, 403)
        self.owner = add_field(board, 19, 281, 226, "ФИО собственника", 51, 310, 403)
        self.phone = add_field(board, 19, 365, 258, "Телефон собственника", 51, 394, 403)
        self.member = kit.CheckBox(board, 62, 448)
        board.label(65, 449, 258, "Собственник - член ТСЖ", "Regular", 16)
        kit.note(
            board,
            50,
            500,
            404,
            62,
            "Номер квартиры должен быть уникальным.\nПлощадь - положительное число.",
            "info",
        )
        kit.Button(board, 185, 659, 119, 35, "Отмена", self.destroy, "plain")
        kit.Button(board, 323, 659, 131, 35, "Сохранить", self.save)

        if apartment_id is not None:
            row = apartments.get_apartment(apartment_id)
            self.number.set(str(row["number"]))
            self.area.set(f"{row['area']:g}")
            self.owner.set(row["owner_name"])
            self.phone.set(row["owner_phone"])
            self.member.set(bool(row["is_member"]))
        self.number.focus()

    def save(self):
        """Сохраняет квартиру и закрывает окно."""
        data = {
            "number": self.number.get(),
            "area": self.area.get(),
            "owner_name": self.owner.get(),
            "owner_phone": self.phone.get(),
            "is_member": self.member.get(),
        }
        try:
            apartments.save_apartment(data, self.apartment_id)
        except AppError as error:
            show_error(self, str(error))
            return
        self.on_saved()
        self.destroy()


class RequestDialog(Modal):
    """Окно «Новая заявка», которое открывает председатель (кадр M2)."""

    COMMON_PROPERTY = "-Общедомовое имущество-"

    def __init__(self, parent, user, on_saved):
        """
        Args:
            parent: вкладка, из которой открыто окно.
            user (dict): председатель, создающий заявку.
            on_saved: функция, вызываемая после сохранения.
        """
        super().__init__(parent, "Новая заявка", 521, 731)
        self.user = user
        self.on_saved = on_saved
        board = self.board

        board.label(3, 42, 335, "Новая заявка", "Bold", 32)
        board.label(-9, 110, 203, "Квартира", "Regular", 16)
        self.apartment_rows = list(apartments.get_apartments())

        names = [self.COMMON_PROPERTY] + [
            f"Кв. {row['number']} - {row['owner_name']}" for row in self.apartment_rows
        ]
        self.apartment_box = kit.DropBox(board, 51, 142, 403, 42, names)

        board.label(19, 197, 173, "Источник", "Regular", 16)

        self.source = kit.RadioGroup(
            board, [("Звонок", "Звонок", 73, 246), ("Приложение", "Приложение", 204, 246)]
        )

        self.title_entry = add_field(board, 19, 281, 123, "Тема", 51, 310, 403, max_length=50)
        board.label(19, 365, 158, "Описание", "Regular", 16)
        self.description = kit.TextBox(board, 51, 394, 403, 42, max_length=250)
        self.executor = add_field(
            board, 19, 447, 358, "Исполнитель (можно указать позже)", 51, 476, 403, max_length=25
        )
        board.label(-99, 525, 713, "Заявка будет создана со статусом «Новая»", "ExtraLight", 20)
        kit.Button(board, 185, 659, 119, 35, "Отмена", self.destroy, "plain")
        kit.Button(board, 323, 659, 152, 35, "Создать заявку", self.save)
        self.title_entry.focus()

    def save(self):
        """Создаёт заявку и закрывает окно."""

        index = self.apartment_box.index

        apartment_id = None
        if index > 0:

            apartment_id = self.apartment_rows[index - 1]["apartment_id"]
        try:

            requests_service.create_request(
                self.user["users_id"],
                apartment_id,
                self.title_entry.get(),
                self.description.get(),
                self.source.get(),
                self.executor.get(),
            )
        except AppError as error:
            show_error(self, str(error))
            return
        self.on_saved()
        self.destroy()


class TargetChargeDialog(Modal):
    """Окно «Новый целевой сбор» (кадр M3)."""

    def __init__(self, parent, on_saved):
        super().__init__(parent, "Новый целевой сбор", 521, 562)
        self.on_saved = on_saved
        board = self.board

        board.label(3, 42, 418, "Новый целевой сбор", "Bold", 32)
        self.purpose = add_field(board, 19, 113, 166, "Назначение", 51, 142, 403, max_length=50)
        self.amount = add_field(board, 19, 197, 258, "Сумма с квартиры, руб.", 51, 226, 403)
        self.amount.on_change(self.update_preview)
        board.label(19, 281, 129, "Месяц", "Regular", 16)
        self.months = dates.get_month_list()
        self.month_box = kit.DropBox(
            board,
            51,
            310,
            403,
            42,
            [dates.month_to_text(m) for m in self.months],
            index=self.months.index(dates.current_month()),
        )
        self.preview = kit.note(board, 51, 384, 404, 62, "", "info")
        self.update_preview()
        kit.Button(board, 158, 488, 119, 35, "Отмена", self.destroy, "plain")
        kit.Button(board, 292, 488, 163, 35, "Начислить сбор", self.save)
        self.purpose.focus()

    def update_preview(self):
        """Обновляет подсказку «Будет создано N начислений...»."""
        count = len(finance.get_apartments_for_charge())
        try:
            amount = check.rubles_to_kopecks(self.amount.get(), "Сумма")
        except AppError:
            text = f"Будет создано {count} {charges_word(count)}."
        else:
            text = (
                f"Будет создано {count} {charges_word(count)} по "
                f"{comma(amount)} руб.\n"
                f"Итого по дому: {comma(amount * count)} руб."
            )
        self.board.itemconfigure(self.preview, text=text)

    def save(self):
        """Создаёт начисления и закрывает окно."""
        try:
            finance.charge_target(
                self.purpose.get(), self.amount.get(), self.months[self.month_box.index]
            )
        except AppError as error:
            show_error(self, str(error))
            return
        self.on_saved()
        self.destroy()


class ListDialog(Modal):
    """Окно-список. columns - столбцы таблицы, rows - строки (ключ, значения, цвет)."""

    def __init__(self, parent, title, size, title_box, columns, rows, back_x):
        """
        Args:
            parent: окно, из которого открыт список.
            title (str): заголовок окна и надпись в нём.
            size (tuple): ширина и высота кадра макета.
            title_box (tuple): положение рамки заголовка (x, ширина), как в Figma.
            columns (list): описание столбцов таблицы.
            rows (list): строки таблицы.
            back_x (int): положение кнопки «Назад» по горизонтали.
        """
        super().__init__(parent, title, *size)
        board = self.board
        board.label(title_box[0], 30, title_box[1], title, "Bold", 32)
        table = kit.Table(
            board, 32, 103, size[0] - 50, 354, columns, header_line=36, row_height=44, header_top=3
        )
        table.set_rows(rows)
        kit.Button(board, back_x, size[1] - 94, 119, 35, "Назад", self.destroy, "plain")


def short_date(stamp):
    return f"{stamp[8:10]}.{stamp[5:7]}.{stamp[0:4]}"


def _column(title, cx, size=16, width=150):
    return {"title": title, "cx": cx, "style": "Light", "size": size, "width": width}


def show_target_charges(parent):
    """Открывает список всех целевых сборов с числом квартир, которые их оплатили."""
    columns = [
        _column("№", 59, 24, 70),
        _column("Назначение", 199.5, 16, 150),
        _column("Месяц", 348, 16, 130),
        _column("Сумма", 473, 16, 110),
        _column("Оплатило квартир", 663, 16, 200),
    ]
    rows = []
    for number, item in enumerate(finance.get_target_charges(), start=1):
        values = [
            number,
            item["purpose"],
            dates.month_to_text(item["period"]),
            check.kopecks_to_text(item["amount"]),
            item["paid"],
        ]
        rows.append((number, values, None))
    ListDialog(parent, "Все целевые сборы", (878, 593), (-77, 525), columns, rows, 742)


def show_payments(parent):
    """Открывает список всех оплат по всем квартирам."""
    columns = [
        _column("№", 59, 24, 70),
        _column("Квартира", 199.5, 16, 150),
        _column("Сумма", 348, 16, 130),
        _column("Дата", 473, 16, 110),
        _column("Комментарий", 663, 16, 200),
    ]
    rows = []
    for number, item in enumerate(finance.get_all_payments(), start=1):
        values = [
            number,
            item["number"],
            check.kopecks_to_text(item["amount"]),
            short_date(item["paid_at"]),
            item["comment"] or "",
        ]
        rows.append((number, values, None))
    ListDialog(parent, "Оплаты", (878, 593), (-77, 367), columns, rows, 742)


def show_residents(parent):
    """Открывает список подтверждённых жильцов с данными их квартир."""
    columns = [
        _column("Квартира", 65, 24, 90),
        _column("ФИО", 224, 16, 230),
        _column("Член ТСЖ", 421, 16, 100),
        _column("Площадь квартиры", 630, 16, 250),
    ]
    rows = []
    for index, item in enumerate(auth.get_residents()):
        values = [
            item["number"],
            item["full_name"],
            "Да" if item["is_member"] else "Нет",
            f"{item['area']:g}",
        ]
        rows.append((index, values, None))
    ListDialog(parent, "Жильцы", (854, 593), (-77, 367), columns, rows, 597)
