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

function log_error {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}
function log_ok {
    echo -e "\033[0;32m[OK]\033[0m $1"
}

# 1. Проверка git
if ! command -v git >/dev/null 2>&1; then
    log_error "git не установлен"
    exit 1
fi

# 2. Проверка python
if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
    log_error "$PYTHON_BIN не найден"
    exit 1
fi

# 3. git pull
if [ -d .git ]; then
    git pull --rebase
else
    git clone "$REPO_URL" "$APP_DIR"
fi

# 4. venv
if [ ! -d "$VENVDIR" ]; then
    $PYTHON_BIN -m venv "$VENVDIR"
fi
source "$VENVDIR/bin/activate"

# 5. pip install
if [ -f "$REQFILE" ]; then
    pip install --upgrade pip
    pip install -r "$REQFILE"
else
    log_error "requirements.txt не найден"
    exit 1
fi

# 6. pytest
if ! pip show pytest >/dev/null 2>&1; then
    pip install pytest
fi
if pytest; then
    log_ok "Тесты прошли успешно"
else
    log_error "Тесты не прошли"
    exit 1
fi

# 7. gunicorn
if ! pip show gunicorn >/dev/null 2>&1; then
    pip install gunicorn
fi

log_ok "Запуск продакшен сервера..."
$GUNICORN_CMD &
GUNICORN_PID=$!
sleep 3
if ps -p $GUNICORN_PID > /dev/null; then
    log_ok "Сервер успешно запущен (PID $GUNICORN_PID)"
else
    log_error "Ошибка запуска gunicorn"
    exit 1
fi
