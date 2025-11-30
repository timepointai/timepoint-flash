#!/bin/bash
# TIMEPOINT Flash startup script
# Runs migrations and starts the server

set -e

echo "=== TIMEPOINT Flash v2.0 ==="
echo "Environment: ${ENVIRONMENT:-development}"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

echo "Migrations complete."

# Start the application
echo "Starting uvicorn server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
