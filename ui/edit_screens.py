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
        board.label(39, 64, 525, "Редактирование данных ТСЖ", "Bold", 32)
        board.label(52, 111, 713, "Измените данные председателя и данные ТСЖ.", "ExtraLight", 20)
        # три синие панели: председатель, логин с паролем, данные ТСЖ
        board.shape(77, 166, 807, 134, 15, kit.PANEL_BLUE)
        board.shape(76, 320, 807, 157, 15, kit.PANEL_BLUE)
        board.shape(76, 496, 807, 322, 15, kit.PANEL_BLUE)
        board.label(43, 176, 304, "Председатель", "Bold", 24)
        board.label(36, 503, 316, "Данные ТСЖ", "Bold", 24)

        add = dialogs.add_field  # короткое имя для функции «подпись + поле»
        self.fields = {
            "full_name": add(board, 77, 219, 111, "ФИО", 105, 248, 355, text=user["full_name"]),
            "phone": add(
                board, 460, 219, 136, "Телефон", 488, 248, 355, text=user["phone"], max_length=20
            ),
            "hoa_name": add(
                board, 76, 546, 224, "Наименование ТСЖ", 104, 575, 738, text=info["name"]
            ),
            "inn": add(board, 76, 621, 111, "ИНН", 104, 650, 355, text=info["inn"]),
            "rate": add(
                board,
                459,
                621,
                179,
                "Тариф за 1 м2, руб.",
                487,
                650,
                355,
                text=dialogs.comma(info["rate_per_m2"]),
            ),
            "address": add(board, 76, 696, 158, "Адрес дома", 104, 725, 738, text=info["address"]),
        }
        # логин и пароль менять нельзя: поля только для чтения (пароль - тот, что введён при входе)
        login = add(board, 77, 318, 248, "Логин (не изменяется)", 105, 347, 738, text=user["login"])
        login.set_readonly(True)
        password = add(
            board, 77, 394, 256, "Пароль (не изменяется)", 105, 423, 738, text=app.session_password
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
        board.label(62, 15, 289, "Редактирование\nданных жильца", "Bold", 32)
        board.label(48, 111, 309, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, 62, 196, 111, "ФИО", 90, 225, 355, text=user["full_name"]),
            "phone": add(
                board, 68, 276, 111, "Телефон", 90, 305, 355, text=user["phone"], max_length=20
            ),
        }
        # логин и пароль менять нельзя
        login = add(board, 62, 356, 240, "Логин (не изменяется)", 90, 385, 355, text=user["login"])
        login.set_readonly(True)
        password = add(
            board, 62, 429, 254, "Пароль (не изменяется)", 90, 458, 355, text=app.session_password
        )
        password.set_readonly(True)

        kit.Button(board, 180, 542, 119, 35, "Отмена", self.cancel, "plain")
        kit.Button(board, 312, 542, 133, 35, "Сохранить", self.save)
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
