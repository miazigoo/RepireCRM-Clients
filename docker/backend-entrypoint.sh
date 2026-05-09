#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic -c /app/backend/alembic.ini upgrade head
fi

exec "$@"
