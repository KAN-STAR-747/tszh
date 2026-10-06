"""Экраны входа и регистрации (кадры 00, 02, 03 макета Figma)."""

from services import auth, hoa, verification

from services.errors import AppError

from ui import dialogs, kit


def brand_header(board, title, text="", hoa_info=False):
    """Шапка узких экранов: логотип по центру, крупный заголовок и пояснение серым цветом.

    Args:
        title (str): заголовок экрана.
        text (str): пояснение под заголовком.
        hoa_info (bool): вместо пояснения показать название ТСЖ и его адрес.

    Returns:
        Номер надписи с адресом ТСЖ (её текст меняется, когда адрес оформлен) или None.
    """
    kit.logo(board, 234, 26, 53)
    board.label(0, 90, 521, title, "Bold", 32)
    address_item = None
    if hoa_info:
        info = hoa.get_hoa()
        if info is not None:
            board.label(0, 138, 521, info["name"], "Medium", 20)
            address_item = board.label(
                60, 166, 401, info["address"], "Light", 16, color=kit.MUTED, wrap=True
            )
    elif text:
        board.label(60, 138, 401, text, "Light", 16, color=kit.MUTED, wrap=True)
    return address_item


def refresh_address_item(board, item):
    """Подставляет в надпись адреса актуальный адрес ТСЖ из базы."""
    info = hoa.get_hoa()
    if item is not None and info is not None:
        board.itemconfigure(item, text=info["address"])


class LoginScreen:
    """Экран «Вход в систему»: логотип, название ТСЖ и форма на голубой панели."""

    size = (521, 650)
    title = "Вход в систему"

    def __init__(self, app, board, message="", kind="error"):
        """
        Args:
            app: главный объект программы.
            board: холст размером с кадр.
            message (str): плашка с сообщением над кнопкой «Войти».
            kind (str): "error" - красная плашка, "info" - голубая.
        """
        self.app = app
        self.board = board
        self.address_item = brand_header(board, "Вход в систему", hoa_info=True)

        board.shape(38, 232, 445, 276, 22, kit.PANEL_BLUE)
        board.label(87, 258, 355, "Электронная почта", "Regular", 16, align="left")
        self.login = kit.EntryBox(board, 83, 287, 355, 42)
        board.label(87, 342, 355, "Пароль", "Regular", 16, align="left")
        self.password = kit.EntryBox(board, 83, 371, 355, 42, show="*")
        self.login.on_enter(self.try_login)
        self.password.on_enter(self.try_login)

        board.set_layer("message")
        if message:
            kit.note(board, 83, 432, 355, 51, message, kind)
        else:
            kit.link(board, 152, 430, 216, "восстановить аккаунт", app.show_recovery_choice)
        board.set_layer("base")

        kit.Button(board, 152, 540, 216, 35, "Войти", self.try_login)
        kit.link(board, 152, 588, 216, "зарегистрироваться", app.show_resident_register)
        self.login.focus()

    def refresh_address(self):
        """Подставляет полный адрес, когда он оформлен (после очереди)."""
        refresh_address_item(self.board, self.address_item)

    def show_message(self, text):
        """Показывает красную плашку с текстом ошибки."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 432, 355, 51, text, "error")
        self.board.set_layer("base")

    def try_login(self):
        """Проверяет логин и пароль и открывает окно по роли."""
        try:
            user = auth.login_user(self.login.get(), self.password.get())
        except AppError as error:
            self.show_message(str(error))
            return
        self.app.session_password = self.password.get()
        self.app.show_main(user)


def send_code(screen, kind, data):
    """Отправляет код на почту из формы и открывает экран ввода кода (или показывает ошибку)."""
    screen.board.configure(cursor="watch")
    screen.board.update()
    try:
        login = verification.start(kind, data)
    except AppError as error:
        screen.board.configure(cursor="")
        dialogs.show_error(screen.board, str(error))
        return
    screen.app.show_verification(kind, data, login)


class VerificationScreen:
    """Экран «Подтверждение почты»: ввод кода из 4 цифр, отправленного на почту."""

    size = (521, 560)
    title = "Подтверждение почты"

    def __init__(self, app, board, kind, data, login):
        """
        Args:
            kind: verification.CHAIRMAN или verification.RESIDENT.
            data (dict): данные формы (вернуться назад можно без повторного ввода).
            login (str): почта, на которую отправлен код.
        """
        self.app, self.board = app, board
        self.kind, self.data, self.login = kind, data, login
        brand_header(
            board,
            "Подтверждение почты",
            f"Мы отправили код из 4 цифр на {login}. Введите его, чтобы завершить регистрацию.",
        )
        board.shape(38, 240, 445, 187, 22, kit.PANEL_BLUE)
        self.code = dialogs.add_field(board, "Код из письма", 83, 299, 355, max_length=4)
        self.code.on_enter(self.confirm)
        kit.Button(board, 106, 455, 119, 35, "Назад", self.back, "plain")
        kit.Button(board, 239, 455, 175, 35, "Подтвердить", self.confirm)
        kit.link(board, 152, 508, 216, "отправить код ещё раз", self.resend)
        self.code.focus()

    def show_note(self, text, kind):
        """Плашка с сообщением под полем: красная ("error") или голубая ("info")."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 360, 355, 51, text, kind)
        self.board.set_layer("base")

    def back(self):
        """Возвращает на форму регистрации с заполненными полями."""
        verification.cancel(self.login)
        self.app.show_register(self.kind, self.data)

    def resend(self):
        """Отправляет новый код."""
        self.show_note("Отправляем новый код...", "info")
        self.board.update()
        try:
            verification.resend(self.login)
        except AppError as error:
            self.show_note(str(error), "error")
            return
        self.show_note("Новый код отправлен на почту.", "info")

    def confirm(self):
        """Проверяет код: верный - создаёт аккаунт."""
        code = self.code.get().strip()
        if len(code) != 4 or not code.isdigit():
            self.show_note("Введите код из 4 цифр.", "error")
            return
        try:
            result = verification.confirm(self.login, code)
        except AppError as error:
            self.show_note(str(error), "error")
            return
        if self.kind == verification.CHAIRMAN:
            text = "Председатель зарегистрирован. Войдите в систему."
            if result:
                text += "\nАдрес будет оформлен полностью автоматически, когда появится интернет."
            dialogs.show_info(self.board, text)
            self.app.show_login()
        elif result:
            self.app.show_login("Вы зарегистрированы как собственник. Войдите в систему.", "info")
        else:
            self.app.show_login("Аккаунт ожидает подтверждения председателем")


