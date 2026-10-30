@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Membuat virtual environment dan memasang dependensi...
    python -m venv .venv
    if errorlevel 1 goto :gagal
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :gagal
)

".venv\Scripts\python.exe" app.py %*
if errorlevel 1 pause
exit /b 0

:gagal
echo.
echo [gagal] Setup tidak selesai. Pastikan Python 3.11+ terpasang dan internet aktif.
pause
exit /b 1
