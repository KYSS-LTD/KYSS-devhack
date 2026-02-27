#!/usr/bin/env bash
set -euo pipefail

DOMAIN=${DOMAIN:-quizbattle.kyssltd.ru}
EMAIL=${EMAIL:-admin@kyssltd.ru}

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI is required"
  exit 1
fi

echo "[1/3] Starting app+nginx for ACME challenge..."
docker compose up -d app nginx

echo "[2/3] Requesting/renewing Let's Encrypt certificate for ${DOMAIN}..."
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  --keep-until-expiring

echo "[3/3] Reloading nginx..."
docker compose exec nginx nginx -s reload

echo "Done. SSL is configured for https://${DOMAIN}"
