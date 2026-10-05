"""Элементы интерфейса, нарисованные по макету Figma.

Все размеры и координаты здесь задаются в «пикселях макета» (как в Figma).
Функция S() переводит их в пиксели экрана с учётом масштаба K, поэтому окно
выглядит как макет на любом мониторе.

Скруглённые фигуры и тени рисует библиотека Pillow, потом они кладутся на холст
Tkinter как картинки. Текст, поля ввода и таблицы - обычные средства Tkinter.
"""

import ctypes
import math
import os
import sys
import tkinter as tk

from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageFilter, ImageTk

BLUE = "#0088ff"
BLUE_HOVER = "#0072d6"
WHITE = "#ffffff"
BLACK = "#000000"
PANEL_GRAY = "#f3f3f3"
PANEL_BLUE = "#ebf5ff"
NOTE_BLUE = "#9ed0ff"
NOTE_BLUE_TEXT = "#3f6fa3"
NOTE_RED = "#ff9e9e"
NOTE_RED_TEXT = "#993838"
DEBT_TINT = "#ffe1d1"
NEW_TINT = "#fff2b8"
SELECT_TINT = "#d9e8ff"
PLACEHOLDER = "#8e8e93"
STATUS_ORANGE = "#ffa100"


BUTTON_SHADOW = ((0, 1, 3, 0, (0, 0, 0, 0.30)), (0, 4, 8, 3, (0, 0, 0, 0.15)))
CARD_SHADOW = ((0, 0, 18, 0, (0, 0, 0, 0.25)),)


MAX_WINDOW = (1588, 919)

K = 1.0

SUPER = 4
_cache = {}


def S(value):
    """Пиксели макета -> пиксели экрана."""

    return int(round(value * K))


def line_width(value=1):
    """Толщина линии на экране (не меньше 1 пикселя)."""
    return max(1, S(value))


def enable_high_dpi():
    """Чёткое отображение на экранах с масштабом больше 100%. Вызвать до создания окна."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def init_scale(root):
    """Выбирает масштаб K так, чтобы самое большое окно помещалось на экран."""
    global K
    system_scale = root.winfo_fpixels("1i") / 96
    fit_width = (root.winfo_screenwidth() - 40) / MAX_WINDOW[0]
    fit_height = (root.winfo_screenheight() - 150) / MAX_WINDOW[1]
    K = max(0.5, min(system_scale, fit_width, fit_height, 1.6))
    _cache.clear()


FONT_FILES = ["Roboto-Light.ttf", "Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf"]
FONT_FAMILIES = {
    "ExtraLight": ("Roboto Light", "normal"),
    "Light": ("Roboto Light", "normal"),
    "Regular": ("Roboto", "normal"),
    "Medium": ("Roboto Medium", "normal"),
    "Bold": ("Roboto", "bold"),
}


def resource_path(relative_path):
    """Путь к файлу проекта (работает и в собранном exe)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def load_fonts():
    """Подключает файлы Roboto из папки fonts на время работы программы."""
    try:
        add_font = ctypes.windll.gdi32.AddFontResourceExW
    except AttributeError:
        return
    for name in FONT_FILES:
        add_font(resource_path(os.path.join("fonts", name)), 0x10, 0)  # 0x10 - только для нас


def font(style, size):
    """Шрифт Tk по начертанию Figma и размеру макета. Отрицательный размер = пиксели."""
    family, weight = FONT_FAMILIES[style]
    pixels = -max(S(size), 1)
    return (family, pixels, "bold") if weight == "bold" else (family, pixels)


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def scaled(shadows):
    """Параметры теней из пикселей макета в пиксели экрана."""
    return tuple((round(x * K), round(y * K), b * K, round(s * K), c) for x, y, b, s, c in shadows)


def shape_image(w, h, radius, fill, outline=None, outline_w=1, shadows=()):
    """Скруглённый прямоугольник с обводкой и тенями. Размеры - в пикселях экрана.

    Returns:
        tuple: (картинка, отступ под тень вокруг фигуры).
    """
    key = (w, h, radius, fill, outline, outline_w, shadows)
    if key in _cache:
        return _cache[key]

    pad = max([int(b * 1.6 + s + max(abs(x), abs(y)) + 2) for x, y, b, s, _ in shadows] or [0])
    size = ((w + 2 * pad) * SUPER, (h + 2 * pad) * SUPER)
    image = Image.new("RGBA", size, (0, 0, 0, 0))

    for x, y, blur, spread, (r, g, b, alpha) in shadows:  # тени: размытая маска
        mask = Image.new("L", size, 0)
        box = ((pad + x - spread) * SUPER, (pad + y - spread) * SUPER)
        box += ((pad + x + w + spread) * SUPER - 1, (pad + y + h + spread) * SUPER - 1)
        ImageDraw.Draw(mask).rounded_rectangle(
            box, (radius + spread) * SUPER, fill=int(255 * alpha)
        )
        mask = mask.filter(ImageFilter.GaussianBlur(max(blur, 0.1) * SUPER / 2))
        layer = Image.new("RGBA", size, (r, g, b, 0))
        layer.putalpha(mask)
        image = Image.alpha_composite(image, layer)

    draw = ImageDraw.Draw(image)
    box = (pad * SUPER, pad * SUPER, (pad + w) * SUPER - 1, (pad + h) * SUPER - 1)
    if outline:
        draw.rounded_rectangle(box, radius * SUPER, fill=_rgb(outline))
        d = outline_w * SUPER
        inner = (box[0] + d, box[1] + d, box[2] - d, box[3] - d)
        draw.rounded_rectangle(inner, max(radius - outline_w, 0) * SUPER, fill=_rgb(fill))
    else:
        draw.rounded_rectangle(box, radius * SUPER, fill=_rgb(fill))

    # уменьшаем до нужного размера (так получается сглаживание) и кладём в кэш
    result = (ImageTk.PhotoImage(image.resize((w + 2 * pad, h + 2 * pad), Image.LANCZOS)), pad)
    _cache[key] = result
    return result


