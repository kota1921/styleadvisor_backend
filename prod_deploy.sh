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

OS="$(uname -s)"
USE_BREW=0
if [[ "$OS" == "Darwin" ]] && command -v brew >/dev/null 2>&1 && brew list nginx >/dev/null 2>&1; then
  USE_BREW=1
fi

if ! command -v nginx >/dev/null 2>&1; then
  log_error "nginx не установлен"; exit 1
fi

log_info "Проверка синтаксиса nginx"
if [ $USE_BREW -eq 1 ]; then
  if nginx -t 2>&1 | tee /tmp/nginx_prod_output; then
    log_ok "Синтаксис OK (brew)"
  else
    log_error "nginx -t FAILED"; exit 1
  fi
else
  if sudo nginx -t 2>&1 | tee /tmp/nginx_prod_output; then
    log_ok "Синтаксис OK (system)"
  else
    log_error "sudo nginx -t FAILED"; exit 1
  fi
fi

if [ "${DRY_RUN:-0}" = "1" ]; then
  log_info "DRY_RUN=1 — перезагрузка пропущена"; exit 0
fi

reload_nginx(){
  if [ $USE_BREW -eq 1 ]; then
    if [ "$EUID" -eq 0 ]; then
      log_warn "macOS brew nginx: запущено под sudo — избегайте. Использую 'nginx -s reload'"
      if nginx -s reload; then return 0; fi
      return 1
    fi
    if brew services restart nginx; then return 0; fi
    log_warn "brew services restart не удалось, пробую 'nginx -s reload'"
    if nginx -s reload; then return 0; fi
    return 1
  else
    if command -v systemctl >/dev/null 2>&1; then
      if sudo systemctl reload nginx; then return 0; fi
      log_warn "systemctl reload не удалось, пробую 'sudo nginx -s reload'"
    fi
    if sudo nginx -s reload; then return 0; fi
    return 1
  fi
}

log_info "Перезагрузка nginx"
if reload_nginx; then
  log_ok "nginx reload OK"
else
  log_error "nginx reload FAILED"; exit 1
fi

if pgrep nginx >/dev/null 2>&1; then
  log_ok "nginx запущен"
else
  log_error "nginx не запущен"; exit 1
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

  log_info "Подготовка продового сервера"

  if [ -d "$VENVDIR" ]; then
    log_info "Удаление старого venv"
    rm -rf "$VENVDIR"
  fi

  log_info "Создание venv"
  $PYTHON_BIN -m venv "$VENVDIR"

  source "$VENVDIR/bin/activate"

  log_info "Обновление pip"
  pip install --no-cache-dir --upgrade pip -q || log_warn "Не удалось обновить pip"

  if [ -f "$REQFILE" ]; then
    log_info "Установка зависимостей"
    pip install --no-cache-dir -q -r "$REQFILE" || log_warn "Не удалось установить зависимости"
  else
    log_warn "requirements.txt не найден, пропуск установки зависимостей"
  fi

  if ! python -c "import server" 2>/dev/null; then
    log_error "Импорт server.py не удался"; exit 1
  fi
  log_ok "Импорт server.py успешен"

  # Прогон тестов
  if [ "${SKIP_TESTS:-0}" != "1" ]; then
    if python -c "import pytest" 2>/dev/null; then
      log_info "Запуск тестов"
      export PYTHONPATH="$APP_DIR"
      if pytest -q; then
        log_ok "Тесты прошли"
      else
        log_error "Тесты не прошли"; exit 1
      fi
    else
      log_warn "pytest не установлен, пропуск тестов"
    fi
  else
    log_info "SKIP_TESTS=1, пропуск тестов"
  fi

  # Остановка старого Gunicorn
  if [ -f /tmp/gunicorn_prod.pid ]; then
    OLD_PID=$(cat /tmp/gunicorn_prod.pid)
    if ps -p $OLD_PID >/dev/null 2>&1; then
      log_info "Остановка старого Gunicorn (PID=$OLD_PID)"
      kill $OLD_PID 2>/dev/null || true
      sleep 2
      if ps -p $OLD_PID >/dev/null 2>&1; then
        log_warn "Принудительная остановка Gunicorn"
        kill -9 $OLD_PID 2>/dev/null || true
      fi
    fi
    rm -f /tmp/gunicorn_prod.pid
  fi

  # Проверка что порт свободен
  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    log_error "Порт 8000 всё ещё занят"; exit 1
  fi

  mkdir -p "$LOG_DIR"
  log_info "Запуск Gunicorn (production)"
  $GUNICORN_CMD --access-logfile "$LOG_DIR/access.log" --error-logfile "$LOG_DIR/error.log" --daemon
  sleep 2

  # Найти PID Gunicorn
  GUNICORN_PID=$(pgrep -f "gunicorn.*server:app" | head -1)
  if [ -z "$GUNICORN_PID" ]; then
    log_error "Gunicorn не запустился"
    if [ -f "$LOG_DIR/error.log" ]; then
      log_error "Логи Gunicorn:"
      tail -n 20 "$LOG_DIR/error.log"
    fi
    exit 1
  fi

  echo "$GUNICORN_PID" > /tmp/gunicorn_prod.pid
  log_ok "Gunicorn запущен (PID=$GUNICORN_PID)"

  # Health-check
  log_info "Health-check (timeout=${HEALTH_TIMEOUT}s)"
  start_ts=$(date +%s)
  health_ok=0
  while true; do
    if ! ps -p $GUNICORN_PID >/dev/null 2>&1; then
      log_error "Gunicorn процесс завершился досрочно"; exit 1
    fi
    code=$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$code" =~ ^[0-9]{3}$ ]]; then
      if [ "$code" -ge 200 ] && [ "$code" -lt 500 ]; then
        health_ok=1; break
      fi
    fi
    now=$(date +%s)
    if [ $((now - start_ts)) -ge $HEALTH_TIMEOUT ]; then
      log_error "Health-check провалился за ${HEALTH_TIMEOUT}s (код=$code)"; exit 1
    fi
    sleep 1
  done
  if [ $health_ok -eq 1 ]; then
    log_ok "Health-check успешен (код=$code)"
  fi

  log_info "Gunicorn работает (остановка: kill $GUNICORN_PID)"
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
        log_info "Последние 10 строк $lf"; tail -n 10 "$lf" || true
      else
        if [[ "$lf" == /var/log/nginx/error.log ]]; then
          log_info "Последние 10 строк $lf"; sudo tail -n 10 "$lf" || true
        else
          log_info "Последние 10 строк $lf"; tail -n 10 "$lf" || true
        fi
      fi
      break
    fi
  done
fi

log_ok "PROD DEPLOY SUCCESS"

