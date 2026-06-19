#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations OK"

echo "[entrypoint] Starting uvicorn..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
