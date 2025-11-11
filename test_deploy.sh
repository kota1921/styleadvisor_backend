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
  if nginx -t 2>&1 | tee /tmp/nginx_test_output; then
    log_ok "Синтаксис OK (brew)"
  else
    log_error "nginx -t FAILED"; exit 1
  fi
else
  if sudo nginx -t 2>&1 | tee /tmp/nginx_test_output; then
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

  log_info "Проверка Flask сервера"

  # Очистка старого venv
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

  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    log_warn "Порт 8000 занят, пропуск запуска"
  else
    log_info "Запуск Flask dev server"
    python -m flask --app server run --host 127.0.0.1 --port 8000 >/tmp/flask_test.log 2>&1 &
    FLASK_PID=$!
    sleep 3
    if ps -p $FLASK_PID >/dev/null 2>&1; then
      log_ok "Flask запущен (PID=$FLASK_PID)"
      if curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/auth/google | grep -qE '^[0-9]{3}$'; then
        log_ok "Flask отвечает на запросы"
      else
        log_warn "Flask не отвечает на запросы"
      fi
      log_info "Flask оставлен запущенным (остановка: kill $FLASK_PID)"
      echo "$FLASK_PID" > /tmp/flask_test.pid
    else
      log_error "Flask не запустился"
      if [ -f /tmp/flask_test.log ]; then
        log_error "Логи Flask:"
        cat /tmp/flask_test.log
      fi
      exit 1
    fi
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

log_ok "TEST DEPLOY SUCCESS"
