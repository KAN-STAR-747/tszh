@echo off
rem Build a single TSJ.exe. Run from the project root: build.bat
rem Result: dist\TSJ.exe (the database tszh.db is created next to it on first start).
setlocal
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo No virtual environment found. Create it first:
    echo     python -m venv venv
    echo     venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
    exit /b 1
)

echo [1/3] Running automatic tests...
venv\Scripts\python.exe -m unittest discover -s tests > build_tests.log 2>&1
if errorlevel 1 (
    echo Tests failed, build stopped. Details: build_tests.log
    exit /b 1
)
del build_tests.log

echo [2/3] Building TSJ.exe (1-2 minutes)...
venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --noconsole ^
    --name TSJ --icon assets\logo.ico ^
    --add-data "fonts;fonts" --add-data "assets;assets" ^
    --hidden-import PIL._tkinter_finder ^
    main.py > build_pyinstaller.log 2>&1
if errorlevel 1 (
    echo Build failed. Details: build_pyinstaller.log
    exit /b 1
)
del build_pyinstaller.log

echo [3/3] Copying secrets (.env)...
if exist .env (
    copy /y .env dist\.env > nul
    echo .env copied to dist: letters with codes will be sent.
) else (
    copy /y .env.example dist\.env.example > nul
    echo .env not found: the example was copied to dist, fill it in and rename it to .env.
)

echo Done: dist\TSJ.exe
endlocal
