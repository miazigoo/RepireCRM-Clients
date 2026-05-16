#!/bin/sh

set -u

log() {
  printf '%s %s\n' "$(date -Iseconds)" "$*"
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

  find /backups \
    -type f \
    -name "${POSTGRES_DB}-*.dump" \
    -mtime +"${POSTGRES_BACKUP_RETENTION_DAYS:-14}" \
    -delete
)

log "Backup service started"

while true; do
  if create_backup; then
    log "Backup completed"
  else
    status=$?
    log "Backup failed with exit code ${status}"
  fi

  sleep "${POSTGRES_BACKUP_INTERVAL_SECONDS:-86400}"
done
