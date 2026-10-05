"""Рисует логотип приложения: assets/logo.png (для окон) и assets/logo.ico (для exe).

Запуск: python make_logo.py
Если у тебя есть свой логотип, просто положи свой квадратный файл в assets/logo.png.
"""

import os

from PIL import Image, ImageDraw

BLUE = (0, 136, 255, 255)
WHITE = (255, 255, 255, 255)
BIG = 1024


def draw_logo():
    """Рисует логотип: синий скруглённый квадрат и белый дом с окошком и дверью."""
    image = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = BIG / 100
    draw.rounded_rectangle((0, 0, BIG - 1, BIG - 1), radius=22 * unit, fill=BLUE)
    draw.polygon(
        [(50 * unit, 18 * unit), (84 * unit, 46 * unit), (16 * unit, 46 * unit)], fill=WHITE
    )
    draw.rectangle((24 * unit, 46 * unit, 76 * unit, 80 * unit), fill=WHITE)
    draw.rounded_rectangle((44 * unit, 58 * unit, 56 * unit, 80 * unit), radius=2 * unit, fill=BLUE)
    draw.rectangle((30 * unit, 54 * unit, 40 * unit, 64 * unit), fill=BLUE)
    draw.rectangle((60 * unit, 54 * unit, 70 * unit, 64 * unit), fill=BLUE)
    return image


def main():
    """Сохраняет логотип в двух файлах."""
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(folder, exist_ok=True)
    big = draw_logo()
    big.resize((256, 256), Image.LANCZOS).save(os.path.join(folder, "logo.png"))
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.save(os.path.join(folder, "logo.ico"), sizes=sizes)
    print("Логотип создан в папке:", folder)


if __name__ == "__main__":
    main()
