#!/bin/sh
set -e

# Ensure required runtime directories exist
mkdir -p /app/data /app/logs /app/app/static/uploads /home/appuser

# Fix volume permissions if running as root
if [ "$(id -u)" = "0" ]; then
    chown -R appuser:appuser /app/data /app/logs /app/app/static/uploads /home/appuser
    chmod -R 775 /app/data /app/logs /app/app/static/uploads
    exec gosu appuser "$@"
fi

exec "$@"
