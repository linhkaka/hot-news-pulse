@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set SNAKEPOD_DATA=data_demo
python -m snakepod.demo
python -m snakepod
pause
