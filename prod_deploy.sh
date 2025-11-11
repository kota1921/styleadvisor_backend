#!/bin/bash
# === Production deploy script ===
# Шаги:
# 1. Проверка nginx синтаксиса и перезагрузка.
# 2. Очистка venv, установка зависимостей.
# 3. Проверка импорта server.py.
# 4. Запуск тестов.
# 5. Остановка старого Gunicorn (если запущен).
# 6. Запуск продового сервера Gunicorn.
# 7. Health-check.
# Переменные: DRY_RUN=1, VERBOSE=1, SKIP_SERVER=1, SKIP_TESTS=1

if [ -z "$BASH_VERSION" ]; then echo "[ERROR] Используйте bash"; exit 1; fi
set -euo pipefail

log_error(){ echo -e "\033[0;31m[ERROR]\033[0m $1"; }
log_ok(){ echo -e "\033[0;32m[OK]\033[0m $1"; }
log_info(){ echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_warn(){ echo -e "\033[0;33m[WARN]\033[0m $1"; }

TOTAL_STEPS=7
CURRENT_STEP=0

print_progress(){
  local step=$1
  local message="$2"
  CURRENT_STEP=$step
  local percent=$((step * 100 / TOTAL_STEPS))
  local bar_len=40
  local filled=$((bar_len * step / TOTAL_STEPS))
  local empty=$((bar_len - filled))
  printf "\r\033[2K"
  printf "\033[1;36m[%3d%%]\033[0m [" "$percent"
  printf "%${filled}s" | tr ' ' '█'
  printf "%${empty}s" | tr ' ' '░'
  printf "] \033[1;37m%s\033[0m" "$message"
  if [ "$step" -eq "$TOTAL_STEPS" ]; then echo ""; fi
}

step_done(){
  local message="${1:-}"
  if [ -n "$message" ]; then
    printf "\r\033[2K"
    log_ok "$message"
  fi
}

step_fail(){
  local message="$1"
  printf "\r\033[2K"
  log_error "$message"
}

OS="$(uname -s)"
USE_BREW=0
if [[ "$OS" == "Darwin" ]] && command -v brew >/dev/null 2>&1 && brew list nginx >/dev/null 2>&1; then
  USE_BREW=1
fi

if ! command -v nginx >/dev/null 2>&1; then
  log_error "nginx не установлен"; exit 1
fi

print_progress 1 "Проверка nginx..."
if [ $USE_BREW -eq 1 ]; then
  if nginx -t >/tmp/nginx_prod_output 2>&1; then
    step_done "nginx синтаксис OK (brew)"
  else
    step_fail "nginx -t FAILED"; cat /tmp/nginx_prod_output; exit 1
  fi
else
  if sudo nginx -t >/tmp/nginx_prod_output 2>&1; then
    step_done "nginx синтаксис OK (system)"
  else
    step_fail "sudo nginx -t FAILED"; cat /tmp/nginx_prod_output; exit 1
  fi
fi

if [ "${DRY_RUN:-0}" = "1" ]; then
  log_info "DRY_RUN=1 — перезагрузка пропущена"; exit 0
fi

reload_nginx(){
  if [ $USE_BREW -eq 1 ]; then
    if [ "$EUID" -eq 0 ]; then
      if nginx -s reload; then return 0; fi
      return 1
    fi
    if brew services restart nginx >/dev/null 2>&1; then return 0; fi
    if nginx -s reload >/dev/null 2>&1; then return 0; fi
    return 1
  else
    if command -v systemctl >/dev/null 2>&1; then
      if sudo systemctl reload nginx >/dev/null 2>&1; then return 0; fi
    fi
    if sudo nginx -s reload >/dev/null 2>&1; then return 0; fi
    return 1
  fi
}

print_progress 2 "Перезагрузка nginx..."
if reload_nginx; then
  if pgrep nginx >/dev/null 2>&1; then
    step_done "nginx перезагружен и запущен"
  else
    step_fail "nginx не запущен"; exit 1
  fi
else
  step_fail "nginx reload FAILED"; exit 1
fi

# --- Проверка и запуск продового сервера ---
if [ "${SKIP_SERVER:-0}" != "1" ]; then
  APP_DIR="$(pwd)"
  VENVDIR="${VENVDIR:-$APP_DIR/.venv}"
  PYTHON_BIN="${PYTHON_BIN:-python3}"
  REQFILE="${REQFILE:-$APP_DIR/requirements.txt}"
  GUNICORN_CMD="${GUNICORN_CMD:-gunicorn -w 4 server:app --bind 0.0.0.0:8000}"
  LOG_DIR="${LOG_DIR:-$APP_DIR/logs}"
  HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/auth/google}"
  HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-30}"

  print_progress 3 "Подготовка окружения..."
  if [ -d "$VENVDIR" ]; then rm -rf "$VENVDIR"; fi
  $PYTHON_BIN -m venv "$VENVDIR"
  source "$VENVDIR/bin/activate"
  pip install --no-cache-dir --upgrade pip -q >/dev/null 2>&1 || true
  if [ -f "$REQFILE" ]; then
    pip install --no-cache-dir -q -r "$REQFILE" >/dev/null 2>&1
  fi
  step_done "venv создан, зависимости установлены"

  print_progress 4 "Проверка кода..."
  if ! python -c "import server" 2>/dev/null; then
    step_fail "Импорт server.py не удался"; exit 1
  fi
  step_done "Импорт server.py успешен"

  if [ "${SKIP_TESTS:-0}" != "1" ]; then
    print_progress 5 "Запуск тестов..."
    if python -c "import pytest" 2>/dev/null; then
      export PYTHONPATH="$APP_DIR"
      if pytest -q >/tmp/pytest_prod_output 2>&1; then
        step_done "Тесты прошли"
      else
        step_fail "Тесты не прошли"; cat /tmp/pytest_prod_output; exit 1
      fi
    else
      step_done "pytest не установлен, пропуск"
    fi
  else
    print_progress 5 "Тесты пропущены (SKIP_TESTS=1)"
    step_done ""
  fi

  print_progress 6 "Запуск Gunicorn..."
  if [ -f /tmp/gunicorn_prod.pid ]; then
    OLD_PID=$(cat /tmp/gunicorn_prod.pid)
    if ps -p $OLD_PID >/dev/null 2>&1; then
      kill $OLD_PID 2>/dev/null || true
      sleep 2
      if ps -p $OLD_PID >/dev/null 2>&1; then kill -9 $OLD_PID 2>/dev/null || true; fi
    fi
    rm -f /tmp/gunicorn_prod.pid
  fi

  # Проверка и освобождение порта 8000
  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    PORT_PID=$(lsof -nP -iTCP:8000 -sTCP:LISTEN | tail -1 | awk '{print $2}')
    if [ -n "$PORT_PID" ]; then
      kill $PORT_PID 2>/dev/null || true
      sleep 2
      if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
        kill -9 $PORT_PID 2>/dev/null || true
        sleep 1
      fi
    fi
  fi

  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    step_fail "Порт 8000 всё ещё занят после принудительной остановки"; exit 1
  fi

  mkdir -p "$LOG_DIR"
  $GUNICORN_CMD --access-logfile "$LOG_DIR/access.log" --error-logfile "$LOG_DIR/error.log" --daemon
  sleep 2
  GUNICORN_PID=$(pgrep -f "gunicorn.*server:app" | head -1)
  if [ -z "$GUNICORN_PID" ]; then
    step_fail "Gunicorn не запустился"
    if [ -f "$LOG_DIR/error.log" ]; then tail -n 20 "$LOG_DIR/error.log"; fi
    exit 1
  fi
  echo "$GUNICORN_PID" > /tmp/gunicorn_prod.pid
  step_done "Gunicorn запущен (PID=$GUNICORN_PID)"

  print_progress 7 "Health-check..."
  start_ts=$(date +%s)
  health_ok=0
  while true; do
    if ! ps -p $GUNICORN_PID >/dev/null 2>&1; then
      step_fail "Gunicorn завершился досрочно"; exit 1
    fi
    code=$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$code" =~ ^[0-9]{3}$ ]]; then
      if [ "$code" -ge 200 ] && [ "$code" -lt 500 ]; then
        health_ok=1; break
      fi
    fi
    now=$(date +%s)
    elapsed=$((now - start_ts))
    if [ $elapsed -ge $HEALTH_TIMEOUT ]; then
      step_fail "Health-check провалился (код=$code)"; exit 1
    fi
    print_progress 7 "Health-check... ${elapsed}/${HEALTH_TIMEOUT}s"
    sleep 1
  done
  if [ $health_ok -eq 1 ]; then
    step_done "Health-check успешен (код=$code)"
  fi
fi

if [ "${VERBOSE:-0}" = "1" ]; then
  LOG_CANDIDATES=(
    /var/log/nginx/error.log
    /usr/local/var/log/nginx/error.log
    /opt/homebrew/var/log/nginx/error.log
  )
  for lf in "${LOG_CANDIDATES[@]}"; do
    if [ -f "$lf" ]; then
      if [ $USE_BREW -eq 1 ]; then
        echo ""; log_info "Последние 10 строк $lf"; tail -n 10 "$lf" || true
      else
        if [[ "$lf" == /var/log/nginx/error.log ]]; then
          echo ""; log_info "Последние 10 строк $lf"; sudo tail -n 10 "$lf" || true
        else
          echo ""; log_info "Последние 10 строк $lf"; tail -n 10 "$lf" || true
        fi
      fi
      break
    fi
  done
fi

echo ""
log_ok "PROD DEPLOY SUCCESS"

