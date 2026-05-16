#!/usr/bin/env bash

set -Eeuo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 2
  fi
}

quote() {
  printf "%q" "$1"
}

require_env DEPLOY_HOST

DEPLOY_USER="${DEPLOY_USER:-root}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/repaircrm/client}"
DEPLOY_COMPOSE_PROJECT="${DEPLOY_COMPOSE_PROJECT:-repaircrm-client}"
DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-.env.production}"
DEPLOY_DOMAIN="${DEPLOY_DOMAIN:-repire-status.ru}"
DEPLOY_FRONTEND_PORT="${DEPLOY_FRONTEND_PORT:-8081}"
DEPLOY_SSH_PORT="${DEPLOY_SSH_PORT:-22}"
DEPLOY_SSH_KEY_PATH="${DEPLOY_SSH_KEY_PATH:-}"
DEPLOY_BACKUP_BEFORE_DEPLOY="${DEPLOY_BACKUP_BEFORE_DEPLOY:-true}"
DEPLOY_BACKUP_KEEP="${DEPLOY_BACKUP_KEEP:-5}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

SSH_CMD=(ssh -p "$DEPLOY_SSH_PORT" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$DEPLOY_SSH_KEY_PATH" ]]; then
  SSH_CMD+=(-i "$DEPLOY_SSH_KEY_PATH")
fi

RSYNC_SSH="${SSH_CMD[*]}"

echo "Deploying RepairCRM Client Portal to ${REMOTE}:${DEPLOY_PATH}"

"${SSH_CMD[@]}" "$REMOTE" "mkdir -p $(quote "$DEPLOY_PATH")"

rsync -az --delete \
  -e "$RSYNC_SSH" \
  --exclude '.git/' \
  --exclude '.env' \
  --exclude '.env.production' \
  --exclude 'venv/' \
  --exclude 'backend/.venv/' \
  --exclude 'node_modules/' \
  --exclude 'frontend/node_modules/' \
  --exclude 'frontend/dist/' \
  --exclude 'frontend/.angular/' \
  --exclude 'dist/' \
  --exclude '.angular/' \
  --exclude 'backups/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  "${ROOT_DIR}/" "${REMOTE}:${DEPLOY_PATH}/"

REMOTE_ENV=(
  "DEPLOY_PATH=$(quote "$DEPLOY_PATH")"
  "DEPLOY_ENV_FILE=$(quote "$DEPLOY_ENV_FILE")"
  "DEPLOY_COMPOSE_PROJECT=$(quote "$DEPLOY_COMPOSE_PROJECT")"
  "DEPLOY_DOMAIN=$(quote "$DEPLOY_DOMAIN")"
  "DEPLOY_FRONTEND_PORT=$(quote "$DEPLOY_FRONTEND_PORT")"
  "DEPLOY_BACKUP_BEFORE_DEPLOY=$(quote "$DEPLOY_BACKUP_BEFORE_DEPLOY")"
  "DEPLOY_BACKUP_KEEP=$(quote "$DEPLOY_BACKUP_KEEP")"
)

"${SSH_CMD[@]}" "$REMOTE" "${REMOTE_ENV[*]} bash -s" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

cd "$DEPLOY_PATH"
test -f "$DEPLOY_ENV_FILE"

compose() {
  docker compose -p "$DEPLOY_COMPOSE_PROJECT" --env-file "$DEPLOY_ENV_FILE" "$@"
}

compose config -q

case "$DEPLOY_BACKUP_KEEP" in
  ''|*[!0-9]*) DEPLOY_BACKUP_KEEP=5 ;;
esac

if [ "$DEPLOY_BACKUP_BEFORE_DEPLOY" = "true" ]; then
  backup_dir="${DEPLOY_PATH}/backups/pre-deploy"
  mkdir -p "$backup_dir"
  db_container="$(compose ps -q postgres || true)"
  if [ -n "$db_container" ] && [ "$(docker inspect -f '{{.State.Running}}' "$db_container" 2>/dev/null || true)" = "true" ]; then
    backup_file="${backup_dir}/client-predeploy-$(date -u +%Y%m%dT%H%M%SZ).dump"
    echo "Creating pre-deploy database backup: ${backup_file}"
    compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
    test -s "$backup_file"
    find "$backup_dir" -type f -name 'client-predeploy-*.dump' \
      | sort -r \
      | tail -n +"$((DEPLOY_BACKUP_KEEP + 1))" \
      | xargs -r rm -f
  else
    echo "Skipping pre-deploy backup: postgres container is not running"
  fi
fi

compose up -d --build --remove-orphans
compose ps

compose exec -T backend python - <<'PY'
from app.config import get_settings
from app.main import app

settings = get_settings()
assert settings.environment == "production"
assert app.title
print("backend settings ok")
PY

for path in /api/health /robots.txt /sitemap.xml /login; do
  status="$(curl -sS \
    -o /tmp/repaircrm-client-smoke-response \
    -w '%{http_code}' \
    -H "Host: ${DEPLOY_DOMAIN}" \
    -H "X-Forwarded-Proto: https" \
    "http://127.0.0.1:${DEPLOY_FRONTEND_PORT}${path}")"

  if [ "$status" != "200" ]; then
    echo "Smoke check failed for ${path} with HTTP ${status}" >&2
    cat /tmp/repaircrm-client-smoke-response >&2 || true
    exit 1
  fi
done
REMOTE_SCRIPT

echo "Deploy completed"
