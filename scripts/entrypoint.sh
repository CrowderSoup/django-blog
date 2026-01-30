#!/usr/bin/env sh
set -eu

DB_WAIT="${DB_WAIT:-true}"
COLLECTSTATIC="${COLLECTSTATIC:-true}"
STORAGE_BOOTSTRAP="${STORAGE_BOOTSTRAP:-true}"

if [ "$DB_WAIT" = "true" ]; then
  echo "Waiting for database..."
  uv run python scripts/wait_for_db.py
fi

uv run manage.py migrate --noinput

if [ "$STORAGE_BOOTSTRAP" = "true" ]; then
  uv run manage.py bootstrap_storage
fi

if [ "$COLLECTSTATIC" = "true" ]; then
  uv run manage.py collectstatic --noinput
fi

exec "$@"
