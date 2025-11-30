#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME"; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - checking if database exists..."

# Check if database exists, create if not
PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USERNAME" -tc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_MAIN_DATABASE'" | grep -q 1 || \
PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USERNAME" -c "CREATE DATABASE $POSTGRES_MAIN_DATABASE"

echo "Database ready - running migrations..."
cd /app/models/db_schemes/firmy

# Check if alembic.ini exists, if not copy from example
if [ ! -f "alembic.ini" ]; then
    if [ -f "alembic.ini.example" ]; then
        echo "Creating alembic.ini from example..."
        cp alembic.ini.example alembic.ini
        # Update the sqlalchemy.url in alembic.ini
        sed -i "s|sqlalchemy.url.*|sqlalchemy.url = postgresql+asyncpg://${POSTGRES_USERNAME}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_MAIN_DATABASE}|g" alembic.ini
    else
        echo "Warning: alembic.ini.example not found, skipping migrations"
    fi
fi

# Run migrations if alembic.ini exists
if [ -f "alembic.ini" ]; then
    echo "Running alembic migrations..."
    alembic upgrade head || echo "Migration failed or no migrations to run"
else
    echo "Skipping migrations - alembic.ini not configured"
fi

cd /app

echo "Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
