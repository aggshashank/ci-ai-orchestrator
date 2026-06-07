#!/bin/bash
# Run Alembic migrations to head.
# Expects DATABASE_URL to be set in the environment.
set -e

echo "[init-db] Running Alembic migrations..."
cd /app
python -m alembic -c db/migrations/alembic.ini upgrade head
echo "[init-db] Migrations complete."
