"""Быстрая проверка набора элементов kit: открывает окно с примерами."""

import tkinter as tk

from ui import kit

kit.enable_high_dpi()
kit.load_fonts()
root = tk.Tk()
kit.init_scale(root)
root.title("Проверка kit")
board = kit.Board(root, 700, 520)
board.pack()
root.geometry(f"{kit.S(700)}x{kit.S(520)}+100+50")

board.label(20, 20, 300, "Заголовок", "Bold", 32, align="left")
kit.Button(board, 20, 90, 216, 35, "Войти", lambda: print("клик"))
kit.Button(board, 250, 90, 119, 35, "Отмена", lambda: print("отмена"), "plain")
kit.EntryBox(board, 20, 150, 355, 42, placeholder="Логин")
kit.EntryBox(board, 20, 210, 355, 42, show="*")
kit.DropBox(board, 20, 270, 355, 42, ["Все", "Новая", "В работе"])
kit.CheckBox(board, 20, 335)
kit.RadioGroup(board, [("a", "Звонок", 120, 335), ("b", "Приложение", 260, 335)])
kit.note(board, 20, 390, 359, 51, "Аккаунт ожидает подтверждения", "error")

columns = [
    {"title": "Кв.", "cx": 50, "style": "Light", "size": 24, "width": 80},
    {"title": "Долг", "cx": 190, "style": "Light", "size": 24, "width": 120},
]
table = kit.Table(board, 400, 20, 280, 300, columns)
table.set_rows([(1, [1, "0.00"], None), (2, [2, "10.65"], kit.DEBT_TINT), (3, [3, "5.00"], None)])

root.mainloop()