# Рисует сглаженную ломаную линию: стрелку списка и галочку
def line_image(size, points, color, width):
    """Сглаженная ломаная линия (стрелка вниз, галочка). points - в пикселях экрана."""
    key = ("line", size, tuple(points), color, width)
    if key not in _cache:
        image = Image.new("RGBA", (size[0] * SUPER, size[1] * SUPER), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        big = [(x * SUPER, y * SUPER) for x, y in points]
        draw.line(big, fill=_rgb(color), width=int(width * SUPER), joint="curve")
        r = width * SUPER / 2
        for x, y in (big[0], big[-1]):  # круглые концы
            draw.ellipse((x - r, y - r, x + r, y + r), fill=_rgb(color))
        _cache[key] = ImageTk.PhotoImage(image.resize(size, Image.LANCZOS))
    return _cache[key]


# ======================================================================
# ЧАСТЬ 3. Холст Board: окно макета фиксированного размера
# ======================================================================


# Board - холст (Canvas): на нём рисуется одно окно макета
class Board(tk.Canvas):
    """Холст, на котором рисуется одно окно макета (координаты - как в Figma).

    Все элементы относятся к «слою» (например, к вкладке). Слой можно очистить целиком.
    """

    def __init__(self, parent, width, height):
        super().__init__(parent, width=S(width), height=S(height), bg=WHITE, highlightthickness=0)
        # слой - метка (тег) элементов; слой можно стереть целиком
        self.layer = "base"
        # поля ввода тоже относятся к слою
        self.layer_widgets = {}  # слой -> поля ввода, которые нужно удалить вместе со слоем
        # области, которые листаются колесом мыши
        self.wheel_areas = []  # области, прокручиваемые колесом мыши
        # счётчик, чтобы у каждой кнопки был свой тег
        self.counter = 0  # для уникальных тегов кнопок
        # реагируем на колесо мыши
        self.bind("<MouseWheel>", self._on_wheel)

    # все элементы, созданные после этого, попадут в слой name
    def set_layer(self, name):
        """Все элементы, созданные дальше, попадут в слой name."""
        self.layer = name

    def clear_layer(self, name):
        """Удаляет с холста слой целиком (рисунки, тексты, поля ввода)."""
        # удаляем с холста всё, что помечено этим тегом
        self.delete(name)
        # и уничтожаем поля ввода слоя
        for widget in self.layer_widgets.pop(name, []):
            widget.destroy()
        self.wheel_areas = [area for area in self.wheel_areas if area[0] != name]

    # запоминаем поле ввода в текущем слое
    def add_widget(self, widget):
        """Запоминает поле ввода, чтобы удалить его вместе со слоем."""
        self.layer_widgets.setdefault(self.layer, []).append(widget)

    # даёт уникальный тег: button1, button2...
    def new_tag(self, prefix):
        """Уникальный тег для группы элементов (чтобы повесить на неё щелчок)."""
        self.counter += 1
        return f"{prefix}{self.counter}"

    # Фигура-подложка (панель, плашка): рисуем картинку и кладём на холст
    def shape(self, x, y, w, h, radius, fill, outline=None, shadows=(), tags=()):
        """Скруглённый прямоугольник (панель, плашка, фон поля)."""
        image, pad = shape_image(
            S(w), S(h), S(radius), fill, outline, line_width(1), scaled(shadows)
        )
        return self.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=image, tags=(self.layer, *tags)
        )

    # Надпись: x, y, ширина, текст, начертание Figma, размер, цвет, выравнивание
    def label(self, x, y, w, text, style, size, color=BLACK, align="center", wrap=False, tags=()):
        """Надпись в рамке макета (x, y, ширина w). align: center, left или right."""
        # от выравнивания зависит, к какой точке привязан текст
        px, anchor = {"center": (x + w / 2, "n"), "left": (x, "nw"), "right": (x + w, "ne")}[align]
        return self.create_text(
            S(px),
            S(y),
            text=text,
            font=font(style, size),
            fill=color,
            anchor=anchor,
            justify=align,
            width=S(w) if wrap else 0,
            tags=(self.layer, *tags),
        )

    # Надпись по центру прямоугольника
    def centered(self, x, y, w, h, text, style, size, color=BLACK, tags=()):
        """Однострочная надпись по центру прямоугольника."""
        return self.create_text(
            S(x + w / 2),
            S(y + h / 2),
            text=text,
            font=font(style, size),
            fill=color,
            anchor="center",
            tags=(self.layer, *tags),
        )

    # Горизонтальная линия
    def hline(self, x, y, w, color=BLACK, width=1, tags=()):
        """Горизонтальная линия."""
        return self.create_line(
            S(x),
            S(y),
            S(x + w),
            S(y),
            fill=color,
            width=line_width(width),
            tags=(self.layer, *tags),
        )

    # Если текст не влезает в ширину - обрезаем и добавляем «…»
    def fit_text(self, text, style, size, max_width):
        """Обрезает текст многоточием, если он не помещается в max_width."""
        # объект для измерения ширины текста
        measure = tkfont.Font(font=font(style, size))
        if measure.measure(text) <= S(max_width):
            return text
        while text and measure.measure(text + "…") > S(max_width):
            text = text[:-1]
        return text + "…"

    # Запоминаем область, которая листается колесом
    def add_wheel_area(self, x, y, w, h, callback):
        """Область, которая прокручивается колесом мыши (callback получает -1 или 1)."""
        self.wheel_areas.append((self.layer, S(x), S(y), S(x + w), S(y + h), callback))

    # при прокрутке ищем область под курсором и вызываем её функцию
    def _on_wheel(self, event):
        for _, x0, y0, x1, y1, callback in self.wheel_areas:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                callback(-1 if event.delta > 0 else 1)
                return

    # Над элементом курсор мыши меняется на «руку»
    def hover_cursor(self, tag):
        """Над элементами с этим тегом курсор становится «рукой»."""
        self.tag_bind(tag, "<Enter>", lambda e: self.configure(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda e: self.configure(cursor=""))


# Плашка с сообщением: голубая (info) или красная (error)
def note(board, x, y, w, h, text, kind="info"):
    """Цветная плашка с сообщением: "info" (голубая) или "error" (красная).

    Returns:
        int: номер текста на холсте (чтобы потом изменить надпись).
    """
    # выбираем цвета по виду плашки
    fill, color = (NOTE_RED, NOTE_RED_TEXT) if kind == "error" else (NOTE_BLUE, NOTE_BLUE_TEXT)
    board.shape(x, y, w, h, 8, fill, BLACK)
    return board.create_text(
        S(x + w / 2),
        S(y + h / 2),
        text=text,
        font=font("Medium", 14),
        fill=color,
        justify="center",
        width=S(w - 24),
        tags=(board.layer,),
    )


# ======================================================================
# ЧАСТЬ 4. Кнопка и ссылка
# ======================================================================


# Кнопка. Обычная кнопка Tkinter не умеет скруглений: наша - картинка + текст на холсте
class Button:
    """Кнопка-«таблетка» из макета: синяя ("primary") или белая ("plain")."""

    def __init__(self, board, x, y, w, h, text, command, kind="primary", size=16):
        # primary - синяя кнопка, иначе белая
        primary = kind == "primary"
        # тень кнопки из Figma
        shadow = scaled(BUTTON_SHADOW)
        # картинка кнопки в обычном состоянии
        self.normal, pad = shape_image(
            S(w), S(h), S(16), BLUE if primary else WHITE, None, 1, shadow
        )
        # и чуть темнее - когда мышь над кнопкой
        self.hover, _ = shape_image(
            S(w), S(h), S(16), BLUE_HOVER if primary else "#ececec", None, 1, shadow
        )
        self.board, self.command = board, command
        # общий тег: картинка и текст кнопки реагируют на мышь вместе
        tag = board.new_tag("button")
        # кладём картинку кнопки на холст
        self.image_id = board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=self.normal, tags=(board.layer, tag)
        )
        # текст на кнопке
        board.create_text(
            S(x + w / 2),
            S(y + h / 2),
            text=text,
            font=font("Medium", size),
            fill=WHITE if primary else BLACK,
            tags=(board.layer, tag),
        )
        # рука над кнопкой
        board.hover_cursor(tag)
        # мышь вошла - светлее; мышь ушла - обычная; отпустили кнопку - вызываем функцию
        board.tag_bind(
            tag, "<Enter>", lambda e: board.itemconfigure(self.image_id, image=self.hover), "+"
        )
        board.tag_bind(
            tag, "<Leave>", lambda e: board.itemconfigure(self.image_id, image=self.normal), "+"
        )
        board.tag_bind(tag, "<ButtonRelease-1>", lambda e: self.command())


