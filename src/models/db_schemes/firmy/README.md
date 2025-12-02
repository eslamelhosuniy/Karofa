## Run Alembic Migrations

### Configuration

```bash
cp alembic.ini.example alembic.ini
```

- Update the `alembic.ini` with your database credentials (`sqlalchemy.url`)

docker exec -it firmy-ai /bin/bash
cd /app/models/db_schemes/firmy

export POSTGRES_USERNAME=""
export POSTGRES_PASSWORD=""
export POSTGRES_HOST=""
export POSTGRES_PORT=""
export POSTGRES_MAIN_DATABASE=""
  
### (Optional) Create a new migration

```bash
alembic revision --autogenerate -m "Add ..."
```

### Upgrade the database

```bash
alembic upgrade head
```
