"""Кабинет жильца (кадр 20 макета Figma, размер 1588x919)."""

from services import apartments, auth, dates, finance, hoa, requests_service
from services import validation as check
from services.errors import AppError
from ui import dialogs, kit

from ui.main_screen import date_only, short_name


def money(kopecks):
    """Сумма в копейках -> «1894,74» (запятая, как в макете)."""
    return check.kopecks_to_text(kopecks).replace(".", ",")


class ResidentScreen:
    """Кабинет жильца: долг, история операций, подача и список заявок."""

    size = (1588, 919)
    title = "Система управления ТСЖ"
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
        self.user = user
        self.apartment = apartments.get_apartment(user["apartment_id"])
        self.requests_offset = 0

        info = hoa.get_hoa()
        self.address_item = kit.header(board, info["name"], info["address"], 18)
        caption = f"{short_name(user['full_name'])} * кв.{self.apartment['number']}"
        board.label(1104, 32, 291, caption, "Regular", 20)
        kit.Button(board, 1376, 29, 119, 35, "Выйти", app.show_login, "plain")
        kit.IconButton(board, 1514, 26, "gear", lambda: app.show_resident_edit(user))
        board.hline(0, 96, 1588)

        chairman = auth.get_chairman()
        if chairman is not None:
            contacts = f"Председатель: {short_name(chairman['full_name'])} * {chairman['phone']}"
            board.label(33, 104, 700, contacts, "ExtraLight", 20, align="left")
        if not auth.is_owner(user):
            board.label(
                988,
                104,
                546,
                f"Собственник: {self.apartment['owner_name']}",
                "ExtraLight",
                20,
                align="left",
            )

        self.debt_layer_widgets = None
        board.shape(33, 137, 903, 108, 22, "#ffcbae")
        board.label(41, 151, 400, f"Задолженность на {dates.today_text()}", "Light", 24)
        board.label(31, 277, 489, "История начислений и оплат", "Regular", 32)
        self.table = kit.Table(board, 31, 330, 905, 433, self.HISTORY_COLUMNS)

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
        self.title_entry = kit.EntryBox(board, 1019, 274, 460, 42, max_length=50)
        board.label(961, 329, 188, "Описание", "Regular", 16)
        self.description = kit.TextBox(board, 1019, 367, 460, 42, max_length=250)
        kit.Button(board, 1153, 439, 216, 35, "Отправить заявку", self.send_request)

        board.shape(988, 528, 546, 310, 22, kit.PANEL_GRAY)
        board.label(937, 545, 291, "Мои заявки", "Bold", 20)
        board.add_wheel_area(988, 528, 546, 310, self.scroll_requests)
        self.refresh()

    def refresh_address(self):
        """Подставляет в шапку полный адрес, когда он оформлен (после очереди)."""
        self.board.itemconfigure(self.address_item, text=hoa.get_hoa()["address"])

    def refresh(self):
        """Обновляет долг, историю операций и список «Мои заявки»."""
        board = self.board
        board.clear_layer("data")
        board.set_layer("data")
        summary = finance.get_resident_summary(self.apartment["apartment_id"])
        board.label(-26, 187, 399, f"{money(summary['debt'])} руб.", "Medium", 36)
        board.label(550, 158, 400, f"Начислено: {money(summary['charged'])} руб.", "Light", 24)
        board.label(550, 199, 400, f"Оплачено: {money(summary['paid'])} руб.", "Light", 24)

        rows = []
        for index, (stamp, operation, purpose, amount) in enumerate(summary["history"]):
            shown = stamp if len(stamp) == 7 else date_only(stamp)
            sign = "+" if amount > 0 else ""
            rows.append((index, [shown, operation, purpose, sign + money(amount)], None))
        self.table.set_rows(rows)

        self.my_requests = list(
            requests_service.get_requests(apartment_id=self.apartment["apartment_id"])
        )
        self.requests_offset = min(self.requests_offset, max(0, len(self.my_requests) - 5))
        for position, row in enumerate(self.my_requests[self.requests_offset :][:5]):
            y = 597 + position * 44
            text = board.fit_text(f"№ {row['requests_id']}  * {row['title']}", "Regular", 16, 330)
            board.label(1010, y, 340, text, "Regular", 16, align="left")
            done = row["status"] == "Выполнена"
            is_new = row["status"] == "Новая"
            board.label(
                1314 if is_new else 1347,
                y - 3,
                187,
                row["status"].lower(),
                "Regular",
                24,
                kit.BLACK if done else "#0048ff",
            )
            if is_new:
                kit.IconButton(
                    board, 1466, y - 5, "trash", lambda r=row["requests_id"]: self.delete_request(r)
                )
        board.set_layer("base")

    def delete_request(self, request_id):
        """Спрашивает подтверждение и удаляет заявку жильца."""
        if not dialogs.ask_yes_no(self.board, f"Удалить заявку №{request_id}?"):
            return
        try:
            requests_service.delete_own_request(self.user["users_id"], request_id)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
        self.refresh()

    def scroll_requests(self, direction):
        """Прокручивает список «Мои заявки» колесом мыши."""
        maximum = max(0, len(self.my_requests) - 5)
        self.requests_offset = min(max(self.requests_offset + direction, 0), maximum)
        self.refresh()

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
        self.title_entry.clear()
        self.description.clear()
        self.requests_offset = 0
        self.refresh()
        dialogs.show_info(self.board, "Заявка отправлена.")
