"""Кабинет жильца (кадр 20 макета Figma, размер 1588x919)."""

# сервисы, которые нужны кабинету
from services import apartments, dates, finance, hoa, requests_service
from services import validation as check
from services.errors import AppError
from ui import dialogs, kit

# переиспользуем функции из окна председателя
from ui.main_screen import date_only, short_name


# Копейки -> «1894,74» (с запятой, как в макете)
def money(kopecks):
    """Сумма в копейках -> «1894,74» (запятая, как в макете)."""
    return check.kopecks_to_text(kopecks).replace(".", ",")


# Кабинет жильца: долг, история операций, подача и список заявок
class ResidentScreen:
    """Кабинет жильца: долг, история операций, подача и список заявок."""

    size = (1588, 919)
    title = "Система управления ТСЖ"
    # столбцы таблицы истории
    HISTORY_COLUMNS = [
        {"title": "Дата / период", "cx": 106.5, "style": "Light", "size": 24, "width": 190},
        {"title": "Операция", "cx": 336, "style": "Light", "size": 24, "width": 190},
        {"title": "Назначение", "cx": 553, "style": "Light", "size": 24, "width": 200},
        {"title": "Сумма, руб.", "cx": 760, "style": "Light", "size": 24, "width": 190},
    ]

    def __init__(self, app, board, user):
        """
        Args:
            app: главный объект программы.
            board: холст размером 1588x919.
            user (dict): вошедший жилец.
        """
        self.app = app
        self.board = board
        # user - словарь вошедшего жильца (из базы)
        self.user = user
        # квартира жильца берётся по его apartment_id
        self.apartment = apartments.get_apartment(user["apartment_id"])
        # с какой заявки показываем список «Мои заявки» (прокрутка)
        self.requests_offset = 0

        # шапка: название ТСЖ и адрес
        info = hoa.get_hoa()
        board.label(-79, 18, 525, info["name"], "Bold", 32)
        board.label(26, 61, 382, info["address"], "ExtraLight", 20)
        # справа ФИО жильца и номер его квартиры
        caption = f"{short_name(user['full_name'])} * кв.{self.apartment['number']}"
        board.label(988, 32, 291, caption, "Regular", 20)
        # выход на экран входа
        kit.Button(board, 1299, 29, 119, 35, "Выйти", app.show_login, "plain")
        board.hline(0, 96, 1588)

        # (запас под слой данных, дальше не используется)
        self.debt_layer_widgets = None
        # оранжевая плашка с задолженностью
        board.shape(33, 137, 903, 108, 22, "#ffcbae")
        board.label(41, 151, 400, f"Задолженность на {dates.today_text()}", "Light", 24)
        board.label(31, 277, 489, "История начислений и оплат", "Regular", 32)
        # таблица «История начислений и оплат»
        self.table = kit.Table(board, 31, 330, 905, 433, self.HISTORY_COLUMNS)

        # панель «Новая заявка»
        board.shape(988, 137, 546, 353, 22, kit.PANEL_GRAY)
        board.label(937, 151, 291, "Новая заявка", "Bold", 20)
        board.label(
            1012,
            194,
            382,
            f"Квартира {self.apartment['number']} подставлена автоматически",
            "ExtraLight",
            20,
        )
        board.label(961, 245, 188, "Тема", "Regular", 16)
        # поле темы
        self.title_entry = kit.EntryBox(board, 1019, 274, 460, 42)
        board.label(961, 329, 188, "Описание", "Regular", 16)
        # поле описания
        self.description = kit.TextBox(board, 1019, 367, 460, 42)
        # кнопка отправки заявки
        kit.Button(board, 1153, 439, 216, 35, "Отправить заявку", self.send_request)

        # панель «Мои заявки»
        board.shape(988, 528, 546, 310, 22, kit.PANEL_GRAY)
        board.label(937, 545, 291, "Мои заявки", "Bold", 20)
        # колесо мыши листает заявки
        board.add_wheel_area(988, 528, 546, 310, self.scroll_requests)
        # первое заполнение данных
        self.refresh()

    # Обновляет долг, таблицу истории и список заявок
    def refresh(self):
        """Обновляет долг, историю операций и список «Мои заявки»."""
        board = self.board
        # стираем старые данные и рисуем новые на слое data
        board.clear_layer("data")
        board.set_layer("data")
        # итоги: начислено, оплачено, долг и история
        summary = finance.get_resident_summary(self.apartment["apartment_id"])
        board.label(-26, 187, 399, f"{money(summary['debt'])} руб.", "Medium", 36)
        board.label(550, 158, 400, f"Начислено: {money(summary['charged'])} руб.", "Light", 24)
        board.label(550, 199, 400, f"Оплачено: {money(summary['paid'])} руб.", "Light", 24)

        # строки таблицы истории
        rows = []
        for index, (stamp, operation, purpose, amount) in enumerate(summary["history"]):
            # у начисления период «ГГГГ-ММ» (7 символов), у оплаты полная дата
            shown = stamp if len(stamp) == 7 else date_only(stamp)
            # начисление со знаком +, оплата уже со знаком -
            sign = "+" if amount > 0 else ""
            rows.append((index, [shown, operation, purpose, sign + money(amount)], None))
        # загружаем историю в таблицу
        self.table.set_rows(rows)

        # заявки только этой квартиры
        self.my_requests = list(
            requests_service.get_requests(apartment_id=self.apartment["apartment_id"])
        )
        self.requests_offset = min(self.requests_offset, max(0, len(self.my_requests) - 5))
        # показываем пять заявок за раз
        for position, row in enumerate(self.my_requests[self.requests_offset :][:5]):
            # каждая следующая ниже на 44 пикселя
            y = 597 + position * 44
            text = board.fit_text(f"№ {row['requests_id']}  * {row['title']}", "Regular", 16, 330)
            board.label(1010, y, 340, text, "Regular", 16, align="left")
            # выполненные чёрным, остальные синим
            done = row["status"] == "Выполнена"
            board.label(
                1347,
                y - 3,
                187,
                row["status"].lower(),
                "Regular",
                24,
                kit.BLACK if done else "#0048ff",
            )
        board.set_layer("base")

    # Прокрутка списка заявок колесом
    def scroll_requests(self, direction):
        """Прокручивает список «Мои заявки» колесом мыши."""
        maximum = max(0, len(self.my_requests) - 5)
        self.requests_offset = min(max(self.requests_offset + direction, 0), maximum)
        self.refresh()

    # Отправка заявки: источник всегда «Приложение», квартира - жильца
    def send_request(self):
        """Отправляет заявку от имени жильца."""
        try:
            requests_service.create_request(
                self.user["users_id"],
                self.apartment["apartment_id"],
                self.title_entry.get(),
                self.description.get(),
                "Приложение",
            )
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        # после отправки очищаем поля
        self.title_entry.clear()
        self.description.clear()
        self.requests_offset = 0
        self.refresh()
        dialogs.show_info(self.board, "Заявка отправлена.")
