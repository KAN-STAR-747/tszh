"""Временная заготовка главного окна (будет заменена завтра)."""


class MainScreen:
    size = (1588, 919)
    title = "Система управления ТСЖ"

    def __init__(self, app, board, user):
        board.label(100, 100, 600, "Окно председателя (заготовка)", "Bold", 32, align="left")
