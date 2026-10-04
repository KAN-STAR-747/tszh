"""Главное окно председателя: шапка, вкладки и их содержимое (кадры 10-13)."""

# filedialog - стандартное окно «Сохранить как...»
from tkinter import filedialog

# сервисы, из которых вкладки берут данные
from services import apartments, auth, dates, finance, hoa, reports, requests_service
from services import validation as check
from services.errors import AppError
from ui import dialogs, kit

# слои холста, которые стираются при смене вкладки
TAB_LAYERS = ("tab", "pending", "detail", "result")


# «Иванов Иван Иванович» -> «Иванов И.И.»
def short_name(full_name):
    """«Иванов Иван Иванович» -> «Иванов И.И.»."""
    # split() делит строку на слова
    parts = full_name.split()
    if not parts:
        return ""
    # фамилия + первые буквы имени и отчества
    return parts[0] + " " + "".join(part[0] + "." for part in parts[1:3])


# «2026-09-30 12:48» -> «30.09.2026» (берём куски строки по номерам символов)
def date_only(stamp):
    """«2026-09-30 12:48» -> «30.09.2026»."""
    return f"{stamp[8:10]}.{stamp[5:7]}.{stamp[0:4]}"


# то же, но с временем
def date_time(stamp):
    """«2026-09-30 12:48» -> «30.09.2026 12:48»."""
    return f"{date_only(stamp)} {stamp[11:16]}"


# Окно председателя: шапка и четыре вкладки
class MainScreen:
    """Окно председателя (размер 1588x919): шапка и четыре вкладки."""

    # размер кадра из Figma
    size = (1588, 919)
    title = "Система управления ТСЖ"
    # названия вкладок и их положение по x (из Figma)
    TAB_NAMES = ["Квартиры", "Заявки", "Финансы", "Отчёты"]
    TAB_X = [51, 204, 369, 534]
    # положение синей линии под активной вкладкой
    UNDERLINE_X = [62, 212, 379, 552]

    def __init__(self, app, board, user):
        """
        Args:
            app: главный объект программы.
            board: холст размером 1588x919.
            user (dict): вошедший председатель.
        """
        self.app = app
        self.board = board
        self.user = user
        # объект текущей вкладки
        self.tab = None
        self.current_index = 0

        # данные ТСЖ для заголовка
        info = hoa.get_hoa()
        # название ТСЖ и адрес в шапке
        board.label(-79, 20, 525, info["name"], "Bold", 32)
        board.label(26, 63, 382, info["address"], "ExtraLight", 20)
        board.label(
            988, 34, 291, f"{short_name(user['full_name'])}  *  Председатель", "Regular", 20
        )
        # кнопка «Выйти» возвращает на экран входа
        kit.Button(board, 1299, 31, 119, 35, "Выйти", app.show_login, "plain")
        # две горизонтальные линии шапки
        board.hline(0, 98, 1588)
        board.hline(0, 183, 1588)
        # сразу открываем первую вкладку
        self.show_tab(0)

    # Переключение вкладки: стираем старую и строим новую
    def show_tab(self, index):
        """Переключает вкладку и заново строит её содержимое."""
        board = self.board
        # стираем все слои предыдущей вкладки
        for layer in TAB_LAYERS + ("tabbar",):
            board.clear_layer(layer)
        self.current_index = index

        board.set_layer("tabbar")
        # рисуем названия вкладок
        for position, (name, x) in enumerate(zip(self.TAB_NAMES, self.TAB_X)):
            tag = f"tab_button{position}"
            board.label(x, 139, 153, name, "Regular", 24, tags=(tag,))
            # щелчок по названию - показать эту вкладку
            board.tag_bind(tag, "<ButtonRelease-1>", lambda e, i=position: self.show_tab(i))
            board.tag_bind(tag, "<Enter>", lambda e: board.configure(cursor="hand2"))
            board.tag_bind(tag, "<Leave>", lambda e: board.configure(cursor=""))
        # синяя линия под выбранной вкладкой
        underline_x = self.UNDERLINE_X[index]
        board.create_line(
            kit.S(underline_x),
            kit.S(175),
            kit.S(underline_x + 133),
            kit.S(175),
            fill="#006fff",
            width=kit.S(6),
            tags=("tabbar",),
        )
        # всё, что рисуем дальше, относится к слою вкладки
        board.set_layer("tab")
        # по номеру вкладки берём нужный класс и создаём его
        classes = [ApartmentsTab, RequestsTab, FinanceTab, ReportsTab]
        self.tab = classes[index](self)


