"""Экраны редактирования данных (кадры 21 и 22 макета Figma)."""

from services import auth, hoa
from services.errors import AppError
from ui import dialogs, kit
from ui.auth_screens import hoa_subtitle


class ChairmanEditScreen:
    """Экран «Редактирование данных ТСЖ» (кадр 21, размер 952x919). Открывается шестерёнкой."""

    size = (952, 919)
    title = "Редактирование данных ТСЖ"

    def __init__(self, app, board, user, tab=0):
        """tab - вкладка главного окна, на которую вернёмся после сохранения или отмены."""
        self.app = app
        self.board = board
        self.user = user
        self.tab = tab
        info = hoa.get_hoa()

        # заголовок и подсказка
        board.label(77, 68, 807, "Редактирование данных ТСЖ", "Bold", 32, align="left")
        board.label(
            77,
            111,
            807,
            "Измените данные председателя и данные ТСЖ.",
            "ExtraLight",
            20,
            align="left",
        )
        # три синие панели: председатель, логин с паролем, данные ТСЖ
        board.shape(77, 166, 807, 134, 15, kit.PANEL_BLUE)
        board.shape(77, 314, 807, 186, 15, kit.PANEL_BLUE)
        board.shape(77, 514, 807, 307, 15, kit.PANEL_BLUE)
        board.label(111, 176, 400, "Председатель", "Bold", 24, align="left")
        board.label(111, 521, 400, "Данные ТСЖ", "Bold", 24, align="left")

        add = dialogs.add_field  # короткое имя для функции «подпись + поле»
        self.fields = {
            "full_name": add(board, 0, 0, 0, "ФИО", 111, 248, 355, text=user["full_name"]),
            "phone": add(
                board, 0, 0, 0, "Телефон", 494, 248, 355, text=user["phone"], max_length=20
            ),
            "hoa_name": add(board, 0, 0, 0, "Наименование ТСЖ", 111, 593, 738, text=info["name"]),
            "inn": add(board, 0, 0, 0, "ИНН", 111, 677, 355, text=info["inn"]),
            "rate": add(
                board,
                0,
                0,
                0,
                "Тариф за 1 м2, руб.",
                494,
                677,
                355,
                text=dialogs.comma(info["rate_per_m2"]),
            ),
            "address": add(board, 0, 0, 0, "Адрес дома", 111, 761, 738, text=info["address"]),
        }
        # логин и пароль менять нельзя: поля только для чтения (пароль - тот, что введён при входе)
        login = add(
            board, 0, 0, 0, "Электронная почта (не изменяется)", 111, 358, 738, text=user["login"]
        )
        login.set_readonly(True)
        password = add(
            board, 0, 0, 0, "Пароль (не изменяется)", 111, 442, 738, text=app.session_password
        )
        password.set_readonly(True)

        # «Отмена» возвращает в главное окно, «Сохранить» записывает изменения
        kit.Button(board, 605, 850, 119, 35, "Отмена", self.cancel, "plain")
        kit.Button(board, 742, 850, 142, 35, "Сохранить", self.save)
        self.fields["full_name"].focus()

    def cancel(self):
        """Возвращает в главное окно без сохранения."""
        self.app.show_main(self.user, self.tab)

    def save(self):
        """Сохраняет данные председателя и ТСЖ."""
        data = {key: field.get() for key, field in self.fields.items()}
        try:
            auth.update_chairman(self.user["users_id"], data)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        dialogs.show_info(self.board, "Данные сохранены.")
        # в главное окно возвращаемся с обновлёнными данными (в шапке новое ФИО)
        self.app.show_main(auth.get_user(self.user["users_id"]), self.tab)


class ResidentEditScreen:
    """Экран «Редактирование данных жильца» (кадр 22, размер 521x640)."""

    size = (521, 640)
    title = "Редактирование данных жильца"

    def __init__(self, app, board, user):
        self.app = app
        self.board = board
        self.user = user

        # заголовок в две строки и подсказка
        board.label(0, 15, 521, "Редактирование\nданных жильца", "Bold", 32)
        board.label(40, 111, 441, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, 0, 0, 0, "ФИО", 83, 225, 355, text=user["full_name"]),
            "phone": add(
                board, 0, 0, 0, "Телефон", 83, 309, 355, text=user["phone"], max_length=20
            ),
        }
        # логин и пароль менять нельзя
        login = add(
            board, 0, 0, 0, "Электронная почта (не изменяется)", 83, 393, 355, text=user["login"]
        )
        login.set_readonly(True)
        password = add(
            board, 0, 0, 0, "Пароль (не изменяется)", 83, 477, 355, text=app.session_password
        )
        password.set_readonly(True)

        kit.Button(board, 127, 565, 119, 35, "Отмена", self.cancel, "plain")
        kit.Button(board, 260, 565, 133, 35, "Сохранить", self.save)
        self.fields["full_name"].focus()

    def cancel(self):
        """Возвращает в кабинет без сохранения."""
        self.app.show_main(self.user)

    def save(self):
        """Сохраняет ФИО и телефон."""
        try:
            auth.update_profile(
                self.user["users_id"], self.fields["full_name"].get(), self.fields["phone"].get()
            )
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        dialogs.show_info(self.board, "Данные сохранены.")
        self.app.show_main(auth.get_user(self.user["users_id"]))
