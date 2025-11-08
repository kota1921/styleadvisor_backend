#!/bin/bash
set -euo pipefail
DOMAIN=${DOMAIN:-}
EMAIL=${EMAIL:-}
if [ -z "$DOMAIN" ]; then echo "DOMAIN required"; exit 1; fi
if [ -z "$EMAIL" ]; then echo "EMAIL required"; exit 1; fi
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
CFG_PATH="/etc/nginx/sites-available/$DOMAIN.conf"
TMP_CFG=$(mktemp)
cat > "$TMP_CFG" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
sudo mv "$TMP_CFG" "$CFG_PATH"
sudo ln -sf "$CFG_PATH" /etc/nginx/sites-enabled/$DOMAIN.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect --preferred-challenges http
sudo certbot renew --dry-run
echo OK
server {
    listen 80;
    server_name example.com www.example.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

