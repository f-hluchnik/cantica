#!/bin/sh
# Container entrypoint.
#
# Migrations and the calendar build run here, not in Fly's release_command, because the
# release machine does not mount the volume that holds the SQLite database.
set -eu

DB_PATH="${DATABASE_PATH:-/data/cantica.sqlite3}"
DB_DIR="$(dirname "$DB_PATH")"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DB_DIR"
    chown -R appuser:appuser "$DB_DIR"
    exec gosu appuser "$0" "$@"
fi

cd /app
python manage.py migrate --noinput
# A broken data commit must not take the site down: keep serving the previous build.
python manage.py calendar_build || echo "WARNING: calendar_build failed; serving the previous calendar data" >&2
# Curated data (songs, groups, rules) is edited in the admin; the YAML only seeds an empty DB.
python manage.py curation_import --if-empty || echo "WARNING: curation_import failed" >&2

exec gunicorn cantica.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 30 \
    --access-logfile -