# Вкладка «Квартиры»: таблица квартир и карточки жильцов на подтверждение
class ApartmentsTab:
    """Вкладка «Квартиры»: реестр квартир и жильцы, ожидающие подтверждения."""

    # Описание столбцов: заголовок, центр столбца (cx), шрифт, размер, максимальная ширина текста
    COLUMNS = [
        {"title": "Кв.", "cx": 37.5, "style": "Light", "size": 24, "width": 70},
        {"title": "Площадь, м2", "cx": 168.5, "style": "Light", "size": 24, "width": 150},
        {"title": "Собственник", "cx": 369.5, "style": "Light", "size": 20, "width": 250},
        {"title": "Телефон", "cx": 560.5, "style": "Light", "size": 20, "width": 170},
        {"title": "Член ТСЖ", "cx": 751.5, "style": "Light", "size": 20, "width": 150},
        {"title": "Долг, руб.", "cx": 933.5, "style": "Light", "size": 24, "width": 150},
    ]

    def __init__(self, screen):
        self.screen = screen
        # короткое имя board для холста
        self.board = board = screen.board
        # с какой карточки жильца показываем (прокрутка)
        self.pending_offset = 0

        # поле поиска
        self.search = kit.EntryBox(board, 26, 229, 264, 36, placeholder="Поиск по номеру или ФИО")
        # при каждом вводе буквы обновляем таблицу
        self.search.on_change(self.refresh_table)
        # галочка «Только члены ТСЖ»
        self.members = kit.CheckBox(board, 333, 235, command=self.refresh_table)
        board.label(368, 233, 243, "Только члены ТСЖ", "Regular", 24)
        # кнопки: добавить, изменить, удалить
        kit.Button(board, 676, 230, 127, 35, "Добавить", self.add)
        kit.Button(board, 823, 230, 119, 35, "Изменить", self.edit, "plain")
        kit.Button(board, 962, 230, 119, 35, "Удалить", self.delete, "plain")

        # таблица квартир
        self.table = kit.Table(board, 26, 294, 1055, 433, self.COLUMNS)
        # строка итогов под таблицей
        self.footer = board.label(13, 743, 350, "", "ExtraLight", 20)
        # серая панель справа для жильцов на подтверждение
        board.shape(1102, 294, 445, 433, 22, kit.PANEL_GRAY)
        self.refresh_table()
        self.refresh_pending()

    # Заполняет таблицу с учётом поиска и галочки
    def refresh_table(self):
        """Заполняет таблицу с учётом поиска и фильтра «Только члены ТСЖ»."""
        # данные из сервиса
        rows = apartments.get_apartments(self.search.get(), self.members.get())
        table = []
        for row in rows:
            # значения ячеек строки в порядке столбцов
            values = [
                row["number"],
                f"{row['area']:g}",
                row["owner_name"],
                row["owner_phone"],
                "Да" if row["is_member"] else "Нет",
                check.kopecks_to_text(row["debt"]),
            ]
            # строки с долгом подсвечиваем
            tint = kit.DEBT_TINT if row["debt"] > 0 else None
            # строка таблицы: (ключ, значения, цвет)
            table.append((row["apartment_id"], values, tint))
        self.table.set_rows(table)
        # итоги под таблицей
        total, members = apartments.get_summary()
        self.board.itemconfigure(
            self.footer, text=f"Всего квартир: {total} * Членов ТСЖ: {members}"
        )

    # Перерисовка карточек жильцов, которые ждут подтверждения
    def refresh_pending(self):
        """Перерисовывает карточки жильцов, ожидающих подтверждения."""
        board = self.board
        board.clear_layer("pending")
        board.set_layer("pending")
        # список жильцов из базы
        pending = list(auth.get_pending_residents())
        board.label(1102, 304, 445, f"Ожидают подтверждения ({len(pending)})", "Bold", 20)
        self.pending_offset = min(self.pending_offset, max(0, len(pending) - 2))

        # показываем не больше двух карточек сразу
        for position, resident in enumerate(pending[self.pending_offset :][:2]):
            # вторая карточка ниже первой на 143 пикселя
            y = 367 + position * 143
            # белая карточка с тенью
            board.shape(1121, y, 407, 113, 15, kit.WHITE, shadows=kit.CARD_SHADOW)
            board.label(1137, y + 6, 300, resident["full_name"], "Light", 20, align="left")
            board.label(
                1137,
                y + 33,
                380,
                f"Кв. {resident['number']} * {resident['phone']}",
                "Light",
                20,
                align="left",
            )
            # id жильца нужен кнопкам
            user_id = resident["users_id"]
            kit.Button(
                board, 1395, y + 69, 106, 35, "Принять", lambda u=user_id: self.decide(u, True)
            )
            kit.Button(
                board,
                1280,
                y + 69,
                103,
                35,
                "Отклонить",
                lambda u=user_id: self.decide(u, False),
                "plain",
            )
        # колесо мыши листает карточки
        board.add_wheel_area(1102, 294, 445, 433, lambda d: self.scroll_pending(d, len(pending)))
        board.set_layer("tab")

    # Прокрутка списка карточек
    def scroll_pending(self, direction, count):
        """Прокручивает список ожидающих жильцов колесом мыши."""
        self.pending_offset = min(max(self.pending_offset + direction, 0), max(0, count - 2))
        self.refresh_pending()

    # Принять (accept=True) или отклонить жильца
    def decide(self, user_id, accept):
        """Подтверждает или отклоняет жильца."""
        if accept:
            auth.approve_resident(user_id)
        else:
            auth.reject_resident(user_id)
        self.refresh_pending()

    # id выбранной строки таблицы; если ничего не выбрано - подсказка
    def selected_id(self):
        """id выбранной квартиры или None (с подсказкой)."""
        if self.table.selected_key is None:
            dialogs.show_info(self.board, "Сначала выберите квартиру в таблице.")
        return self.table.selected_key

    # Кнопка «Добавить»: открываем окно новой квартиры
    def add(self):
        """Открывает окно добавления квартиры."""
        dialogs.ApartmentDialog(self.board, self.after_change)

    # Кнопка «Изменить»: окно с данными выбранной квартиры
    def edit(self):
        """Открывает окно изменения выбранной квартиры."""
        apartment_id = self.selected_id()
        if apartment_id is not None:
            dialogs.ApartmentDialog(self.board, self.after_change, apartment_id)

    # Окно сообщит, что данные сохранены, - обновляем таблицу
    def after_change(self):
        """Обновляет таблицу после сохранения квартиры."""
        self.refresh_table()

    # Кнопка «Удалить»: сначала спрашиваем подтверждение
    def delete(self):
        """Удаляет выбранную квартиру после подтверждения."""
        apartment_id = self.selected_id()
        if apartment_id is None:
            return
        number = apartments.get_apartment(apartment_id)["number"]
        # ответ «Нет» - ничего не делаем
        if not dialogs.ask_yes_no(self.board, f"Удалить квартиру {number}?"):
            return
        try:
            apartments.delete_apartment(apartment_id)
        except AppError as error:
            # если у квартиры есть данные, сервис откажет - показываем причину
            dialogs.show_error(self.board, str(error), "Удаление невозможно")
            return
        self.refresh_table()


