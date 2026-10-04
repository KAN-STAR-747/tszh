"""Временная заготовка кабинета жильца (будет заменена завтра)."""


class ResidentScreen:
    size = (1588, 919)
    title = "Система управления ТСЖ"

    def __init__(self, app, board, user):
        board.label(100, 100, 600, "Кабинет жильца (заготовка)", "Bold", 32, align="left")
