"""Главный класс программы: хранит окно и переключает экраны."""

import threading
import time

from services import auth, hoa
from ui import dialogs, kit
from ui.auth_screens import (
    ChairmanRegisterScreen,
    LoginScreen,
    RecoveryChoiceScreen,
    RecoveryScreen,
    VerificationScreen,
    ResidentRegisterScreen,
)
from ui.edit_screens import ChairmanEditScreen, ResidentEditScreen
from ui.main_screen import MainScreen
from ui.resident_screen import ResidentScreen

ADDRESS_POLL_MS = 3000
ADDRESS_RETRY_SECONDS = 30


class App:
    """Показывает по одному экрану макета; размер окна подгоняется под кадр."""

    def __init__(self, root):
        """
        Args:
            root: главное окно Tk.
        """
        self.root = root
        self.board = None
        self.screen = None
        self.session_password = ""
        root.configure(bg=kit.WHITE)
        root.resizable(True, True)
        kit.init_scale(root)
        self.set_icon()
        root.bind("<F11>", self.toggle_fullscreen)
        root.bind("<Escape>", self.leave_fullscreen)
        root.report_callback_exception = self.handle_error
        self.address_busy = False
        self.address_done = False
        self.address_tried = float("-inf")
        self.show_start_screen()
        self.watch_address()

    def watch_address(self):
        """Следит за очередью адреса: при появлении интернета подставляет полный адрес."""
        if self.address_done:
            self.address_done = False
            refresh = getattr(self.screen, "refresh_address", None)
            if refresh is not None:
                refresh()
        elif (
            not self.address_busy and time.monotonic() - self.address_tried > ADDRESS_RETRY_SECONDS
        ):
            if hoa.has_pending_address():
                self.address_busy = True
                self.address_tried = time.monotonic()
                threading.Thread(target=self.resolve_address, daemon=True).start()
        self.root.after(ADDRESS_POLL_MS, self.watch_address)

    def resolve_address(self):
        """Фоновый поток: один запрос к нейросети, окно в это время не замирает."""
        try:
            self.address_done = hoa.resolve_pending_address()
        except Exception:
            self.address_done = False
        finally:
            self.address_busy = False

    def set_icon(self):
        """Ставит логотип в заголовок окна (если файл логотипа есть)."""
        picture = kit.logo_image(64)
        if picture is not None:
            self.root.iconphoto(True, picture)

    def is_big_window(self):
        """True, если окно сейчас развёрнуто или открыто на весь экран."""
        return self.root.state() == "zoomed" or bool(self.root.attributes("-fullscreen"))

    def toggle_fullscreen(self, event=None):
        """F11: на весь экран и обратно."""
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))
        return "break"

    def leave_fullscreen(self, event=None):
        """Esc: выйти из полноэкранного режима."""
        if self.root.attributes("-fullscreen"):
            self.root.attributes("-fullscreen", False)

    def handle_error(self, error_type, error, traceback):
        """Неожиданная ошибка (например, сбой базы) не закрывает программу.

        Пользователь видит сообщение и продолжает работу (п. 4.1.4 ТЗ).
        """
        dialogs.show_error(self.root, f"Произошла ошибка: {error}")

    def show(self, screen_class, *args):
        """Заменяет текущий экран новым и подгоняет размер окна.

        Args:
            screen_class: класс экрана (LoginScreen и т.д.).
            *args: дополнительные аргументы экрана.
        """
        if self.board is not None:
            self.board.destroy()
        width, height = screen_class.size
        self.board = kit.Board(self.root, width, height)
        self.board.place(relx=0.5, rely=0.5, anchor="center")
        self.root.title(screen_class.title)

        pixel_width, pixel_height = kit.S(width), kit.S(height)
        self.root.minsize(pixel_width, pixel_height)
        if not self.is_big_window():
            x = (self.root.winfo_screenwidth() - pixel_width) // 2
            y = max((self.root.winfo_screenheight() - pixel_height) // 3 - 20, 0)
            self.root.geometry(f"{pixel_width}x{pixel_height}+{x}+{y}")
        self.screen = screen_class(self, self.board, *args)

    def show_start_screen(self):
        """Первый запуск: регистрация председателя, иначе - вход."""
        if auth.chairman_exists():
            self.show_login()
        else:
            self.show(ChairmanRegisterScreen)

    def show_login(self, message="", kind="error"):
        """Экран входа (можно передать сообщение: kind "error" - красное, "info" - голубое)."""
        self.session_password = ""
        self.show(LoginScreen, message, kind)

    def show_resident_register(self, data=None):
        """Экран регистрации жильца (data - уже введённые поля)."""
        self.show(ResidentRegisterScreen, data)

    def show_register(self, kind, data=None):
        """Форма регистрации жильца или председателя (после возврата с экрана ввода кода)."""
        if kind == "chairman":
            self.show(ChairmanRegisterScreen, data)
        else:
            self.show_resident_register(data)

    def show_verification(self, kind, data, login):
        """Экран ввода кода, отправленного на почту при регистрации."""
        self.show(VerificationScreen, kind, data, login)

    def show_recovery_choice(self):
        """Окно «Чей аккаунт восстановить» (кадр 25)."""
        self.show(RecoveryChoiceScreen)

    def show_recovery(self, chairman=False):
        """Экран восстановления аккаунта председателя (True) или жильца (False)."""
        self.show(RecoveryScreen, chairman)

    def show_main(self, user, tab=0):
        """Главное окно в зависимости от роли пользователя (tab - вкладка председателя)."""
        if user["is_participant"] == 0:
            self.show(MainScreen, user, tab)
        else:
            self.show(ResidentScreen, user)

    def show_chairman_edit(self, user, tab):
        """Экран редактирования данных ТСЖ и председателя (кнопка-шестерёнка)."""
        self.show(ChairmanEditScreen, user, tab)

    def show_resident_edit(self, user):
        """Экран редактирования данных жильца (кнопка-шестерёнка)."""
        self.show(ResidentEditScreen, user)
