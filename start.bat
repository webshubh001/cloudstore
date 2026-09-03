@echo off
title CloudStore — Dev Server
color 0A

echo.
echo  ========================================
echo     CloudStore ^| Secure Cloud Storage
echo  ========================================
echo.

:: ── Check venv exists ──────────────────────────────────────────────────────
if not exist "venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    echo          Run: python -m venv venv
    echo          Then: venv\Scripts\activate ^& pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

:: ── Check .env exists ──────────────────────────────────────────────────────
if not exist ".env" (
    echo  [WARNING] .env file not found.
    echo            Copying from .env.example — fill in your credentials!
    copy .env.example .env >nul
    echo  [OK] .env created from .env.example
    echo.
)

:: ── Activate virtual environment ───────────────────────────────────────────
echo  [1/4] Activating virtual environment...
call venv\Scripts\activate.bat
echo  [OK] venv activated

:: ── Run migrations ─────────────────────────────────────────────────────────
echo.
echo  [2/4] Applying database migrations...
python manage.py migrate --run-syncdb 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Migration failed. Check your database settings in .env
    pause
    exit /b 1
)
echo  [OK] Migrations applied

:: ── Collect static files ───────────────────────────────────────────────────
echo.
echo  [3/4] Collecting static files...
python manage.py collectstatic --noinput --clear -v 0 2>&1
echo  [OK] Static files ready

:: ── Start development server ───────────────────────────────────────────────
echo.
echo  [4/4] Starting development server...
echo.
echo  ----------------------------------------
echo   Open in browser:  http://127.0.0.1:8000
echo   Admin panel:      http://127.0.0.1:8000/admin/
echo   Press Ctrl+C to stop
echo  ----------------------------------------
echo.
python manage.py runserver

:: ── On server stop ─────────────────────────────────────────────────────────
echo.
echo  Server stopped.
pause
