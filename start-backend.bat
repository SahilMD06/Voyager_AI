@echo off
cd /d "%~dp0backend"
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist .env copy .env.example .env >nul
python -m uvicorn app.main:app --reload --port 8000
pause
