#!/usr/bin/env bash
# start.sh — CloudStore local development startup script
# Usage: chmod +x start.sh && ./start.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

echo ""
echo -e "${CYAN} ========================================"
echo -e "    CloudStore | Secure Cloud Storage"
echo -e " ========================================${RESET}"
echo ""

# ── Check venv ────────────────────────────────────────────────────────────────
if [ ! -f "venv/bin/activate" ]; then
    echo -e "${RED} [ERROR] Virtual environment not found.${RESET}"
    echo "         Run: python3 -m venv venv"
    echo "         Then: source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# ── Check .env ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${YELLOW} [WARNING] .env not found — copying from .env.example${RESET}"
    cp .env.example .env
    echo -e "${GREEN} [OK] .env created. Fill in your credentials before continuing.${RESET}"
    echo ""
fi

# ── Activate venv ─────────────────────────────────────────────────────────────
echo -e " ${CYAN}[1/4]${RESET} Activating virtual environment..."
source venv/bin/activate
echo -e " ${GREEN}[OK]${RESET} venv activated"

# ── Migrate ───────────────────────────────────────────────────────────────────
echo ""
echo -e " ${CYAN}[2/4]${RESET} Applying database migrations..."
python manage.py migrate --run-syncdb
echo -e " ${GREEN}[OK]${RESET} Migrations applied"

# ── Static files ──────────────────────────────────────────────────────────────
echo ""
echo -e " ${CYAN}[3/4]${RESET} Collecting static files..."
python manage.py collectstatic --noinput --clear -v 0
echo -e " ${GREEN}[OK]${RESET} Static files ready"

# ── Run server ────────────────────────────────────────────────────────────────
echo ""
echo -e " ${CYAN}[4/4]${RESET} Starting development server..."
echo ""
echo -e " ${GREEN}----------------------------------------"
echo -e "  Open:   http://127.0.0.1:8000"
echo -e "  Admin:  http://127.0.0.1:8000/admin/"
echo -e "  Stop:   Ctrl+C"
echo -e " ----------------------------------------${RESET}"
echo ""
python manage.py runserver
