#!/bin/bash
# === Local nginx config test script ===
# Linux (systemd) -> sudo systemctl reload nginx
# macOS (brew nginx) -> brew services restart nginx (без sudo), иначе nginx -s reload
# Переменные: DRY_RUN=1, VERBOSE=1, SKIP_SERVER=1 (пропуск запуска Flask)

if [ -z "$BASH_VERSION" ]; then echo "[ERROR] Используйте bash"; exit 1; fi
set -euo pipefail

log_error(){ echo -e "\033[0;31m[ERROR]\033[0m $1"; }
log_ok(){ echo -e "\033[0;32m[OK]\033[0m $1"; }
log_info(){ echo -e "\033[0;34m[INFO]\033[0m $1"; }
log_warn(){ echo -e "\033[0;33m[WARN]\033[0m $1"; }

TOTAL_STEPS=6
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
  if nginx -t >/tmp/nginx_test_output 2>&1; then
    step_done "nginx синтаксис OK (brew)"
  else
    step_fail "nginx -t FAILED"; cat /tmp/nginx_test_output; exit 1
  fi
else
  if sudo nginx -t >/tmp/nginx_test_output 2>&1; then
    step_done "nginx синтаксис OK (system)"
  else
    step_fail "sudo nginx -t FAILED"; cat /tmp/nginx_test_output; exit 1
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

# Проверка что nginx запущен
if pgrep nginx >/dev/null 2>&1; then
  log_ok "nginx запущен"
else
  log_error "nginx не запущен"; exit 1
fi

# --- Проверка и запуск Flask сервера ---
if [ "${SKIP_SERVER:-0}" != "1" ]; then
  APP_DIR="$(pwd)"
  VENVDIR="${VENVDIR:-$APP_DIR/.venv}"
  PYTHON_BIN="${PYTHON_BIN:-python3}"
  REQFILE="${REQFILE:-$APP_DIR/requirements.txt}"

  print_progress 3 "Подготовка окружения..."
  # Очистка старого venv
  if [ -d "$VENVDIR" ]; then
    rm -rf "$VENVDIR"
  fi

  # Создание venv
  $PYTHON_BIN -m venv "$VENVDIR"

  source "$VENVDIR/bin/activate"

  # Обновление pip
  pip install --no-cache-dir --upgrade pip -q >/dev/null 2>&1 || true

  if [ -f "$REQFILE" ]; then
    # Установка зависимостей
    pip install --no-cache-dir -q -r "$REQFILE" >/dev/null 2>&1
  fi
  step_done "venv создан, зависимости установлены"

  print_progress 4 "Проверка кода..."
  if ! python -c "import server" 2>/dev/null; then
    step_fail "Импорт server.py не удался"; exit 1
  fi

  if python -c "import pytest" 2>/dev/null; then
    export PYTHONPATH="$APP_DIR"
    if pytest -q >/tmp/pytest_test_output 2>&1; then
      step_done "Импорт OK, тесты прошли"
    else
      step_fail "Тесты не прошли"; cat /tmp/pytest_test_output; exit 1
    fi
  else
    step_done "Импорт OK, pytest не установлен"
  fi

  # Проверка и освобождение порта 8000
  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    # Агрессивное освобождение порта 8000
    MAX_ATTEMPTS=5
    for attempt in $(seq 1 $MAX_ATTEMPTS); do
      if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
        break
      fi

      PORT_PIDS=$(lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null | grep LISTEN | awk '{print $2}' | sort -u)

      if [ -n "$PORT_PIDS" ]; then
        for pid in $PORT_PIDS; do
          if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
            kill -9 $pid 2>/dev/null || true
          else
            kill $pid 2>/dev/null || true
          fi
        done
      fi

      sleep 1
    done

    if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
      step_fail "Порт 8000 занят после $MAX_ATTEMPTS попыток"
      echo ""
      log_error "Процессы на порту 8000:"
      lsof -nP -iTCP:8000 -sTCP:LISTEN
      exit 1
    fi
    step_done "Порт 8000 освобождён"
  fi

  print_progress 5 "Запуск Flask dev server..."
  python -m flask --app server run --host 127.0.0.1 --port 8000 >/tmp/flask_test.log 2>&1 &
  FLASK_PID=$!
  sleep 3
  if ps -p $FLASK_PID >/dev/null 2>&1; then
    step_done "Flask запущен (PID=$FLASK_PID)"
    print_progress 6 "Проверка ответа Flask..."
    if curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/auth/google | grep -qE '^[0-9]{3}$'; then
      step_done "Flask отвечает, оставлен запущенным"
      echo "$FLASK_PID" > /tmp/flask_test.pid
    else
      step_fail "Flask не отвечает на запросы"
    fi
  else
    step_fail "Flask не запустился"
    if [ -f /tmp/flask_test.log ]; then cat /tmp/flask_test.log; fi
    exit 1
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
log_ok "TEST DEPLOY SUCCESS"
