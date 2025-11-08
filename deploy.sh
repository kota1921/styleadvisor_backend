#!/bin/bash
# Проверка, что запущено под bash
if [ -z "$BASH_VERSION" ]; then
    echo "[ERROR] Запускайте скрипт через bash, а не sh."
    exit 1
fi
set -euo pipefail

REPO_URL="git@github.com:kota1921/styleadvisor_backend.git"
APP_DIR="$(pwd)"
PYTHON_BIN="python3"
VENVDIR="$APP_DIR/.venv"
REQFILE="$APP_DIR/requirements.txt"
GUNICORN_CMD="gunicorn -w 4 server:app --bind 0.0.0.0:8000"
LOG_DIR="$APP_DIR/logs"
DOMAIN=${DOMAIN:-}
CERT_EMAIL=${CERT_EMAIL:-}

function log_error { echo -e "\033[0;31m[ERROR]\033[0m $1"; }
function log_ok { echo -e "\033[0;32m[OK]\033[0m $1"; }

install_service() {
    local unit_src="$APP_DIR/infra/styleadvisor.service"
    local unit_dst="/etc/systemd/system/styleadvisor.service"
    if [ ! -f "$unit_src" ]; then log_error "нет $unit_src"; return 1; fi
    sudo cp "$unit_src" "$unit_dst"
    sudo chmod 644 "$unit_dst"
    sudo systemctl daemon-reload
    sudo systemctl enable --now styleadvisor.service
    sudo systemctl status --no-pager styleadvisor.service || true
    log_ok "systemd service установлен"
}

setup_nginx_ssl() {
    if [ -z "$DOMAIN" ]; then log_error "DOMAIN пуст"; return 1; fi
    if [ -z "$CERT_EMAIL" ]; then log_error "CERT_EMAIL пуст"; return 1; fi
    sudo apt update -y
    sudo apt install -y nginx certbot python3-certbot-nginx
    local cfg_src="$APP_DIR/infra/nginx_site.conf"
    local cfg_dst="/etc/nginx/sites-available/${DOMAIN}.conf"
    if [ ! -f "$cfg_src" ]; then log_error "нет $cfg_src"; return 1; fi
    sudo cp "$cfg_src" "$cfg_dst"
    sudo ln -sf "$cfg_dst" "/etc/nginx/sites-enabled/${DOMAIN}.conf"
    sudo nginx -t
    sudo systemctl reload nginx
    sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --agree-tos -m "$CERT_EMAIL" --redirect --non-interactive || log_error "certbot ошибка"
    log_ok "nginx+ssl готов"
}

# 1. Проверка git
if ! command -v git >/dev/null 2>&1; then log_error "git не установлен"; exit 1; fi
# 2. Проверка python
if ! command -v $PYTHON_BIN >/dev/null 2>&1; then log_error "$PYTHON_BIN не найден"; exit 1; fi
# 3. git pull
if [ -d .git ]; then git pull --rebase; else git clone "$REPO_URL" "$APP_DIR"; fi
# 4. venv
if [ ! -d "$VENVDIR" ]; then $PYTHON_BIN -m venv "$VENVDIR"; fi
source "$VENVDIR/bin/activate"
# 5. pip install
if [ -f "$REQFILE" ]; then pip install --upgrade pip; pip install -r "$REQFILE"; else log_error "requirements.txt не найден"; exit 1; fi
# 6. pytest
if ! pip show pytest >/dev/null 2>&1; then pip install pytest; fi
export PYTHONPATH="$APP_DIR"
if PYTHONPATH="$APP_DIR" pytest -q; then log_ok "Тесты прошли"; else log_error "Тесты не прошли"; exit 1; fi
# 7. gunicorn (или systemd/nginx)
if ! pip show gunicorn >/dev/null 2>&1; then pip install gunicorn; fi
mkdir -p "$LOG_DIR"

if [ "${INSTALL_SERVICE:-0}" = "1" ]; then install_service; fi
if [ "${INSTALL_NGINX_SSL:-0}" = "1" ]; then setup_nginx_ssl; fi

if [ "${INSTALL_SERVICE:-0}" = "1" ]; then
    log_ok "Локальный запуск пропущен (используется systemd)"
    exit 0
fi

log_ok "Запуск продакшен сервера..."
if [ "${DRY_RUN:-0}" = "1" ]; then log_ok "DRY_RUN=1"; exit 0; fi
if [ "${FOREGROUND:-0}" = "1" ]; then
    log_ok "FOREGROUND=1"
    exec $GUNICORN_CMD --access-logfile - --error-logfile -
else
    $GUNICORN_CMD --access-logfile "$LOG_DIR/access.log" --error-logfile "$LOG_DIR/error.log" &
    GUNICORN_PID=$!; sleep 3
    if ps -p $GUNICORN_PID > /dev/null; then log_ok "Сервер PID $GUNICORN_PID"; else log_error "gunicorn не стартовал"; exit 1; fi
fi
