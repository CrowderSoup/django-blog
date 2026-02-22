#!/usr/bin/env sh
set -eu

cd /app

uv run manage.py startup

exec "$@"
