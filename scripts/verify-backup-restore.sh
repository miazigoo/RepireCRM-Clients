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
DEPLOY_SSH_PORT="${DEPLOY_SSH_PORT:-22}"
DEPLOY_SSH_KEY_PATH="${DEPLOY_SSH_KEY_PATH:-}"
RESTORE_DUMP_FILE="${RESTORE_DUMP_FILE:-}"

REMOTE="${DEPLOY_USER}@${DEPLOY_HOST}"

SSH_CMD=(ssh -p "$DEPLOY_SSH_PORT" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [[ -n "$DEPLOY_SSH_KEY_PATH" ]]; then
  SSH_CMD+=(-i "$DEPLOY_SSH_KEY_PATH")
fi

REMOTE_ENV=(
  "DEPLOY_PATH=$(quote "$DEPLOY_PATH")"
  "DEPLOY_ENV_FILE=$(quote "$DEPLOY_ENV_FILE")"
  "DEPLOY_COMPOSE_PROJECT=$(quote "$DEPLOY_COMPOSE_PROJECT")"
  "RESTORE_DUMP_FILE=$(quote "$RESTORE_DUMP_FILE")"
)

echo "Running client portal backup restore drill on ${REMOTE}"

"${SSH_CMD[@]}" "$REMOTE" "${REMOTE_ENV[*]} bash -s" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

cd "$DEPLOY_PATH"
test -f "$DEPLOY_ENV_FILE"

docker compose -p "$DEPLOY_COMPOSE_PROJECT" --env-file "$DEPLOY_ENV_FILE" exec -T \
  -e RESTORE_DUMP_FILE="$RESTORE_DUMP_FILE" \
  db-backup sh -s <<'CONTAINER_SCRIPT'
set -eu

dump_file="${RESTORE_DUMP_FILE:-}"
if [ -z "$dump_file" ]; then
  dump_file="$(ls -1t /backups/"${POSTGRES_DB}"-*.dump 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$dump_file" ] || [ ! -f "$dump_file" ]; then
  echo "No PostgreSQL dump found in /backups" >&2
  exit 3
fi

restore_db="restore_check_$(date -u +%Y%m%d%H%M%S)"
export PGPASSWORD="$POSTGRES_PASSWORD"

cleanup() {
  dropdb \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "$POSTGRES_USER" \
    --if-exists \
    "$restore_db" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Using dump: ${dump_file}"
echo "Creating temporary restore database: ${restore_db}"

createdb \
  -h "${POSTGRES_HOST:-postgres}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  "$restore_db"

pg_restore \
  -h "${POSTGRES_HOST:-postgres}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  -d "$restore_db" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  "$dump_file"

table_count="$(psql \
  -h "${POSTGRES_HOST:-postgres}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  -d "$restore_db" \
  -Atc "select count(*) from information_schema.tables where table_schema = 'public';")"

alembic_count="$(psql \
  -h "${POSTGRES_HOST:-postgres}" \
  -p "${POSTGRES_PORT:-5432}" \
  -U "$POSTGRES_USER" \
  -d "$restore_db" \
  -Atc "select count(*) from alembic_version;")"

if [ "$table_count" -lt 10 ]; then
  echo "Restore check failed: expected at least 10 public tables, got ${table_count}" >&2
  exit 4
fi

if [ "$alembic_count" -lt 1 ]; then
  echo "Restore check failed: alembic_version is empty" >&2
  exit 5
fi

echo "Restore check passed: ${table_count} tables, ${alembic_count} alembic version row(s)"
CONTAINER_SCRIPT
REMOTE_SCRIPT

echo "Client portal backup restore drill completed"