# Вкладка «Заявки»: таблица заявок и карточка выбранной
class RequestsTab:
    """Вкладка «Заявки»: список заявок и карточка выбранной заявки."""

    COLUMNS = [
        {"title": "№", "cx": 37.5, "style": "Light", "size": 24, "width": 70},
        {"title": "Дата", "cx": 168.5, "style": "Light", "size": 20, "width": 150},
        {"title": "Тема", "cx": 369.5, "style": "Light", "size": 20, "width": 250},
        {"title": "Кв.", "cx": 604.5, "style": "Light", "size": 20, "width": 80},
        {"title": "Источник", "cx": 751.5, "style": "Light", "size": 20, "width": 160},
        {"title": "Статус", "cx": 933.5, "style": "Light", "size": 24, "width": 150},
    ]

    def __init__(self, screen):
        self.screen = screen
        self.board = board = screen.board
        self.user = screen.user
        # какая заявка сейчас выбрана
        self.request_id = None

        board.label(44, 230, 112, "Статус:", "Regular", 24)
        # фильтр по статусу
        self.status_box = kit.DropBox(
            board,
            156,
            229,
            149,
            42,
            ["Все"] + requests_service.STATUSES,
            command=self.refresh_table,
            size=16,
        )
        # создание заявки
        kit.Button(board, 893, 230, 159, 35, "Новая заявка", self.add)
        # on_select - при щелчке по строке показываем карточку
        self.table = kit.Table(board, 26, 294, 1055, 433, self.COLUMNS, on_select=self.show_details)
        board.shape(1102, 294, 445, 595, 22, kit.PANEL_GRAY)
        self.refresh_table()
        # пока ничего не выбрано
        self.show_details(None)

    def refresh_table(self):
        """Заполняет таблицу с учётом выбранного статуса."""
        # выбранный статус
        status = self.status_box.get()
        # None означает «все статусы»
        rows = requests_service.get_requests(None if status == "Все" else status)
        table = []
        for row in rows:
            values = [
                row["requests_id"],
                date_only(row["created_at"]),
                row["title"],
                # нет квартиры - ставим прочерк
                row["apartment_number"] or "-",
                row["source"],
                row["status"],
            ]
            # новые заявки подсвечены жёлтым
            tint = kit.NEW_TINT if row["status"] == "Новая" else None
            table.append((row["requests_id"], values, tint))
        self.table.set_rows(table)
        if self.request_id in [row[0] for row in table]:
            self.table.select(self.request_id)

    def add(self):
        """Открывает окно создания заявки."""
        dialogs.RequestDialog(self.board, self.user, self.refresh_table)

    # Строим карточку заявки справа
    def show_details(self, request_id):
        """Строит карточку заявки на правой панели."""
        board = self.board
        board.clear_layer("detail")
        board.set_layer("detail")
        self.request_id = request_id
        if request_id is None:
            board.label(1102, 320, 445, "Выберите заявку в таблице", "ExtraLight", 20)
            board.set_layer("tab")
            return
        # данные выбранной заявки
        request = requests_service.get_request(request_id)
        board.label(
            1108,
            304,
            382,
            f"Заявка №{request['requests_id']} * создана " f"{date_time(request['created_at'])}",
            "ExtraLight",
            20,
        )
        # длинную тему обрезаем
        title = board.fit_text(request["title"], "Bold", 20, 400)
        board.label(1062, 329, 291, title, "Bold", 20)

        # три строки «название - значение»: квартира, источник, автор
        for y, name, value in [
            (390, "Квартира", request["apartment_number"] or "Общедомовое"),
            (425, "Источник", request["source"]),
            (461, "Автор", short_name(request["author_name"] or "")),
        ]:
            board.label(1130, y, 200, name, "Light", 20, align="left")
            board.label(1310, y, 200, value, "Light", 20, align="right")

        # белая рамка под описание
        board.shape(1115, 505, 404, 96, 22, kit.WHITE)
        description = request["description"] or "Описание не указано"
        # длинное описание сокращаем
        if len(description) > 110:
            description = description[:107] + "..."
        board.label(1124, 519, 385, description, "Light", 20, wrap=True)

        board.label(1100, 609, 191, "Исполнитель", "Bold", 20)
        # поле исполнителя
        self.executor = kit.EntryBox(board, 1124, 652, 405, 44, text=request["executor"] or "")
        board.label(1078, 704, 191, "Статус", "Bold", 20)
        # строка статусов со стрелками
        self.draw_status_line(request["status"])

        # кнопка зависит от следующего статуса
        next_status = requests_service.get_next_status(request["status"])
        if next_status == "Выполнена":
            kit.Button(board, 1229, 790, 216, 35, "Отметить выполненной", self.change_status)
        elif next_status:
            kit.Button(board, 1229, 790, 216, 35, "Взять в работу", self.change_status)
        # у выполненной заявки показываем дату закрытия
        if request["closed_at"]:
            closed = f"Закрыта: {date_time(request['closed_at'])}"
            board.label(1102, 795, 445, closed, "Light", 20)
        kit.Button(board, 1229, 834, 216, 35, "Сохранить исполнителя", self.save_executor, "plain")
        board.set_layer("tab")

    # «Новая -> В работе -> Выполнена», текущий статус оранжевый и жирный
    def draw_status_line(self, current):
        """Строка «Новая → В работе → Выполнена» с выделением текущего статуса."""
        board = self.board
        # положение каждого статуса: x и ширина
        boxes = [(1118, 97), (1242, 97), (1358, 138)]
        for (x, w), name in zip(boxes, requests_service.STATUSES):
            if name == current:
                board.label(x, 738, w, name, "Bold", 20, kit.STATUS_ORANGE)
            else:
                board.label(x, 738, w, name, "ExtraLight", 20)
        # две стрелки между статусами
        for x, w in [(1204, 26), (1339, 27)]:
            board.create_line(
                kit.S(x),
                kit.S(756),
                kit.S(x + w),
                kit.S(756),
                fill=kit.BLACK,
                width=kit.S(2),
                arrow="last",
                arrowshape=(kit.S(9), kit.S(11), kit.S(4)),
                tags=("detail",),
            )

    # Перевод в следующий статус
    def change_status(self):
        """Переводит заявку в следующий статус."""
        try:
            # сервис меняет статус и ставит дату закрытия
            requests_service.move_to_next_status(self.request_id)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
        request_id = self.request_id
        self.refresh_table()
        self.show_details(request_id)

    # Запись исполнителя в заявку
    def save_executor(self):
        """Сохраняет исполнителя заявки."""
        requests_service.set_executor(self.request_id, self.executor.get())
        dialogs.show_info(self.board, "Исполнитель сохранён.")


