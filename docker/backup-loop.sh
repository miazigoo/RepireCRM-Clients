#!/bin/sh

set -u

log() {
  printf '%s %s\n' "$(date -Iseconds)" "$*"
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

notify() {
  if [ -z "${ALERT_WEBHOOK_URL:-}" ]; then
    return 0
  fi

  text="$(json_escape "$1")"
  curl -fsS -m "${ALERT_WEBHOOK_TIMEOUT_SECONDS:-10}" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"${text}\"}" \
    "$ALERT_WEBHOOK_URL" >/dev/null 2>&1 || true
}

configure_rclone() {
  if [ -n "${RCLONE_CONFIG_B64:-}" ]; then
    mkdir -p /config/rclone
    printf '%s' "$RCLONE_CONFIG_B64" | base64 -d > /config/rclone/rclone.conf
    export RCLONE_CONFIG=/config/rclone/rclone.conf
  fi
}

copy_offsite() {
  if [ -z "${BACKUP_RCLONE_REMOTE:-}" ]; then
    log "Offsite backup is disabled: BACKUP_RCLONE_REMOTE is empty"
    return 0
  fi

  configure_rclone
  log "Syncing backups to ${BACKUP_RCLONE_REMOTE}"
  rclone copy /backups "$BACKUP_RCLONE_REMOTE" \
    --max-age "${BACKUP_SYNC_MAX_AGE:-48h}" \
    --transfers "${BACKUP_RCLONE_TRANSFERS:-4}" \
    --checkers "${BACKUP_RCLONE_CHECKERS:-8}"
}

create_backup() (
  set -eu

  mkdir -p /backups
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  dump_file="/backups/${POSTGRES_DB}-${timestamp}.dump"

  log "Creating PostgreSQL backup: ${dump_file}"
  PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST:-postgres}" \
    -p "${POSTGRES_PORT:-5432}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -Fc \
    -f "${dump_file}"

  test -s "${dump_file}"

  copy_offsite

  find /backups \
    -type f \
    -name "${POSTGRES_DB}-*.dump" \
    -mtime +"${POSTGRES_BACKUP_RETENTION_DAYS:-14}" \
    -delete
)

log "Backup service started"

while true; do
  if create_backup; then
    notify "RepairCRM Client backup completed on $(hostname)"
  else
    status=$?
    log "Backup failed with exit code ${status}"
    notify "RepairCRM Client backup FAILED on $(hostname), exit code ${status}"
  fi

  sleep "${POSTGRES_BACKUP_INTERVAL_SECONDS:-86400}"
done
