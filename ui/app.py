"""Главный класс программы: хранит окно и переключает экраны."""

# auth нужен, чтобы узнать, есть ли уже председатель
from services import auth

# dialogs - всплывающие окна, kit - элементы интерфейса
from ui import dialogs, kit

# экраны входа и регистрации
from ui.auth_screens import ChairmanRegisterScreen, LoginScreen, ResidentRegisterScreen

# окно председателя
from ui.main_screen import MainScreen

# кабинет жильца
from ui.resident_screen import ResidentScreen


class App:
    """Показывает по одному экрану макета; размер окна подгоняется под кадр."""

    def __init__(self, root):
        """
        Args:
            root: главное окно Tk.
        """
        # запоминаем окно: оно понадобится в других методах
        self.root = root
        # board - холст текущего экрана; пока экрана нет
        self.board = None
        # объект текущего экрана
        self.screen = None
        # белый фон окна
        root.configure(bg=kit.WHITE)
        # размер окна менять нельзя: он подогнан под макет
        root.resizable(False, False)
        # считаем масштаб интерфейса под экран
        kit.init_scale(root)
        # любая неожиданная ошибка пойдёт в handle_error, а не закроет программу
        root.report_callback_exception = self.handle_error
        # показываем первый экран
        self.show_start_screen()

    def handle_error(self, error_type, error, traceback):
        """Неожиданная ошибка (например, сбой базы) не закрывает программу.

        Пользователь видит сообщение и продолжает работу (п. 4.1.4 ТЗ).
        """
        # показываем сообщение об ошибке и продолжаем работу
        dialogs.show_error(self.root, f"Произошла ошибка: {error}")

    def show(self, screen_class, *args):
        """Заменяет текущий экран новым и подгоняет размер окна.

        Args:
            screen_class: класс экрана (LoginScreen и т.д.).
            *args: дополнительные аргументы экрана.
        """
        # если какой-то экран уже есть,
        if self.board is not None:
            self.board.destroy()
        # размер кадра берём из самого класса экрана
        width, height = screen_class.size
        # создаём новый холст нужного размера
        self.board = kit.Board(self.root, width, height)
        self.board.pack()
        # название окна берём из класса экрана
        self.root.title(screen_class.title)

        # переводим размер из пикселей макета в пиксели экрана
        pixel_width, pixel_height = kit.S(width), kit.S(height)
        # ставим окно по центру экрана по горизонтали
        x = (self.root.winfo_screenwidth() - pixel_width) // 2
        # по вертикали чуть выше центра
        y = max((self.root.winfo_screenheight() - pixel_height) // 3 - 20, 0)
        # задаём размер и положение окна
        self.root.geometry(f"{pixel_width}x{pixel_height}+{x}+{y}")
        # создаём сам экран: он рисует все элементы на холсте
        self.screen = screen_class(self, self.board, *args)

    def show_start_screen(self):
        """Первый запуск: регистрация председателя, иначе - вход."""
        # председатель уже есть - показываем вход
        if auth.chairman_exists():
            self.show_login()
        else:
            # председателя нет (первый запуск) - его регистрация
            self.show(ChairmanRegisterScreen)

    def show_login(self, message=""):
        """Экран входа (можно передать красное сообщение)."""
        # message - красное сообщение над кнопкой «Войти»
        self.show(LoginScreen, message)

    def show_resident_register(self):
        """Экран регистрации жильца."""
        self.show(ResidentRegisterScreen)

    def show_main(self, user):
        """Главное окно в зависимости от роли пользователя."""
        # 0 - председатель, 1 - жилец
        if user["is_participant"] == 0:
            self.show(MainScreen, user)
        else:
            self.show(ResidentScreen, user)