# Вкладка «Финансы»: таблица за месяц и форма внесения оплаты
class FinanceTab:
    """Вкладка «Финансы»: начисления за месяц и форма внесения оплаты."""

    COLUMNS = [
        {"title": "Кв.", "cx": 37.5, "style": "Light", "size": 24, "width": 70},
        {"title": "Собственник", "cx": 168.5, "style": "Light", "size": 20, "width": 200},
        {"title": "Начислено, руб.", "cx": 399, "style": "Light", "size": 24, "width": 200},
        {"title": "Оплачено, руб.", "cx": 632, "style": "Light", "size": 24, "width": 200},
        {"title": "Долг, руб.", "cx": 933.5, "style": "Light", "size": 24, "width": 200},
    ]

    def __init__(self, screen):
        self.screen = screen
        self.board = board = screen.board
        # месяцы для выпадающего списка
        self.months = dates.get_month_list()

        board.label(44, 228, 112, "Месяц:", "Regular", 24)
        # выбор месяца; при смене обновляется таблица
        self.month_box = kit.DropBox(
            board,
            156,
            227,
            237,
            42,
            [dates.month_to_text(m) for m in self.months],
            index=self.months.index(dates.current_month()),
            command=self.refresh_table,
            size=16,
        )
        # начисление за месяц и целевой сбор
        kit.Button(board, 432, 228, 188, 35, "Начислить за месяц", self.charge_month)
        kit.Button(board, 642, 228, 149, 35, "Целевой сбор", self.open_target, "plain")
        # тариф из данных ТСЖ
        tariff = check.kopecks_to_text(hoa.get_tariff())
        board.label(836, 225, 216, f"Тариф {tariff} руб./м2", "ExtraLight", 20)

        self.table = kit.Table(board, 26, 292, 1055, 433, self.COLUMNS)
        # правая панель оплаты
        self.build_payment_panel()
        self.refresh_table()

    # Правая панель «Внести оплату»
    def build_payment_panel(self):
        """Правая панель «Внести оплату»."""
        board = self.board
        board.shape(1102, 292, 445, 503, 22, kit.PANEL_GRAY)
        board.label(1062, 327, 291, "Внести оплату", "Bold", 20)
        rows = list(apartments.get_apartments())
        # id квартир в том же порядке, что и строки списка
        self.apartment_ids = [row["apartment_id"] for row in rows]
        board.label(1107, 368, 145, "Квартира", "Regular", 16)
        # выбор квартиры
        self.payment_apartment = kit.DropBox(
            board,
            1135,
            397,
            355,
            42,
            [f"{row['number']} * {short_name(row['owner_name'])}" for row in rows],
            index=0,
        )
        board.label(1107, 443, 167, "Сумма, руб.", "Regular", 16)
        self.payment_amount = kit.EntryBox(board, 1135, 472, 355, 42)
        board.label(1107, 526, 180, "Дата оплаты", "Regular", 16)
        # дата по умолчанию - сегодня
        self.payment_date = kit.EntryBox(board, 1135, 555, 355, 42, text=dates.today_text())
        board.label(1107, 608, 180, "Комментарий", "Regular", 16)
        self.payment_comment = kit.EntryBox(board, 1135, 637, 355, 42)
        # сохранение оплаты
        kit.Button(board, 1218, 725, 216, 35, "Сохранить оплату", self.save_payment)

    def refresh_table(self):
        """Заполняет таблицу данными за выбранный месяц."""
        # месяц из выбранного пункта списка
        month = self.months[self.month_box.index]
        # данные за месяц
        rows = finance.get_month_table(month)
        table = []
        for row in rows:
            values = [
                row["number"],
                short_name(row["owner_name"]),
                check.kopecks_to_text(row["charged"]),
                check.kopecks_to_text(row["paid"]),
                check.kopecks_to_text(row["debt"]),
            ]
            tint = kit.DEBT_TINT if row["debt"] > 0 else None
            table.append((row["apartment_id"], values, tint))
        self.table.set_rows(table)

    # Начисление за месяц с вопросом
    def charge_month(self):
        """Начисляет плату за месяц после подтверждения."""
        month = self.months[self.month_box.index]
        try:
            tariff = check.kopecks_to_text(hoa.get_tariff()).replace(".", ",")
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        # сколько квартир получат начисление
        count = len(finance.get_apartments_for_charge())
        # текст вопроса
        question = (
            f"Начислить плату за {dates.month_to_text(month).lower()}?\n"
            f"Будет создано {count} {dialogs.charges_word(count)} "
            f"по тарифу {tariff} руб./м2"
        )
        if not dialogs.ask_yes_no(self.board, question):
            return
        try:
            # создаём начисления
            finance.charge_month(month)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        self.refresh_table()

    # Окно целевого сбора
    def open_target(self):
        """Открывает окно целевого сбора."""
        dialogs.TargetChargeDialog(self.board, self.refresh_table)

    # Внесение оплаты: данные берём из полей панели
    def save_payment(self):
        """Вносит оплату по выбранной квартире."""
        index = self.payment_apartment.index
        apartment_id = self.apartment_ids[index] if index >= 0 else None
        try:
            finance.add_payment(
                apartment_id,
                self.payment_amount.get(),
                self.payment_date.get(),
                self.payment_comment.get(),
            )
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        # после сохранения очищаем сумму и комментарий
        self.payment_amount.clear()
        self.payment_comment.clear()
        self.refresh_table()
        dialogs.show_info(self.board, "Оплата внесена.")


