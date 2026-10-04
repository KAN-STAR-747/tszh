"""Всплывающие окна: сообщения и формы (кадры M1-M6 макета Figma)."""

# tk.Toplevel - это дополнительное окно поверх главного
import tkinter as tk

# сервисы, которые вызывают окна
from services import apartments, dates, finance, requests_service
from services import validation as check
from services.errors import AppError

# элементы интерфейса
from ui import kit


# Modal - основа всех всплывающих окон: холст, центрирование и блокировка главного окна
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
        # создаём пустое окно (вызов конструктора tk.Toplevel)
        super().__init__(parent)
        # заголовок окна
        self.title(title)
        self.configure(bg=kit.WHITE)
        # размер менять нельзя
        self.resizable(False, False)
        # холст размером с кадр макета
        self.board = kit.Board(self, width, height)
        self.board.pack()
        # главное окно программы
        main = parent.winfo_toplevel()
        # окно всегда поверх главного
        self.transient(main)
        # даём Tkinter посчитать размеры
        self.update_idletasks()
        # размер в пикселях экрана
        w, h = kit.S(width), kit.S(height)
        # считаем центр главного окна
        x = main.winfo_rootx() + (main.winfo_width() - w) // 2
        y = main.winfo_rooty() + (main.winfo_height() - h) // 3
        # следим, чтобы окно не вышло за край экрана
        x = min(max(x, 0), self.winfo_screenwidth() - w - 20)
        y = min(max(y, 0), self.winfo_screenheight() - h - 90)
        # ставим окно на место
        self.geometry(f"+{x}+{y}")
        # пока окно открыто, главное окно не реагирует на клики
        self.grab_set()
        # Esc закрывает окно
        self.bind("<Escape>", lambda event: self.destroy())


# Универсальное окно сообщения: одна функция для ошибок, информации и вопросов
def _message(parent, title, text, icon, buttons):
    """Окно сообщения в стиле макета (кадры M4, M5, M6).

    Args:
        buttons (list[tuple]): (надпись, результат, главная ли кнопка).

    Returns:
        Результат нажатой кнопки или None, если окно закрыли крестиком.
    """
    # размер кадра M4-M6 из Figma
    dialog = Modal(parent, title, 521, 307)
    board = dialog.board
    # сюда запишется ответ пользователя
    dialog.result = None
    board.label(16, 13, 269, title, "Medium", 16, align="left")
    # линия под заголовком
    board.hline(0, 52, 521)
    # значок: ! ошибка, i информация, ? вопрос
    board.label(16, 74, 30, icon, "Regular", 36)
    board.label(100, 73, 353, text, "Regular", 16, wrap=True)

    # вызывается при нажатии кнопки: запоминает ответ и закрывает окно
    def finish(result):
        dialog.result = result
        dialog.destroy()

    # положения кнопок: одна кнопка или две
    positions = {1: [(368, 131)], 2: [(230, 119), (368, 131)]}[len(buttons)]
    # рисуем кнопки по очереди
    for (caption, result, primary), (x, w) in zip(buttons, positions):
        kit.Button(
            board,
            x,
            249,
            w,
            35,
            caption,
            # lambda - маленькая функция; r=result запоминает ответ именно этой кнопки
            lambda r=result: finish(r),
            "primary" if primary else "plain",
        )
    # ждём, пока окно закроют
    parent.wait_window(dialog)
    # возвращаем ответ
    return dialog.result


# Три короткие обёртки над _message: ошибка, информация, вопрос Да/Нет
def show_error(parent, text, title="Ошибка"):
    """Окно с сообщением об ошибке и кнопкой OK."""
    _message(parent, title, text, "!", [("OK", True, True)])


def show_info(parent, text, title="Сообщение"):
    """Информационное окно с кнопкой OK."""
    _message(parent, title, text, "i", [("OK", True, True)])


def ask_yes_no(parent, text, title="Подтверждение"):
    """Окно с вопросом и кнопками «Нет» / «Да». Возвращает True при «Да»."""
    return bool(_message(parent, title, text, "?", [("Нет", False, False), ("Да", True, True)]))


# Правильная форма слова: 1 начисление, 2 начисления, 5 начислений
def charges_word(count):
    """Слово «начисление» в нужной форме для числа count."""
    return dates.plural(count, "начисление", "начисления", "начислений")


# Копейки в текст с запятой, как в макете: 150000 -> «1500,00»
def comma(kopecks):
    """Сумма в копейках -> текст с запятой, как в макете («1500,00»)."""
    return check.kopecks_to_text(kopecks).replace(".", ",")


# Подпись и поле ввода под ней - повторяется во всех формах, поэтому вынесено
def add_field(board, label_x, label_y, label_w, caption, x, y, w, show="", text=""):
    """Подпись (шрифт 16) и поле ввода под ней - как в макете."""
    board.label(label_x, label_y, label_w, caption, "Regular", 16)
    return kit.EntryBox(board, x, y, w, 42, show=show, text=text)