# Ссылка: синий текст, по щелчку вызывает command
def link(board, x, y, w, text, command, size=14):
    """Синяя ссылка-текст (например, «зарегистрироваться»)."""
    tag = board.new_tag("link")
    board.label(x, y, w, text, "Medium", size, BLUE, tags=(tag,))
    board.hover_cursor(tag)
    board.tag_bind(tag, "<ButtonRelease-1>", lambda e: command())


# ======================================================================
# ЧАСТЬ 5. Поля ввода
# ======================================================================


# Рамка поля ввода: обычная и с синей обводкой, когда в поле курсор
def _chip_images(w, h):
    """Две картинки рамки поля: обычная и с синей обводкой (когда в поле курсор)."""
    normal, pad = shape_image(S(w), S(h), S(8), WHITE, BLACK, line_width(1))
    focused, _ = shape_image(S(w), S(h), S(8), WHITE, BLUE, line_width(2))
    return normal, focused, pad


# Поле ввода: обычный tk.Entry, положенный на картинку скруглённой рамки
class EntryBox:
    """Однострочное поле ввода в скруглённой рамке (в Figma - «Assistive chip»)."""

    def __init__(
        self,
        board,
        x,
        y,
        w,
        h,
        show="",
        text="",
        placeholder="",
        size=12,
        max_length=None,
        readonly=False,
    ):
        """show - символ вместо букв (для пароля), placeholder - серая подсказка,
        max_length - наибольшая длина текста, readonly - поле нельзя менять."""
        # запоминаем параметры
        self.board, self.placeholder, self.show_char = board, placeholder, show
        self.max_length = max_length
        # показана ли серая подсказка вместо текста
        self.showing_placeholder = False
        self.normal, self.focused, pad = _chip_images(w, h)
        # картинка рамки
        self.bg_id = board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=self.normal, tags=(board.layer,)
        )
        # настоящее поле ввода без собственной рамки (bd=0)
        self.entry = tk.Entry(
            board,
            bd=0,
            highlightthickness=0,
            justify="center",
            font=font("Medium", size),
            bg=WHITE,
            fg=BLACK,
            insertbackground=BLACK,
            show=show,
        )
        # кладём виджет на холст в нужное место
        board.create_window(
            S(x + w / 2),
            S(y + h / 2),
            window=self.entry,
            width=S(w - 24),
            height=S(h - 12),
            tags=(board.layer,),
        )
        board.add_widget(self.entry)
        if max_length:
            # проверка при каждом нажатии клавиши: длиннее max_length ввести нельзя
            check = (board.register(self._allowed), "%P")
            self.entry.configure(validate="key", validatecommand=check)
        # курсор попал в поле - синяя рамка; ушёл - обычная
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        if text:
            self.entry.insert(0, text)
        else:
            self._show_placeholder()
        if readonly:
            self.set_readonly(True)

    # Можно ли записать такой текст: подсказка не считается, остальное не длиннее max_length
    def _allowed(self, new_text):
        return self.showing_placeholder or len(new_text) <= self.max_length

    # Запретить или разрешить менять текст (поле «Логин (не изменяется)»)
    def set_readonly(self, flag):
        state = "readonly" if flag else "normal"
        self.entry.configure(state=state, readonlybackground=WHITE)

    # серая подсказка, пока поле пустое
    def _show_placeholder(self):
        if self.placeholder and not self.entry.get():
            self.showing_placeholder = True
            self.entry.configure(show="", fg=PLACEHOLDER)
            self.entry.insert(0, self.placeholder)

    # при входе в поле: синяя рамка и убираем подсказку
    def _focus_in(self, event):
        self.board.itemconfigure(self.bg_id, image=self.focused)
        if self.showing_placeholder:
            self.showing_placeholder = False
            self.entry.delete(0, "end")
            self.entry.configure(fg=BLACK, show=self.show_char)

    # при выходе: обычная рамка, при пустом поле - снова подсказка
    def _focus_out(self, event):
        self.board.itemconfigure(self.bg_id, image=self.normal)
        self._show_placeholder()

    # Текст поля (подсказка не считается)
    def get(self):
        """Введённый текст (без подсказки)."""
        return "" if self.showing_placeholder else self.entry.get()

    def set(self, text):
        """Заменяет текст в поле."""
        self.showing_placeholder = False
        state = str(self.entry.cget("state"))  # запоминаем, было ли поле только для чтения
        self.entry.configure(state="normal", fg=BLACK, show=self.show_char)
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.entry.configure(state=state)

    def clear(self):
        """Очищает поле."""
        self.entry.delete(0, "end")
        self.showing_placeholder = False
        self._show_placeholder()

    def focus(self):
        """Ставит курсор в поле."""
        self.entry.focus_set()

    # После каждой нажатой клавиши вызываем callback
    def on_change(self, callback):
        """Вызывает callback после каждого нажатия клавиши."""
        self.entry.bind("<KeyRelease>", lambda event: callback())

    # По Enter вызываем callback
    def on_enter(self, callback):
        """Вызывает callback при нажатии Enter."""
        self.entry.bind("<Return>", lambda event: callback())


