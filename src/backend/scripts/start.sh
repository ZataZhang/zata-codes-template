#!/bin/sh
set -e

# Run database migrations before starting the application.
alembic upgrade head

# Start the server.
# NOTE: Update the module path if your ASGI application lives elsewhere.
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
