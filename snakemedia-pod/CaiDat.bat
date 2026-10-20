@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Cai dat SNAKEMEDIA POD (chi can chay 1 lan) ===
python --version || (echo Chua co Python. Tai tai https://www.python.org/downloads/ va TICK "Add python.exe to PATH" & pause & exit /b 1)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
echo.
echo Xong! Buoc tiep theo: chay DangNhapFacebook.bat roi ChayTool.bat
pause