# Многострочное поле (tk.Text) для описания заявки
class TextBox:
    """Многострочное поле (описание заявки) в такой же рамке."""

    def __init__(self, board, x, y, w, h, size=12, max_length=None):
        self.max_length = max_length
        self.normal, self.focused, pad = _chip_images(w, h)
        bg_id = board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=self.normal, tags=(board.layer,)
        )
        # wrap="word" - перенос строк по словам
        self.text = tk.Text(
            board,
            bd=0,
            highlightthickness=0,
            font=font("Medium", size),
            bg=WHITE,
            fg=BLACK,
            wrap="word",
            insertbackground=BLACK,
        )
        board.create_window(
            S(x + w / 2),
            S(y + h / 2),
            window=self.text,
            width=S(w - 24),
            height=S(h - 10),
            tags=(board.layer,),
        )
        board.add_widget(self.text)
        self.text.bind("<FocusIn>", lambda e: board.itemconfigure(bg_id, image=self.focused))
        self.text.bind("<FocusOut>", lambda e: board.itemconfigure(bg_id, image=self.normal))
        if max_length:
            # лишние символы (набранные или вставленные) сразу отрезаем
            self.text.bind("<KeyRelease>", self._cut)
            self.text.bind("<<Paste>>", lambda e: self.text.after(1, self._cut))

    # Отрезает текст, который длиннее max_length
    def _cut(self, event=None):
        if len(self.text.get("1.0", "end-1c")) > self.max_length:
            self.text.delete(f"1.0+{self.max_length}c", "end")

    def get(self):
        """Введённый текст."""
        # "1.0" - с начала (строка 1, символ 0) и до конца
        return self.text.get("1.0", "end").strip()

    def clear(self):
        """Очищает поле."""
        self.text.delete("1.0", "end")


