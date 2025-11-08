#!/bin/bash
set -euo pipefail
SERVICE_NAME=styleadvisor.service
UNIT_SRC=infra/styleadvisor.service
UNIT_DST=/etc/systemd/system/${SERVICE_NAME}
if [ ! -f "$UNIT_SRC" ]; then echo "no $UNIT_SRC"; exit 1; fi
sudo cp "$UNIT_SRC" "$UNIT_DST"
sudo chmod 644 "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status --no-pager "$SERVICE_NAME"

