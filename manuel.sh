#!/bin/bash

# GlichFlow Manual Installation Script
# Usage:
#   curl -sSL http://glichflow.glitchidea.com/shell/manual.sh | bash
# or
#   bash manual.sh

set -euo pipefail

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}🚀 Starting GlichFlow Manual Installation...${NC}"
echo "================================================"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo -e "${RED}❌ $1 not found.${NC}"; return 1; }
}

need_cmd python3
need_cmd pip3
need_cmd git
echo -e "${GREEN}✅ Python3, pip3 and Git are ready${NC}"

# (Optional) PostgreSQL and Redis checks
if ! command -v psql >/dev/null 2>&1; then
  echo -e "${YELLOW}ℹ️  'psql' not found (PostgreSQL CLI). Install it if you plan to use local PostgreSQL.${NC}"
fi
if ! command -v redis-cli >/dev/null 2>&1; then
  echo -e "${YELLOW}ℹ️  'redis-cli' not found. Install it if you plan to use local Redis.${NC}"
fi

# Project directory
PROJECT_DIR="glichflow"
if [ -d "$PROJECT_DIR" ]; then
  echo -e "${YELLOW}⚠️  Directory $PROJECT_DIR exists, creating backup...${NC}"
  mv "$PROJECT_DIR" "${PROJECT_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
fi

echo -e "${BLUE}📁 Creating project directory: $PROJECT_DIR${NC}"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Clone repository
REPO_URL="https://github.com/glitchidea/glichflow.git"
echo -e "${BLUE}📥 Cloning repository: ${REPO_URL}${NC}"
git clone "$REPO_URL" . 2>/dev/null || git pull --rebase

# Python virtualenv
echo -e "${BLUE}🐍 Creating virtual environment...${NC}"
python3 -m venv venv

# Activate venv
if [ -f "venv/bin/activate" ]; then
  # Linux/Mac
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
  # Windows (Git Bash/WSL)
  # shellcheck disable=SC1091
  source venv/Scripts/activate
else
  echo -e "${RED}❌ Could not activate venv. Aborting.${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# Dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip3 install --upgrade pip
pip3 install -r requirements.txt

# .env (create minimal if missing)
if [ ! -f ".env" ]; then
  echo -e "${BLUE}🧩 Creating .env (minimal)...${NC}"
  cat > .env << 'EOF'
DEBUG=True
SECRET_KEY=change_me_please
DATABASE_URL=postgresql://postgres:password@localhost:5432/glichflow
REDIS_URL=redis://localhost:6379/0
EOF
fi

# Django migrate + collectstatic
echo -e "${BLUE}🗄️  Running database migrations...${NC}"
python manage.py migrate

echo -e "${BLUE}🧰 Collecting static files...${NC}"
python manage.py collectstatic --noinput || true

# Superuser (optional)
echo -e "${BLUE}👤 Create admin user (optional).${NC}"
read -p "Create admin? [y/N]: " CREATE_SU
if [[ "${CREATE_SU:-N}" =~ ^[Yy]$ ]]; then
  python manage.py createsuperuser
fi

echo ""
echo "================================================"
echo -e "${GREEN}🎉 GlichFlow installed successfully!${NC}"
echo -e "${GREEN}✅ Site:${NC} http://127.0.0.1:8000"
echo -e "${GREEN}✅ Admin Panel:${NC} http://127.0.0.1:8000/admin"
echo ""
echo -e "${YELLOW}📋 Useful Commands:${NC}"
echo "• Activate venv (Linux/Mac): source venv/bin/activate"
echo "• Activate venv (Windows Git Bash/WSL): source venv/Scripts/activate"
echo "• Start server: python manage.py runserver"
echo "• Stop server: Ctrl+C"
echo "• Deactivate venv: deactivate"
echo ""
echo -e "${BLUE}🚀 Happy hacking!${NC}"