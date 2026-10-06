"""Экраны редактирования данных (кадры 21 и 22 макета Figma)."""

from services import auth, hoa
from services.errors import AppError
from ui import dialogs, kit
from ui.auth_screens import brand_header


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

        board.label(77, 68, 807, "Редактирование данных ТСЖ", "Bold", 32, align="left")
        board.label(
            77,
            111,
            807,
            "Измените данные председателя и данные ТСЖ.",
            "ExtraLight",
            20,
            color=kit.MUTED,
            align="left",
        )
        board.shape(77, 166, 807, 134, 15, kit.PANEL_BLUE)
        board.shape(77, 314, 807, 186, 15, kit.PANEL_BLUE)
        board.shape(77, 514, 807, 307, 15, kit.PANEL_BLUE)
        board.label(111, 176, 400, "Председатель", "Bold", 24, align="left")
        board.label(111, 521, 400, "Данные ТСЖ", "Bold", 24, align="left")

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, "ФИО", 111, 248, 355, text=user["full_name"]),
            "phone": add(board, "Телефон", 494, 248, 355, text=user["phone"], max_length=20),
            "hoa_name": add(board, "Наименование ТСЖ", 111, 593, 738, text=info["name"]),
            "inn": add(board, "ИНН", 111, 677, 355, text=info["inn"]),
            "rate": add(
                board, "Тариф за 1 м2, руб.", 494, 677, 355, text=dialogs.comma(info["rate_per_m2"])
            ),
            "address": add(board, "Адрес дома", 111, 761, 738, text=info["address"]),
        }
        login = add(board, "Электронная почта (не изменяется)", 111, 358, 738, text=user["login"])
        login.set_readonly(True)
        self.password = add(board, "Пароль", 111, 442, 738, text=app.session_password)

        kit.Button(board, 605, 850, 119, 35, "Отмена", self.cancel, "plain")
        kit.Button(board, 742, 850, 142, 35, "Сохранить", self.save)
        self.fields["full_name"].focus()

    def cancel(self):
        """Возвращает в главное окно без сохранения."""
        self.app.show_main(self.user, self.tab)

    def save(self):
        """Сохраняет данные председателя и ТСЖ."""
        data = {key: field.get() for key, field in self.fields.items()}
        new_password = self.password.get()
        if new_password == self.app.session_password:
            new_password = None
        try:
            auth.update_chairman(self.user["users_id"], data, new_password)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        if new_password is not None:
            self.app.session_password = new_password
        dialogs.show_info(self.board, "Данные сохранены.")
        self.app.show_main(auth.get_user(self.user["users_id"]), self.tab)


class ResidentEditScreen:
    """Экран «Данные жильца»: ФИО, телефон и пароль можно менять, почту - нельзя."""

    size = (521, 665)
    title = "Редактирование данных жильца"

    def __init__(self, app, board, user):
        self.app = app
        self.board = board
        self.user = user

        brand_header(
            board,
            "Данные жильца",
            "Измените ФИО, телефон или пароль. Электронная почта не меняется.",
        )
        board.shape(38, 222, 445, 364, 22, kit.PANEL_BLUE)

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, "ФИО", 83, 270, 355, text=user["full_name"]),
            "phone": add(board, "Телефон", 83, 354, 355, text=user["phone"], max_length=20),
        }
        login = add(board, "Электронная почта (не изменяется)", 83, 438, 355, text=user["login"])
        login.set_readonly(True)
        self.password = add(board, "Пароль", 83, 522, 355, text=app.session_password)

        kit.Button(board, 127, 612, 119, 35, "Отмена", self.cancel, "plain")
        kit.Button(board, 260, 612, 133, 35, "Сохранить", self.save)
        self.fields["full_name"].focus()

    def cancel(self):
        """Возвращает в кабинет без сохранения."""
        self.app.show_main(self.user)

    def save(self):
        """Сохраняет ФИО и телефон."""
        new_password = self.password.get()
        if new_password == self.app.session_password:
            new_password = None
        try:
            auth.update_profile(
                self.user["users_id"],
                self.fields["full_name"].get(),
                self.fields["phone"].get(),
                new_password,
            )
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        if new_password is not None:
            self.app.session_password = new_password
        dialogs.show_info(self.board, "Данные сохранены.")
        self.app.show_main(auth.get_user(self.user["users_id"]))