# Выпадающий список: рамка, текст, стрелка. По щелчку открывается меню
class DropBox:
    """Выпадающий список: значение и стрелка справа. По щелчку открывается меню."""

    def __init__(self, board, x, y, w, h, values, index=0, command=None, size=12):
        self.board, self.rect, self.size = board, (x, y, w, h), size
        self.values, self.command = list(values), command
        # номер выбранного пункта
        self.index = index if self.values else -1
        normal, pad = shape_image(S(w), S(h), S(8), WHITE, BLACK, line_width(1))
        tag = board.new_tag("drop")
        board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=normal, tags=(board.layer, tag)
        )
        # текст выбранного пункта
        self.text_id = board.create_text(
            S(x + (w - 34) / 2),
            S(y + h / 2),
            text=self._text(),
            font=font("Medium", size),
            tags=(board.layer, tag),
        )
        # стрелка вниз, нарисованная как картинка
        arrow = line_image(
            (S(20), S(12)), [(S(2), S(2)), (S(10), S(9.5)), (S(18), S(2))], BLACK, max(2, S(2.4))
        )
        board.create_image(
            S(x + w - 32), S(y + h / 2 - 6), anchor="nw", image=arrow, tags=(board.layer, tag)
        )
        board.hover_cursor(tag)
        board.tag_bind(tag, "<ButtonRelease-1>", lambda e: self._open_menu())

    # текст выбранного пункта (длинный обрезаем)
    def _text(self):
        if 0 <= self.index < len(self.values):
            return self.board.fit_text(
                self.values[self.index], "Medium", self.size, self.rect[2] - 60
            )
        return ""

    # Меню со всеми пунктами под полем
    def _open_menu(self):
        # обычное меню Tkinter
        menu = tk.Menu(self.board, tearoff=0, font=font("Regular", 16), bg=WHITE)
        for position, value in enumerate(self.values):
            # lambda p=position запоминает номер пункта для этой строки меню
            menu.add_command(label=value, command=lambda p=position: self.select(p))
        x, y, w, h = self.rect
        try:
            # показываем меню под полем
            menu.tk_popup(self.board.winfo_rootx() + S(x), self.board.winfo_rooty() + S(y + h))
        finally:
            menu.grab_release()

    # Выбираем пункт и сообщаем об этом
    def select(self, position, notify=True):
        """Выбирает пункт по номеру."""
        self.index = position
        self.board.itemconfigure(self.text_id, text=self._text())
        if notify and self.command:
            self.command()

    # Заменяем список пунктов
    def set_values(self, values, index=0):
        """Заменяет пункты списка."""
        self.values = list(values)
        self.select(index if self.values else -1, notify=False)

    def get(self):
        """Текст выбранного пункта."""
        return self.values[self.index] if 0 <= self.index < len(self.values) else ""


# ======================================================================
# ЧАСТЬ 6. Флажок и радиокнопки
# ======================================================================


# Флажок: серый квадрат; когда отмечен - синий с галочкой
class CheckBox:
    """Флажок: серый квадрат, а когда отмечен - синий с белой галочкой."""

    SIZE = 24

    def __init__(self, board, x, y, checked=False, command=None):
        self.board, self.checked, self.command = board, checked, command
        size = S(self.SIZE)
        # две картинки: выключен и включен
        self.off, pad = shape_image(size, size, S(5), "#dcdcdc")
        self.on, _ = shape_image(size, size, S(5), BLUE)
        # белая галочка
        tick = line_image(
            (size, size),
            [(size * 0.24, size * 0.53), (size * 0.43, size * 0.72), (size * 0.77, size * 0.30)],
            WHITE,
            max(2, S(2.4)),
        )
        tag = board.new_tag("check")
        self.box_id = board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=self.off, tags=(board.layer, tag)
        )
        # галочка скрыта, пока флажок снят
        self.tick_id = board.create_image(
            S(x), S(y), anchor="nw", image=tick, state="hidden", tags=(board.layer, tag)
        )
        board.hover_cursor(tag)
        board.tag_bind(tag, "<ButtonRelease-1>", lambda e: self.toggle())
        self.set(checked)

    # Переключение по щелчку
    def toggle(self):
        """Переключает флажок и вызывает command."""
        self.set(not self.checked)
        if self.command:
            self.command()

    def set(self, checked):
        """Ставит или снимает отметку."""
        self.checked = checked
        # меняем картинку и показываем или прячем галочку
        self.board.itemconfigure(self.box_id, image=self.on if checked else self.off)
        self.board.itemconfigure(self.tick_id, state="normal" if checked else "hidden")

    def get(self):
        """True, если флажок отмечен."""
        return self.checked