class RecoveryChoiceScreen:
    """Окно «Чей аккаунт восстановить»: два варианта и кнопки «Отмена» и «Далее»."""

    size = (521, 470)
    title = "Чей аккаунт восстановить"

    def __init__(self, app, board):
        self.app = app
        self.board = board
        self.chairman = None
        brand_header(board, "Восстановление аккаунта", "Чей аккаунт нужно восстановить?")
        board.shape(38, 232, 445, 92, 22, kit.PANEL_BLUE)
        kit.Button(board, 199, 410, 119, 35, "Отмена", app.show_login, "plain")
        kit.Button(board, 332, 410, 131, 35, "Далее", self.next)
        self.draw_choice()

    def draw_choice(self):
        """Рисует кнопки выбора: выбранная синяя, вторая белая (пока не выбрано - обе синие)."""
        self.board.clear_layer("choice")
        self.board.set_layer("choice")
        for x, text, is_chairman in ((58, "Председатель", True), (268, "Жилец", False)):
            kind = (
                "plain" if self.chairman is not None and self.chairman != is_chairman else "primary"
            )
            kit.Button(
                self.board, x, 260, 195, 35, text, lambda v=is_chairman: self.choose(v), kind
            )
        self.board.set_layer("base")

    def choose(self, is_chairman):
        """Запоминает выбор и перерисовывает кнопки (после щелчка, чтобы не удалять нажатую)."""
        self.chairman = is_chairman
        self.board.clear_layer("message")
        self.board.after(1, self.draw_choice)

    def next(self):
        """Открывает экран восстановления выбранного человека."""
        if self.chairman is None:
            self.board.clear_layer("message")
            self.board.set_layer("message")
            kit.note(self.board, 83, 342, 355, 51, "Выберите, чей аккаунт восстановить", "error")
            self.board.set_layer("base")
            return
        self.app.show_recovery(self.chairman)


