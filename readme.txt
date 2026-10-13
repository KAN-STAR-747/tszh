СИСТЕМА УПРАВЛЕНИЯ ТСЖ
======================

Запуск проекта в Codeium (Windsurf) на Linux
--------------------------------------------

1. Установите системные пакеты (Debian / Ubuntu / Mint):

       sudo apt update
       sudo apt install -y git python3 python3-venv python3-pip python3-tk fonts-roboto

   Пакет python3-tk обязателен: без него не работает Tkinter (окна программы).
   Для Fedora: sudo dnf install git python3 python3-tkinter google-roboto-fonts
   Для Arch:   sudo pacman -S git python tk ttf-roboto

   Нужен Python 3.10 или новее (проверка: python3 --version).

2. Скачайте проект и откройте его в Codeium (Windsurf):

       git clone https://github.com/KAN-STAR-747/tszh.git
       cd tszh
       windsurf .

   Либо откройте папку проекта через меню File -> Open Folder.
   Все следующие команды выполняйте во встроенном терминале (Ctrl+`).
   Графическое окно программы откроется на рабочем столе, поэтому запускайте
   в обычной графической сессии (не по ssh без X11).

3. Создайте виртуальное окружение и установите библиотеки:

       python3 -m venv venv
       source venv/bin/activate
       pip install --upgrade pip
       pip install -r requirements.txt
       pip install -r requirements-dev.txt

   requirements.txt - библиотеки программы (openpyxl, Pillow),
   requirements-dev.txt - инструменты разработки (black, flake8, pre-commit и др.).

   В Codeium выберите интерпретатор: Ctrl+Shift+P -> "Python: Select Interpreter"
   -> ./venv/bin/python.

4. (По желанию) Заполните тестовыми данными:

       python seed_test_data.py

   Тестовые учётные записи (логин - пароль):
       ivanov@example.com   - ivanov123
       smirnov@example.com  - smirnov123
       petrov@example.com   - petrov123

   Без этого шага программа стартует с пустой базой, и первым нужно
   зарегистрировать председателя.

5. Запустите программу:

       python main.py

   База данных tszh.db создаётся автоматически рядом с программой.

6. Запуск тестов:

       python -m unittest discover -s tests -v

   Покрытие кода тестами (coverage.py):

       python -m coverage run --source=services,db -m unittest discover -s tests
       python -m coverage report -m

   Замер времени отклика и памяти на доме из 500 квартир:

       python -m tests.performance_check

7. Проверка стиля кода (по желанию):

       black --check .
       flake8


Сборка exe (Windows)
--------------------

    build.bat

Скрипт запускает тесты, собирает dist\TSJ.exe через pyinstaller и копирует рядом
.env. Инструкция для пользователя: docs\Инструкция пользователя.docx (и .pdf).


Секреты: почта и нейросеть (необязательно)
------------------------------------------

Все секреты (ключ DeepSeek, адрес и секретное слово скрипта Google, пароль почты)
хранятся только в файле .env рядом с main.py (рядом с TSJ.exe). В репозиторий он
не попадает: в git лежит лишь образец без секретов - .env.example.

    cp .env.example .env        (Windows: copy .env.example .env)

Откройте .env в любом редакторе и впишите свои значения. Значения можно задать и
обычными переменными окружения с теми же именами (они главнее файла).

Без файла .env программа работает, но код регистрации и новый пароль не
отправляются, а адрес ТСЖ сохраняется так, как введён. Кто скачал проект с GitHub,
получает рабочую программу, положив свой .env рядом с main.py.


Частые проблемы на Linux
------------------------

* ModuleNotFoundError: No module named 'tkinter'
  Установите пакет: sudo apt install python3-tk

* no display name and no $DISPLAY environment variable
  Нет графической сессии. Запускайте на рабочем столе или настройте X11/Wayland.

* Шрифт выглядит не так, как в макете
  Установите Roboto (sudo apt install fonts-roboto) и перезапустите программу.
  На Linux шрифты из папки fonts автоматически не подключаются, поэтому
  берутся системные.

* Окно слишком мелкое или крупное
  Размеры подстраиваются под экран автоматически. Для масштаба можно
  задать переменную: GDK_SCALE=2 python main.py