# Радиокнопки: выбрать можно только одну
class RadioGroup:
    """Радиокнопки: можно выбрать только одну. items - список (значение, подпись, x, y)."""

    SIZE = 24

    def __init__(self, board, items, selected=0):
        self.board, self.values, self.selected = board, [item[0] for item in items], selected
        size = S(self.SIZE)
        # кольцо кнопки
        ring, pad = shape_image(size, size, size // 2, WHITE, BLUE, max(2, S(2)))
        dot_size = S(self.SIZE * 0.4)
        # точка внутри кольца
        dot, dot_pad = shape_image(dot_size, dot_size, dot_size // 2, BLUE)
        self.dots = []
        # для каждого варианта рисуем кольцо, точку и подпись
        for position, (_, caption, x, y) in enumerate(items):
            tag = board.new_tag("radio")
            board.create_image(
                S(x) - pad, S(y) - pad, anchor="nw", image=ring, tags=(board.layer, tag)
            )
            offset = S((self.SIZE - self.SIZE * 0.4) / 2)
            self.dots.append(
                board.create_image(
                    S(x) + offset - dot_pad,
                    S(y) + offset - dot_pad,
                    anchor="nw",
                    image=dot,
                    tags=(board.layer, tag),
                )
            )
            board.create_text(
                S(x + self.SIZE + 10),
                S(y + self.SIZE / 2),
                text=caption,
                anchor="w",
                font=font("Regular", 14),
                tags=(board.layer, tag),
            )
            board.hover_cursor(tag)
            board.tag_bind(tag, "<ButtonRelease-1>", lambda e, p=position: self.select(p))
        self.select(selected)

    # показываем точку только у выбранной кнопки
    def select(self, position):
        """Выбирает кнопку по номеру."""
        self.selected = position
        for index, dot in enumerate(self.dots):
            self.board.itemconfigure(dot, state="normal" if index == position else "hidden")

    def get(self):
        """Значение выбранной кнопки."""
        return self.values[self.selected]


# ======================================================================
# ЧАСТЬ 7А. Прокручиваемый текст, круглые кнопки, логотип
# ======================================================================


# Текстовое поле с полосой прокрутки без рамки: описание заявки в карточке
class ScrollText:
    """Многострочный текст с прокруткой. Длинный текст листается колесом мыши или полосой."""

    def __init__(self, board, x, y, w, h, text="", size=20, style="Light", max_length=None):
        self.max_length = max_length
        # обычное многострочное поле Tkinter: без рамки, фон белый (как карточка под ним)
        self.text = tk.Text(
            board,
            bd=0,
            highlightthickness=0,
            font=font(style, size),
            bg=WHITE,
            fg=BLACK,
            wrap="word",
            insertbackground=BLACK,
            padx=0,
            pady=0,
        )
        # полоса прокрутки справа; yscrollcommand заставляет её двигаться вместе с текстом
        self.scroll = tk.Scrollbar(board, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.scroll.set)
        bar = S(16)  # ширина полосы
        board.create_window(
            S(x),
            S(y),
            window=self.text,
            anchor="nw",
            width=S(w) - bar - S(4),
            height=S(h),
            tags=(board.layer,),
        )
        board.create_window(
            S(x + w) - bar,
            S(y),
            window=self.scroll,
            anchor="nw",
            width=bar,
            height=S(h),
            tags=(board.layer,),
        )
        board.add_widget(self.text)
        board.add_widget(self.scroll)
        if max_length:
            # лишние символы (набранные или вставленные) сразу отрезаем
            self.text.bind("<KeyRelease>", self._cut)
            self.text.bind("<<Paste>>", lambda e: self.text.after(1, self._cut))
        self.set(text)

    # Отрезает текст, который длиннее max_length
    def _cut(self, event=None):
        if len(self.text.get("1.0", "end-1c")) > self.max_length:
            self.text.delete(f"1.0+{self.max_length}c", "end")

    def set(self, text):
        """Записывает текст в поле."""
        state = str(self.text.cget("state"))  # запоминаем, было ли поле только для чтения
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state=state)

    def get(self):
        """Текст поля."""
        return self.text.get("1.0", "end").strip()

    def set_readonly(self, flag):
        """Запретить или разрешить менять текст (выполненную заявку менять нельзя)."""
        self.text.configure(state="disabled" if flag else "normal")


# Рисуем значок для круглой кнопки: шестерёнка или корзина
def icon_image(kind, px):
    """Картинка значка размером px на px: "gear" (шестерёнка) или "trash" (корзина)."""
    key = ("icon", kind, px)
    if key not in _cache:
        big = px * SUPER  # рисуем крупнее, потом уменьшаем - края получаются гладкими
        image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        unit = big / 24  # размер значка условно 24 клетки
        if kind == "gear":
            center = big / 2
            points = []
            for tooth in range(8):  # восемь зубцов через каждые 45 градусов
                angle = tooth * math.pi / 4
                # у зубца четыре точки: основание слева, верх слева, верх справа, основание справа
                for shift, radius in ((-0.21, 8), (-0.12, 10.5), (0.12, 10.5), (0.21, 8)):
                    a = angle + shift
                    points.append(
                        (center + math.cos(a) * radius * unit, center + math.sin(a) * radius * unit)
                    )
            draw.polygon(points, fill=(0, 0, 0, 255))
            hole = 3.6 * unit  # отверстие посередине
            draw.ellipse(
                (center - hole, center - hole, center + hole, center + hole), fill=(0, 0, 0, 0)
            )
        else:  # корзина
            black = (0, 0, 0, 255)
            draw.rounded_rectangle(
                (4 * unit, 6 * unit, 20 * unit, 8.2 * unit), unit, fill=black
            )  # крышка
            draw.rounded_rectangle(
                (9 * unit, 3.4 * unit, 15 * unit, 6.4 * unit), unit, fill=black
            )  # ручка
            draw.polygon(  # корпус немного сужается книзу
                [
                    (5.8 * unit, 9.2 * unit),
                    (18.2 * unit, 9.2 * unit),
                    (17 * unit, 20.8 * unit),
                    (7 * unit, 20.8 * unit),
                ],
                fill=black,
            )
            for line_x in (10, 12, 14):  # три светлые полоски на корпусе
                draw.line(
                    (line_x * unit, 11.4 * unit, line_x * unit, 18.4 * unit),
                    fill=(0, 0, 0, 0),
                    width=int(1.3 * unit),
                )
        _cache[key] = ImageTk.PhotoImage(image.resize((px, px), Image.LANCZOS))
    return _cache[key]


# Круглая белая кнопка с тенью и значком внутри (FAB в Figma)
class IconButton:
    """Круглая кнопка со значком. kind: "gear" (настройки) или "trash" (удалить)."""

    def __init__(self, board, x, y, kind, command, size=40):
        px = S(size)
        shadow = scaled(BUTTON_SHADOW)
        # две картинки круга: обычная и чуть темнее (когда мышь над кнопкой); радиус = половина
        self.normal, pad = shape_image(px, px, px // 2, WHITE, None, 1, shadow)
        self.hover, _ = shape_image(px, px, px // 2, "#ececec", None, 1, shadow)
        self.board, self.command = board, command
        tag = board.new_tag("icon")
        self.image_id = board.create_image(
            S(x) - pad, S(y) - pad, anchor="nw", image=self.normal, tags=(board.layer, tag)
        )
        icon_size = S(24)
        offset = (px - icon_size) // 2  # значок по центру круга
        board.create_image(
            S(x) + offset,
            S(y) + offset,
            anchor="nw",
            image=icon_image(kind, icon_size),
            tags=(board.layer, tag),
        )
        board.hover_cursor(tag)
        board.tag_bind(
            tag, "<Enter>", lambda e: board.itemconfigure(self.image_id, image=self.hover), "+"
        )
        board.tag_bind(
            tag, "<Leave>", lambda e: board.itemconfigure(self.image_id, image=self.normal), "+"
        )
        board.tag_bind(tag, "<ButtonRelease-1>", lambda e: self.command())


# Логотип приложения: файл assets/logo.png нужного размера
def logo_image(size):
    """Картинка логотипа size на size пикселей экрана (или None, если файла нет)."""
    key = ("logo", size)
    if key not in _cache:
        path = resource_path(os.path.join("assets", "logo.png"))
        if not os.path.exists(path):
            return None
        picture = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        _cache[key] = ImageTk.PhotoImage(picture)
    return _cache[key]


def logo(board, x, y, size):
    """Кладёт логотип на холст: x, y, size - в пикселях макета."""
    picture = logo_image(S(size))
    if picture is None:  # нет файла - окно просто работает без логотипа
        return None
    return board.create_image(S(x), S(y), anchor="nw", image=picture, tags=(board.layer,))


# Шапка окна: логотип, название ТСЖ и адрес. Обе строки начинаются с одной линии
def header(board, title, subtitle, y=20):
    """Рисует логотип слева и рядом название и адрес ТСЖ, прижатые к одному левому краю."""
    logo(board, 26, y - 2, 64)
    board.label(104, y, 800, title, "Bold", 32, align="left")
    board.label(104, y + 43, 800, subtitle, "ExtraLight", 20, align="left")


# ======================================================================
# ЧАСТЬ 7. Таблица
# ======================================================================


# Ключ сортировки: числа как числа, текст - без учёта регистра
def _sort_key(value):
    """Число сортируем как число, остальное как текст без учёта регистра."""
    try:
        return (0, float(str(value).replace(",", ".")), "")
    except ValueError:
        return (1, 0, str(value).lower())


# Таблица в серой панели: заголовок, строки, прокрутка и сортировка по щелчку на заголовок
class Table:
    """Таблица в серой скруглённой панели, как в макете.

    Заголовок, тёмные линии между строками, значения по центрам столбцов.
    Щелчок по заголовку сортирует столбец, колесо мыши прокручивает строки,
    щелчок по строке выбирает её.
    """

    # обычные размеры: высота от верха панели до линии под заголовком и высота строки
    HEADER_LINE = 54
    ROW_HEIGHT = 53

    def __init__(
        self,
        board,
        x,
        y,
        w,
        h,
        columns,
        on_select=None,
        header_line=None,
        row_height=None,
        header_top=10,
    ):
        """columns: список словарей title, cx (центр столбца от левого края панели),
        style, size (шрифт значений), width (наибольшая ширина текста).
        header_line, row_height, header_top - размеры, если таблица не обычная (окна-списки)."""
        self.board, self.on_select = board, on_select
        self.x, self.y, self.w, self.h, self.columns = x, y, w, h, columns
        # rows - строки, offset - с какой строки показываем (прокрутка)
        self.rows, self.offset, self.selected_key = [], 0, None
        # по какому столбцу отсортировано и в какую сторону
        self.sort_column, self.sort_reverse = None, False
        self.tag, self.layer = board.new_tag("table"), board.layer
        # размеры этой таблицы: свои или обычные
        self.header_line = header_line or self.HEADER_LINE
        self.row_height = row_height or self.ROW_HEIGHT
        # сколько строк помещается в панель
        self.visible = (h - self.header_line - 4) // self.row_height

        # серая скруглённая панель
        board.shape(x, y, w, h, 22, PANEL_GRAY)
        self.headers = []
        # заголовки столбцов; по щелчку - сортировка
        for number, column in enumerate(columns):
            tag = f"{self.tag}head{number}"
            item = board.centered(
                x + column["cx"] - 90,
                y + header_top,
                180,
                29,
                column["title"],
                "Regular",
                24,
                tags=(tag,),
            )
            self.headers.append(item)
            board.hover_cursor(tag)
            board.tag_bind(tag, "<ButtonRelease-1>", lambda e, n=number: self.sort_by(n))
        # колесо мыши листает таблицу
        board.add_wheel_area(x, y, w, h, self.scroll)
        # щелчок по строке - выбор
        board.tag_bind(self.tag + "row", "<ButtonRelease-1>", self._click)

    # Загружаем новые строки: (ключ, значения, цвет строки)
    def set_rows(self, rows):
        """rows: список (ключ, значения столбцов, цвет подложки или None)."""
        self.rows = list(rows)
        if self.selected_key not in [row[0] for row in self.rows]:
            self.selected_key = None
        self.offset = 0
        self._apply_sort()
        self.redraw()

    # Сортировка по столбцу; повторный щелчок - в обратную сторону
    def sort_by(self, number):
        """Сортирует по столбцу; повторный щелчок меняет направление."""
        self.sort_reverse = not self.sort_reverse if self.sort_column == number else False
        self.sort_column = number
        self._apply_sort()
        self.redraw()

    # сортируем и рисуем стрелку в заголовке
    def _apply_sort(self):
        number = self.sort_column
        if number is not None:
            self.rows.sort(key=lambda row: _sort_key(row[1][number]), reverse=self.sort_reverse)
        for index, item in enumerate(self.headers):
            arrow = (" ↓" if self.sort_reverse else " ↑") if index == number else ""
            self.board.itemconfigure(item, text=self.columns[index]["title"] + arrow)

    # Прокрутка колесом
    def scroll(self, direction):
        """Прокручивает на строку вверх (-1) или вниз (1)."""
        self.offset = min(max(self.offset + direction, 0), max(0, len(self.rows) - self.visible))
        self.redraw()

    def select(self, key):
        """Выделяет строку с этим ключом."""
        self.selected_key = key
        self.redraw()

    # Перерисовка: стираем строки и рисуем только видимые
    def redraw(self):
        """Перерисовывает видимые строки."""
        board, top = self.board, self.y + self.header_line
        # удаляем старые строки
        board.delete(self.tag)
        # цикл по видимым строкам
        for position in range(self.visible):
            index = self.offset + position
            if index >= len(self.rows):
                break
            key, values, tint = self.rows[index]
            row_top = top + position * self.row_height
            tags = (self.layer, self.tag, self.tag + "row", f"row{index}")
            # подложка нужна, чтобы Tk ловил щелчки по пустому месту строки
            board.create_rectangle(
                S(self.x + 1),
                S(row_top),
                S(self.x + self.w - 1),
                S(row_top + self.row_height),
                fill=PANEL_GRAY,
                outline="",
                tags=tags,
            )
            # цвет строки: выбранная подсвечивается синим, иначе свой цвет
            fill = SELECT_TINT if key == self.selected_key else tint
            if fill:
                board.create_rectangle(
                    S(self.x + 12),
                    S(row_top + 2),
                    S(self.x + self.w - 12),
                    S(row_top + self.row_height - 2),
                    fill=fill,
                    outline="",
                    tags=tags,
                )
            # линия между строками
            if position > 0:
                board.hline(self.x + 1, row_top, self.w - 2, tags=(self.tag,))
            # текст каждой ячейки по центру своего столбца
            for column, value in zip(self.columns, values):
                text = board.fit_text(str(value), column["style"], column["size"], column["width"])
                board.create_text(
                    S(self.x + column["cx"]),
                    S(row_top + self.row_height / 2),
                    text=text,
                    font=font(column["style"], column["size"]),
                    tags=tags,
                )
        board.hline(self.x + 1, top, self.w - 2, tags=(self.tag,))  # линия под заголовком
        self._draw_scrollbar()

    # Ползунок прокрутки справа, если строк больше, чем помещается
    def _draw_scrollbar(self):
        if len(self.rows) <= self.visible:
            return
        track = self.h - self.header_line - 24
        thumb = max(30, track * self.visible / len(self.rows))
        start = self.y + self.header_line + 8
        start += (track - thumb) * self.offset / max(1, len(self.rows) - self.visible)
        x = S(self.x + self.w - 9)
        self.board.create_line(
            x,
            S(start),
            x,
            S(start + thumb),
            fill="#b9b9b9",
            width=S(5),
            capstyle="round",
            tags=(self.layer, self.tag),
        )

    # Щелчок по строке: находим строку под курсором и вызываем on_select
    def _click(self, event):
        item = self.board.find_withtag("current")
        for tag in self.board.gettags(item[0]) if item else ():
            if tag.startswith("row"):
                self.selected_key = self.rows[int(tag[3:])][0]
                self.redraw()
                if self.on_select:
                    self.on_select(self.selected_key)
                return