class RecoveryScreen:
    """Экран «Восстановление аккаунта»: пароль приходит на почту, указанную при регистрации."""

    size = (521, 540)
    title = "Восстановление аккаунта"

    def __init__(self, app, board, chairman=False):
        """
        Args:
            chairman (bool): True - восстанавливаем аккаунт председателя, False - жильца.
        """
        self.app = app
        self.board = board
        self.chairman = chairman
        who = "председателя" if chairman else "жильца"
        brand_header(
            board,
            "Восстановление аккаунта",
            f"Аккаунт {who}. Новый пароль придёт на электронную почту, "
            "которую вы указали при регистрации.",
        )
        board.shape(38, 232, 445, 195, 22, kit.PANEL_BLUE)
        self.email = dialogs.add_field(board, "Электронная почта", 83, 291, 355)
        self.email.on_enter(self.send)
        kit.Button(board, 106, 455, 119, 35, "Отмена", app.show_login, "plain")
        kit.Button(board, 239, 455, 175, 35, "Отправить пароль", self.send)
        self.email.focus()

    def show_note(self, text, kind):
        """Плашка с сообщением под полем: красная ("error") или голубая ("info")."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 352, 355, 51, text, kind)
        self.board.set_layer("base")

    def send(self):
        """Создаёт новый пароль и отправляет его на почту."""
        self.show_note("Отправляем новый пароль...", "info")
        self.board.update()
        try:
            auth.recover_account(self.email.get(), self.chairman)
        except AppError as error:
            self.show_note(str(error), "error")
            return
        self.app.show_login("Новый пароль отправлен на вашу почту. Войдите с ним.", "info")


class ResidentRegisterScreen:
    """Экран «Регистрация жильца»: логотип, название ТСЖ и форма на голубой панели."""

    size = (521, 915)
    title = "Регистрация жильца"

    def __init__(self, app, board, data=None):
        self.app = app
        self.board = board
        self.address_item = brand_header(board, "Регистрация жильца", hoa_info=True)
        board.shape(38, 222, 445, 520, 22, kit.PANEL_BLUE)

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, "ФИО", 83, 268, 355),
            "phone": add(board, "Телефон", 83, 350, 355),
            "apartment_number": add(board, "Квартира", 83, 432, 355),
            "login": add(board, "Электронная почта", 83, 514, 355),
            "password": add(board, "Пароль", 83, 596, 355, show="*"),
            "password2": add(board, "Повтор пароля", 83, 678, 355, show="*"),
        }
        kit.note(
            board,
            83,
            756,
            355,
            51,
            "После регистрации аккаунт должен\nподтвердить председатель ТСЖ",
            "info",
        )
        kit.Button(board, 152, 826, 216, 35, "Зарегистрироваться", self.register)
        kit.link(board, 152, 873, 216, "войти", app.show_login)
        for key, value in (data or {}).items():
            if key in self.fields:
                self.fields[key].set(value)
        self.fields["full_name"].focus()

    def refresh_address(self):
        """Подставляет полный адрес, когда он оформлен (после очереди)."""
        refresh_address_item(self.board, self.address_item)

    def register(self):
        """Проверяет форму и отправляет код подтверждения на почту (аккаунт пока не создаётся)."""
        data = {key: field.get() for key, field in self.fields.items()}
        send_code(self, verification.RESIDENT, data)


class ChairmanRegisterScreen:
    """Экран «Регистрация председателя ТСЖ» (кадр 03, размер 952x919)."""

    size = (952, 919)
    title = "Регистрация председателя ТСЖ"

    def __init__(self, app, board, data=None):
        self.app = app
        self.board = board
        board.label(77, 68, 807, "Регистрация председателя ТСЖ", "Bold", 32, align="left")
        board.label(
            77,
            111,
            807,
            "Данные ТСЖ ещё не заполнены. Укажите данные председателя дома.",
            "ExtraLight",
            20,
            color=kit.MUTED,
            align="left",
        )
        board.shape(77, 166, 807, 306, 15, kit.PANEL_BLUE)
        board.shape(77, 496, 807, 322, 15, kit.PANEL_BLUE)
        board.label(111, 176, 400, "Председатель", "Bold", 24, align="left")
        board.label(111, 503, 400, "Данные ТСЖ", "Bold", 24, align="left")

        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, "ФИО", 111, 248, 355),
            "phone": add(board, "Телефон", 494, 248, 355),
            "login": add(board, "Электронная почта", 111, 332, 738),
            "password": add(board, "Пароль", 111, 416, 355, show="*"),
            "password2": add(board, "Повторите пароль", 494, 416, 355, show="*"),
            "hoa_name": add(board, "Наименование ТСЖ", 111, 575, 738),
            "inn": add(board, "ИНН", 111, 659, 355),
            "rate": add(board, "Тариф за 1 м2, руб.", 494, 659, 355),
            "address": add(board, "Адрес дома", 111, 743, 738),
        }
        kit.Button(board, 539, 850, 119, 35, "Отмена", app.root.destroy, "plain")
        kit.Button(board, 668, 850, 216, 35, "Зарегистрироваться", self.register)
        for key, value in (data or {}).items():
            if key in self.fields:
                self.fields[key].set(value)
        self.fields["full_name"].focus()

    def register(self):
        """Проверяет форму и отправляет код подтверждения на почту (аккаунт пока не создаётся)."""
        data = {key: field.get() for key, field in self.fields.items()}
        send_code(self, verification.CHAIRMAN, data)
