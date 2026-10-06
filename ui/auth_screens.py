"""Экраны входа и регистрации (кадры 00, 02, 03 макета Figma)."""

# сервисы: вход/регистрация и данные ТСЖ
from services import auth, hoa, verification

# наша ошибка, которую нужно показать пользователю
from services.errors import AppError

# окна и элементы интерфейса
from ui import dialogs, kit


def hoa_subtitle():
    """Строка «название ТСЖ, адрес» для заголовков экранов."""
    # данные ТСЖ из базы
    info = hoa.get_hoa()
    if info is None:
        return ""
    return f"{info['name']}, {info['address']}"


class LoginScreen:
    """Экран «Вход в систему» (кадр 00, размер 521x572)."""

    # размер кадра в Figma: ширина и высота
    size = (521, 572)
    # заголовок окна
    title = "Вход в систему"

    def __init__(self, app, board, message="", kind="error"):
        """
        Args:
            app: главный объект программы.
            board: холст размером с кадр.
            message (str): красная плашка над кнопкой «Войти».
        """
        # запоминаем главный объект и холст
        self.app = app
        self.board = board
        # label(x, y, ширина, текст, шрифт, размер) - надпись; координаты берём из Figma
        board.label(0, 83, 521, "Вход в систему", "Bold", 32)
        self.address_item = board.label(40, 126, 441, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        board.label(87, 215, 355, "Электронная почта", "Regular", 16, align="left")
        # поле ввода: x, y, ширина, высота
        self.login = kit.EntryBox(board, 83, 244, 355, 42)
        board.label(87, 315, 355, "Пароль", "Regular", 16, align="left")
        # show="*" - вместо символов пароля показываются звёздочки
        self.password = kit.EntryBox(board, 83, 344, 355, 42, show="*")
        # по нажатию Enter тоже пробуем войти
        self.login.on_enter(self.try_login)
        self.password.on_enter(self.try_login)

        # сообщение рисуем на отдельном слое, чтобы его можно было стереть
        board.set_layer("message")
        if message:
            # цветная плашка с подсказкой
            kit.note(board, 83, 394, 355, 51, message, kind)
        else:
            # пока сообщения нет, на его месте стоит ссылка (как в макете)
            kit.link(board, 152, 394, 216, "восстановить аккаунт", app.show_recovery_choice)
        board.set_layer("base")

        # кнопка: x, y, ширина, высота, текст, функция по клику
        kit.Button(board, 152, 495, 216, 35, "Войти", self.try_login)
        # ссылка под кнопкой
        kit.link(board, 152, 538, 216, "зарегистрироваться", app.show_resident_register)
        # курсор сразу в поле логина
        self.login.focus()

    def refresh_address(self):
        """Подставляет полный адрес, когда он оформлен (после очереди)."""
        self.board.itemconfigure(self.address_item, text=hoa_subtitle())

    def show_message(self, text):
        """Показывает красную плашку с текстом ошибки."""
        # стираем старое сообщение
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 394, 355, 51, text, "error")
        self.board.set_layer("base")

    def try_login(self):
        """Проверяет логин и пароль и открывает окно по роли."""
        try:
            # сервис проверит логин и пароль
            user = auth.login_user(self.login.get(), self.password.get())
        # неверные данные - показываем текст ошибки на экране
        except AppError as error:
            self.show_message(str(error))
            return
        # запоминаем пароль на время работы: настройки покажут его в поле «Пароль»
        self.app.session_password = self.password.get()
        # успех - открываем окно по роли
        self.app.show_main(user)