# Вкладка «Отчёты»: три панели с кнопкой «Выгрузить в Excel»
class ReportsTab:
    """Вкладка «Отчёты»: три отчёта с выгрузкой в Excel."""

    def __init__(self, screen):
        self.screen = screen
        self.board = board = screen.board

        # три серые панели
        for x, y, h in [(51, 242, 307), (576, 242, 307), (1101, 239, 310)]:
            board.shape(x, y, 445, h, 22, kit.PANEL_GRAY)

        # отчёт 1: должники
        board.label(-10, 262, 291, "Должники", "Bold", 20)
        board.label(
            110,
            320,
            328,
            "Квартиры с долгом на текущую дату: номер, собственник, " "телефон, сумма долга.",
            "Regular",
            16,
            wrap=True,
        )
        kit.Button(
            board,
            153,
            497,
            216,
            35,
            "Выгрузить в Excel",
            lambda: self.export("Должники", reports.export_debtors),
        )

        # отчёт 2: заявки за период
        board.label(552, 262, 291, "Заявки за период", "Bold", 20)
        board.label(
            635,
            295,
            328,
            "Тема, квартира, источник, статус, исполнитель, даты создания и закрытия.",
            "Regular",
            16,
            wrap=True,
        )
        board.label(651, 408, 56, "с", "Medium", 20)
        # поля дат: «с» - начало месяца, «по» - сегодня
        self.date_from = kit.EntryBox(board, 635, 438, 149, 42, text=dates.month_start_text())
        board.label(843, 408, 51, "по", "Medium", 20)
        self.date_to = kit.EntryBox(board, 831, 438, 149, 42, text=dates.today_text())
        kit.Button(
            board,
            707,
            495,
            216,
            35,
            "Выгрузить в Excel",
            lambda: self.export("Заявки", self.export_requests),
        )

        # отчёт 3: реестр членов ТСЖ
        board.label(1083, 256, 291, "Реестр членов ТСЖ", "Bold", 20)
        board.label(
            1163,
            290,
            328,
            "Квартиры, собственники которых - члены ТСЖ: номер, ФИО, телефон, площадь.",
            "Regular",
            16,
            wrap=True,
        )
        # для строки «N членов из M собственников»
        total, members = apartments.get_summary()
        # правильное окончание слова
        member_word = dates.plural(members, "член", "члена", "членов")
        owner_word = dates.plural(total, "собственника", "собственников", "собственников")
        board.label(
            1110, 386, 328, f"{members} {member_word} из {total} {owner_word}", "Regular", 16
        )
        kit.Button(
            board,
            1219,
            495,
            216,
            35,
            "Выгрузить в Excel",
            lambda: self.export("Члены_ТСЖ", reports.export_members),
        )

    # Отчёт по заявкам берёт даты из двух полей
    def export_requests(self, file_path):
        """Выгружает заявки за период из полей «с» и «по»."""
        return reports.export_requests(file_path, self.date_from.get(), self.date_to.get())

    # Общая выгрузка: спрашиваем, куда сохранить, и вызываем нужную функцию отчёта
    def export(self, prefix, export_function):
        """Спрашивает, куда сохранить файл, и запускает выгрузку."""
        # окно «Сохранить как»
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=reports.default_file_name(prefix),
            filetypes=[("Файлы Excel", "*.xlsx")],
        )
        # пользователь нажал «Отмена»
        if not file_path:
            return
        try:
            export_function(file_path)
        except AppError as error:
            dialogs.show_error(self.board, str(error))
            return
        # файл открыт в Excel - Windows не даёт его перезаписать
        except PermissionError:
            dialogs.show_error(
                self.board,
                "Не удалось сохранить файл. Если он открыт в Excel, " "закройте его и повторите.",
            )
            return
        self.show_result(file_path)

    # Плашка «Файл сохранён» под панелями
    def show_result(self, file_path):
        """Плашка «Файл сохранён» внизу окна."""
        board = self.board
        board.clear_layer("result")
        board.set_layer("result")
        text = board.fit_text(f"Файл сохранён: {file_path}", "Medium", 12, 520)
        kit.note(board, 51, 584, 564, 51, text, "info")
        board.set_layer("tab")
