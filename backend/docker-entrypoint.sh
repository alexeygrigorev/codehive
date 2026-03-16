#!/bin/bash
set -e

# Run Alembic migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start uvicorn with factory pattern
echo "Starting uvicorn..."
exec uvicorn codehive.api.app:create_app --factory --host 0.0.0.0 --port 7433