def send_code(screen, kind, data):
    """Отправляет код на почту из формы и открывает экран ввода кода (или показывает ошибку)."""
    screen.board.configure(cursor="watch")  # отправка письма занимает несколько секунд
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

    size = (521, 575)
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
        board.label(0, 100, 521, "Подтверждение почты", "Bold", 32)
        board.label(
            60,
            160,
            401,
            f"Мы отправили код из 4 цифр на {login}. Введите его, чтобы завершить регистрацию.",
            "ExtraLight",
            20,
            wrap=True,
        )
        self.code = dialogs.add_field(
            board, 53, 290, 250, "Код из письма", 83, 319, 355, max_length=4
        )
        self.code.on_enter(self.confirm)
        kit.Button(board, 106, 440, 119, 35, "Назад", self.back, "plain")
        kit.Button(board, 239, 440, 175, 35, "Подтвердить", self.confirm)
        kit.link(board, 152, 500, 216, "отправить код ещё раз", self.resend)
        self.code.focus()

    def show_note(self, text, kind):
        """Плашка с сообщением под полем: красная ("error") или голубая ("info")."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 380, 355, 51, text, kind)
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
            if result:  # адрес ждёт интернета в очереди
                text += "\nАдрес будет оформлен полностью автоматически, когда появится интернет."
            dialogs.show_info(self.board, text)
            self.app.show_login()
        elif result:  # жилец - собственник из реестра: подтверждение не нужно
            self.app.show_login("Вы зарегистрированы как собственник. Войдите в систему.", "info")
        else:  # остальные ждут подтверждения председателя
            self.app.show_login("Аккаунт ожидает подтверждения председателем")


class RecoveryChoiceScreen:
    """Окно «Чей аккаунт восстановить» (кадр 25, размер 521x575)."""

    size = (521, 575)
    title = "Чей аккаунт восстановить"

    def __init__(self, app, board):
        self.app = app
        self.board = board
        # None - ничего не выбрано, True - председатель, False - жилец
        self.chairman = None
        board.label(0, 152, 521, "Чей аккаунт восстановить", "Bold", 32)
        kit.Button(board, 220, 341, 119, 35, "Отмена", app.show_login, "plain")
        kit.Button(board, 353, 341, 131, 35, "Далее", self.next)
        self.draw_choice()

    def draw_choice(self):
        """Рисует кнопки выбора: выбранная синяя, вторая белая (пока не выбрано - обе синие)."""
        self.board.clear_layer("choice")
        self.board.set_layer("choice")
        for x, text, is_chairman in ((38, "Председатель", True), (268, "Жилец", False)):
            kind = (
                "plain" if self.chairman is not None and self.chairman != is_chairman else "primary"
            )
            kit.Button(
                self.board, x, 220, 216, 35, text, lambda v=is_chairman: self.choose(v), kind
            )
        self.board.set_layer("base")

    def choose(self, is_chairman):
        """Запоминает выбор и перерисовывает кнопки (после щелчка, чтобы не удалять нажатую)."""
        self.chairman = is_chairman
        self.board.clear_layer("message")  # старое предупреждение больше не нужно
        self.board.after(1, self.draw_choice)

    def next(self):
        """Открывает экран восстановления выбранного человека."""
        if self.chairman is None:
            self.board.clear_layer("message")
            self.board.set_layer("message")
            kit.note(self.board, 83, 394, 355, 51, "Выберите, чей аккаунт восстановить", "error")
            self.board.set_layer("base")
            return
        self.app.show_recovery(self.chairman)


class RecoveryScreen:
    """Экран «Восстановление аккаунта»: пароль приходит на почту, указанную при регистрации."""

    size = (521, 575)
    title = "Восстановление аккаунта"

    def __init__(self, app, board, chairman=False):
        """
        Args:
            chairman (bool): True - восстанавливаем аккаунт председателя, False - жильца.
        """
        self.app = app
        self.board = board
        self.chairman = chairman
        board.label(0, 100, 521, "Восстановление аккаунта", "Bold", 32)
        who = "председателя" if chairman else "жильца"
        board.label(
            60,
            160,
            401,
            f"Аккаунт {who}. Новый пароль придёт на электронную почту, "
            "которую вы указали при регистрации.",
            "ExtraLight",
            20,
            wrap=True,
        )
        self.email = dialogs.add_field(board, 53, 270, 250, "Электронная почта", 83, 299, 355)
        self.email.on_enter(self.send)
        kit.Button(board, 106, 440, 119, 35, "Отмена", app.show_login, "plain")
        kit.Button(board, 239, 440, 175, 35, "Отправить пароль", self.send)
        self.email.focus()

    def show_note(self, text, kind):
        """Плашка с сообщением под полем: красная ("error") или голубая ("info")."""
        self.board.clear_layer("message")
        self.board.set_layer("message")
        kit.note(self.board, 83, 360, 355, 51, text, kind)
        self.board.set_layer("base")

    def send(self):
        """Создаёт новый пароль и отправляет его на почту."""
        self.show_note("Отправляем новый пароль...", "info")
        self.board.update()  # перерисовать окно до того, как начнётся долгая отправка
        try:
            auth.recover_account(self.email.get(), self.chairman)
        except AppError as error:
            self.show_note(str(error), "error")
            return
        self.app.show_login("Новый пароль отправлен на вашу почту. Войдите с ним.", "info")


class ResidentRegisterScreen:
    """Экран «Регистрация жильца» (кадр 02, размер 521x909)."""

    size = (521, 909)
    title = "Регистрация жильца"

    def __init__(self, app, board, data=None):
        self.app = app
        self.board = board
        board.label(0, 68, 521, "Регистрация жильца", "Bold", 32)
        self.address_item = board.label(40, 111, 441, hoa_subtitle(), "ExtraLight", 20, wrap=True)

        # словарь полей формы: ключ совпадает с ключом данных для сервиса
        self.fields = {
            "full_name": dialogs.add_field(board, 0, 0, 0, "ФИО", 83, 225, 355),
            "phone": dialogs.add_field(board, 0, 0, 0, "Телефон", 83, 309, 355),
            # квартира - обычное поле: жилец вводит номер сам
            "apartment_number": dialogs.add_field(board, 0, 0, 0, "Квартира", 83, 393, 355),
            "login": dialogs.add_field(board, 0, 0, 0, "Электронная почта", 83, 477, 355),
            "password": dialogs.add_field(board, 0, 0, 0, "Пароль", 83, 561, 355, show="*"),
            "password2": dialogs.add_field(board, 0, 0, 0, "Повтор пароля", 83, 645, 355, show="*"),
        }
        kit.note(
            board,
            83,
            703,
            355,
            51,
            "После регистрации аккаунт должен\nподтвердить председатель ТСЖ",
            "info",
        )
        kit.Button(board, 152, 775, 216, 35, "Зарегистрироваться", self.register)
        kit.link(board, 152, 824, 216, "войти", app.show_login)
        for key, value in (data or {}).items():  # вернулись с экрана ввода кода: поля заполнены
            if key in self.fields:
                self.fields[key].set(value)
        self.fields["full_name"].focus()

    def refresh_address(self):
        """Подставляет полный адрес, когда он оформлен (после очереди)."""
        self.board.itemconfigure(self.address_item, text=hoa_subtitle())

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
            align="left",
        )
        # голубая панель-подложка под группой полей
        board.shape(77, 166, 807, 306, 15, kit.PANEL_BLUE)
        board.shape(77, 496, 807, 322, 15, kit.PANEL_BLUE)
        board.label(111, 176, 400, "Председатель", "Bold", 24, align="left")
        board.label(111, 503, 400, "Данные ТСЖ", "Bold", 24, align="left")

        # короткое имя для функции создания «подпись + поле»
        add = dialogs.add_field
        self.fields = {
            "full_name": add(board, 0, 0, 0, "ФИО", 111, 248, 355),
            "phone": add(board, 0, 0, 0, "Телефон", 494, 248, 355),
            "login": add(board, 0, 0, 0, "Электронная почта", 111, 332, 738),
            "password": add(board, 0, 0, 0, "Пароль", 111, 416, 355, show="*"),
            "password2": add(board, 0, 0, 0, "Повторите пароль", 494, 416, 355, show="*"),
            "hoa_name": add(board, 0, 0, 0, "Наименование ТСЖ", 111, 575, 738),
            "inn": add(board, 0, 0, 0, "ИНН", 111, 659, 355),
            "rate": add(board, 0, 0, 0, "Тариф за 1 м2, руб.", 494, 659, 355),
            "address": add(board, 0, 0, 0, "Адрес дома", 111, 743, 738),
        }
        # «Отмена» закрывает программу: без председателя работать нельзя
        kit.Button(board, 539, 850, 119, 35, "Отмена", app.root.destroy, "plain")
        kit.Button(board, 668, 850, 216, 35, "Зарегистрироваться", self.register)
        for key, value in (data or {}).items():  # вернулись с экрана ввода кода: поля заполнены
            if key in self.fields:
                self.fields[key].set(value)
        self.fields["full_name"].focus()

    def register(self):
        """Проверяет форму и отправляет код подтверждения на почту (аккаунт пока не создаётся)."""
        data = {key: field.get() for key, field in self.fields.items()}
        send_code(self, verification.CHAIRMAN, data)
