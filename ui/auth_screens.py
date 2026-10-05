"""Экраны входа и регистрации (кадры 00, 02, 03 макета Figma)."""

from services import auth, hoa

from services.errors import AppError

from ui import dialogs, kit


def hoa_subtitle():
    """Строка «название ТСЖ, адрес» для заголовков экранов."""
    info = hoa.get_hoa()
    if info is None:
        return ""
    return f"{info['name']}, {info['address']}"


class LoginScreen:
    """Экран «Вход в систему» (кадр 00, размер 521x572)."""

    size = (521, 572)
    title = "Вход в систему"

    def __init__(self, app, board, message="", kind="error"):
        """
        Args:
            app: главный объект программы.
            board: холст размером с кадр.
            message (str): красная плашка над кнопкой «Войти».
        """
        self.app = app
        self.board = board
        board.label(32, 83, 335, "Вход в систему", "Bold", 32)
        board.label(49, 126, 309, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        board.label(53, 215, 111, "Логин", "Regular", 16)
        self.login = kit.EntryBox(board, 81, 244, 355, 42)
        board.label(53, 315, 123, "Пароль", "Regular", 16)
        self.password = kit.EntryBox(board, 81, 344, 355, 42, show="*")
        self.login.on_enter(self.try_login)
        self.password.on_enter(self.try_login)

        board.set_layer("message")
        if message:
            kit.note(board, 81, 394, 359, 51, message, kind)
        board.set_layer("base")

        kit.Button(board, 164, 495, 216, 35, "Войти", self.try_login)
        kit.link(board, 168, 538, 216, "зарегистрироваться", app.show_resident_register)
        self.login.focus()

    def show_message(self, text):
        """Показывает красную плашку с текстом ошибки."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 81, 394, 359, 51, text, "error")
        self.board.set_layer("base")

    def try_login(self):
        """Проверяет логин и пароль и открывает окно по роли."""
        try:
            user = auth.login_user(self.login.get(), self.password.get())
        except AppError as error:
            self.show_message(str(error))
            return
        self.app.show_main(user)


class ResidentRegisterScreen:
    """Экран «Регистрация жильца» (кадр 02, размер 521x909)."""

    size = (521, 909)
    title = "Регистрация жильца"

    def __init__(self, app, board):
        self.app = app
        self.board = board
        board.label(62, 68, 335, "Регистрация жильца", "Bold", 32)
        board.label(48, 111, 309, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        self.fields = {
            "full_name": dialogs.add_field(board, 62, 196, 111, "ФИО", 90, 225, 355),
            "phone": dialogs.add_field(board, 68, 276, 111, "Телефон", 90, 305, 355),
            "apartment_number": dialogs.add_field(board, 76, 359, 111, "Квартира", 90, 390, 355),
            "login": dialogs.add_field(board, 62, 441, 111, "Логин", 90, 470, 355),
            "password": dialogs.add_field(board, 62, 514, 137, "Пароль", 90, 543, 355, show="*"),
            "password2": dialogs.add_field(
                board, 68, 583, 182, "Повтор пароля", 96, 612, 355, show="*"
            ),
        }
        kit.note(
            board,
            96,
            668,
            359,
            51,
            "После регистрации аккаунт должен\nподтвердить председатель ТСЖ",
            "info",
        )
        kit.Button(board, 168, 750, 216, 35, "Зарегистрироваться", self.register)
        kit.link(board, 173, 799, 216, "войти", app.show_login)
        self.fields["full_name"].focus()

    def register(self):
        """Собирает данные формы и регистрирует жильца."""
        data = {key: field.get() for key, field in self.fields.items()}
        try:
            approved = auth.register_resident(data)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        if approved:
            self.app.show_login("Вы зарегистрированы как собственник. Войдите в систему.", "info")
        else:
            self.app.show_login("Аккаунт ожидает подтверждения председателем")


class ChairmanRegisterScreen:
    """Экран «Регистрация председателя ТСЖ» (кадр 03, размер 952x919)."""

    size = (952, 919)
    title = "Регистрация председателя ТСЖ"

    def __init__(self, app, board):
        self.app = app
        self.board = board
        board.label(52, 68, 525, "Регистрация председателя ТСЖ", "Bold", 32)
        board.label(
            52,
            111,
            713,
            "Данные ТСЖ ещё не заполнены. Укажите данные председателя дома.",
            "ExtraLight",
            20,
        )
        board.shape(77, 166, 807, 298, 15, kit.PANEL_BLUE)
        board.shape(76, 496, 807, 322, 15, kit.PANEL_BLUE)
        board.label(43, 176, 304, "Председатель", "Bold", 24)
        board.label(36, 503, 316, "Данные ТСЖ", "Bold", 24)

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, 77, 219, 111, "ФИО", 105, 248, 355),
            "phone": add(board, 460, 219, 136, "Телефон", 488, 248, 355),
            "login": add(board, 77, 300, 126, "Логин", 105, 329, 738),
            "password": add(board, 77, 376, 136, "Пароль", 105, 405, 355, show="*"),
            "password2": add(board, 459, 376, 209, "Повторите пароль", 487, 405, 355, show="*"),
            "hoa_name": add(board, 76, 546, 224, "Наименование ТСЖ", 104, 575, 738),
            "inn": add(board, 76, 621, 111, "ИНН", 104, 650, 355),
            "rate": add(board, 459, 621, 179, "Тариф за 1 м2, руб.", 487, 650, 355),
            "address": add(board, 76, 696, 158, "Адрес дома", 104, 725, 738),
        }
        kit.Button(board, 539, 850, 119, 35, "Отмена", app.root.destroy, "plain")
        kit.Button(board, 668, 850, 216, 35, "Зарегистрироваться", self.register)
        self.fields["full_name"].focus()

    def register(self):
        """Собирает данные формы и регистрирует председателя."""
        data = {key: field.get() for key, field in self.fields.items()}
        try:
            auth.register_chairman(data)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        dialogs.show_info(self.board, "Председатель зарегистрирован. Войдите в систему.")
        self.app.show_login()
