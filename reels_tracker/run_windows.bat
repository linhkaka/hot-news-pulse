@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
    echo Dang cai dat lan dau...
    python -m venv .venv || (echo Chua cai Python. Tai tai https://www.python.org/downloads/ & pause & exit /b 1)
    .venv\Scripts\pip install -r requirements.txt
)
if not exist .env (
    copy .env.example .env >nul
    echo Da tao file .env - hay mo file .env, dien token roi chay lai.
    notepad .env
    pause
    exit /b 0
)
:loop
.venv\Scripts\python tracker.py
if errorlevel 2 (
    echo.
    echo Cau hinh chua dung - xem huong dan sua loi o tren, sua file .env roi chay lai.
    pause
    exit /b 2
)
echo Tool da dung, tu khoi dong lai sau 10 giay... (Ctrl+C de thoat)
timeout /t 10 >nul
goto loop
