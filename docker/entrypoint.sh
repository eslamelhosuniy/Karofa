#!/bin/bash
set -e

RAW_POSTGRES_PASSWORD="$POSTGRES_PASSWORD"

echo "Waiting for PostgreSQL to be ready..."
until PGPASSWORD="$RAW_POSTGRES_PASSWORD" pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME"; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - checking if database exists..."

# Check if database exists, create if not
PGPASSWORD=$RAW_POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USERNAME" -tc "SELECT 1 FROM pg_database WHERE datname = '$POSTGRES_MAIN_DATABASE'" | grep -q 1 || \
PGPASSWORD=$RAW_POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USERNAME" -c "CREATE DATABASE $POSTGRES_MAIN_DATABASE"

echo "Database ready - running migrations..."
cd /app/models/db_schemes/firmy

# URL encode the password for PostgreSQL connection string
# This handles special characters like @, $, etc.
ENCODED_PASSWORD=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${RAW_POSTGRES_PASSWORD}', safe=''))")
# Escape % as %% for .ini file format (ConfigParser requirement)
ENCODED_PASSWORD_INI=$(echo "$ENCODED_PASSWORD" | sed 's/%/%%/g')

# Always recreate alembic.ini to ensure correct database URL
if [ -f "alembic.ini.example" ]; then
    echo "Creating alembic.ini from example..."
    cp alembic.ini.example alembic.ini
    # Update the sqlalchemy.url in alembic.ini - use psycopg2 for migrations, not asyncpg
    sed -i "s|sqlalchemy.url.*|sqlalchemy.url = postgresql+psycopg2://${POSTGRES_USERNAME}:${ENCODED_PASSWORD_INI}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_MAIN_DATABASE}|g" alembic.ini
else
    echo "Warning: alembic.ini.example not found, skipping migrations"
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
export POSTGRES_PASSWORD="$ENCODED_PASSWORD"
exec uvicorn main:app --host 0.0.0.0 --port 8000