# Окно добавления и изменения квартиры (кадр M1)
class ApartmentDialog(Modal):
    """Окно «Новая квартира» / «Изменение квартиры» (кадр M1)."""

    def __init__(self, parent, on_saved, apartment_id=None):
        """
        Args:
            parent: вкладка, из которой открыто окно.
            on_saved: функция, вызываемая после сохранения.
            apartment_id (int): id квартиры при изменении, иначе None.
        """
        # заголовок зависит от того, добавляем или изменяем
        title = "Новая квартира" if apartment_id is None else "Изменение квартиры"
        super().__init__(parent, title, 521, 731)
        # on_saved - функция, которую вызовем после сохранения (обновит таблицу)
        self.on_saved = on_saved
        self.apartment_id = apartment_id
        board = self.board

        board.label(3, 42, 335, title, "Bold", 32)
        # поля формы
        self.number = add_field(board, 19, 113, 203, "Номер квартиры", 51, 142, 403)
        self.area = add_field(board, 19, 197, 173, "Площадь, м2", 51, 226, 403)
        self.owner = add_field(board, 19, 281, 226, "ФИО собственника", 51, 310, 403)
        self.phone = add_field(board, 19, 365, 258, "Телефон собственника", 51, 394, 403)
        # галочка «член ТСЖ»
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

        # при изменении заполняем поля текущими данными
        if apartment_id is not None:
            row = apartments.get_apartment(apartment_id)
            self.number.set(str(row["number"]))
            self.area.set(f"{row['area']:g}")
            self.owner.set(row["owner_name"])
            self.phone.set(row["owner_phone"])
            self.member.set(bool(row["is_member"]))
        # курсор в первое поле
        self.number.focus()

    def save(self):
        """Сохраняет квартиру и закрывает окно."""
        # собираем данные формы
        data = {
            "number": self.number.get(),
            "area": self.area.get(),
            "owner_name": self.owner.get(),
            "owner_phone": self.phone.get(),
            "is_member": self.member.get(),
        }
        try:
            # сервис проверит данные и запишет их в базу
            apartments.save_apartment(data, self.apartment_id)
        except AppError as error:
            show_error(self, str(error))
            return
        # сообщаем вкладке, что данные изменились
        self.on_saved()
        self.destroy()


# Окно создания заявки председателем (кадр M2)
class RequestDialog(Modal):
    """Окно «Новая заявка», которое открывает председатель (кадр M2)."""

    # пункт списка для заявок без квартиры
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
        # список квартир для выпадающего списка
        self.apartment_rows = list(apartments.get_apartments())
        # строки списка: сначала общедомовое имущество, потом «Кв. N - ФИО»
        names = [self.COMMON_PROPERTY] + [
            f"Кв. {row['number']} - {row['owner_name']}" for row in self.apartment_rows
        ]
        self.apartment_box = kit.DropBox(board, 51, 142, 403, 42, names)

        board.label(19, 197, 173, "Источник", "Regular", 16)
        # переключатель источника: Звонок или Приложение
        self.source = kit.RadioGroup(
            board, [("Звонок", "Звонок", 73, 246), ("Приложение", "Приложение", 204, 246)]
        )
        self.title_entry = add_field(board, 19, 281, 123, "Тема", 51, 310, 403)
        board.label(19, 365, 158, "Описание", "Regular", 16)
        # поле описания
        self.description = kit.TextBox(board, 51, 394, 403, 42)
        self.executor = add_field(
            board, 19, 447, 358, "Исполнитель (можно указать позже)", 51, 476, 403
        )
        board.label(-99, 525, 713, "Заявка будет создана со статусом «Новая»", "ExtraLight", 20)
        kit.Button(board, 185, 659, 119, 35, "Отмена", self.destroy, "plain")
        kit.Button(board, 323, 659, 152, 35, "Создать заявку", self.save)
        self.title_entry.focus()

    def save(self):
        """Создаёт заявку и закрывает окно."""
        # номер выбранного пункта списка
        index = self.apartment_box.index
        # 0 - общедомовое имущество, квартиры нет
        apartment_id = None
        if index > 0:
            # иначе берём квартиру из списка (минус 1 из-за первого пункта)
            apartment_id = self.apartment_rows[index - 1]["apartment_id"]
        try:
            # создаём заявку
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


# Окно целевого сбора (кадр M3)
class TargetChargeDialog(Modal):
    """Окно «Новый целевой сбор» (кадр M3)."""

    def __init__(self, parent, on_saved):
        super().__init__(parent, "Новый целевой сбор", 521, 562)
        self.on_saved = on_saved
        board = self.board

        board.label(3, 42, 418, "Новый целевой сбор", "Bold", 32)
        self.purpose = add_field(board, 19, 113, 166, "Назначение", 51, 142, 403)
        self.amount = add_field(board, 19, 197, 258, "Сумма с квартиры, руб.", 51, 226, 403)
        # при каждом вводе цифры пересчитываем подсказку
        self.amount.on_change(self.update_preview)
        board.label(19, 281, 129, "Месяц", "Regular", 16)
        # список месяцев для выбора
        self.months = dates.get_month_list()
        # выпадающий список месяцев; по умолчанию текущий
        self.month_box = kit.DropBox(
            board,
            51,
            310,
            403,
            42,
            [dates.month_to_text(m) for m in self.months],
            index=self.months.index(dates.current_month()),
        )
        # плашка с итогом: сколько начислений и на какую сумму
        self.preview = kit.note(board, 51, 384, 404, 62, "", "info")
        self.update_preview()
        kit.Button(board, 158, 488, 119, 35, "Отмена", self.destroy, "plain")
        kit.Button(board, 292, 488, 163, 35, "Начислить сбор", self.save)
        self.purpose.focus()

    def update_preview(self):
        """Обновляет подсказку «Будет создано N начислений...»."""
        # сколько квартир получат начисление
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
        # меняем текст плашки
        self.board.itemconfigure(self.preview, text=text)

    def save(self):
        """Создаёт начисления и закрывает окно."""
        try:
            # создаём начисления для всех квартир
            finance.charge_target(
                self.purpose.get(), self.amount.get(), self.months[self.month_box.index]
            )
        except AppError as error:
            show_error(self, str(error))
            return
        self.on_saved()
        self.destroy()
