#!/usr/bin/env bash
# Run migrations then start the API. Used as container entrypoint so every deploy applies migrations.
set -e
cd /app
echo "Running database migrations..."
python -m alembic upgrade head || { echo "Migration failed"; exit 1; }
echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
