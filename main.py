"""Точка входа: запуск программы «Система управления ТСЖ»."""

import tkinter as tk

from db import database

from ui import kit

from ui.app import App


def main():
    """Создаёт базу данных (если её нет) и открывает главное окно."""
    kit.enable_high_dpi()
    kit.load_fonts()
    database.init_db()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
