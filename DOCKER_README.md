# Docker Setup Guide

This guide explains how to run the Karofa application using Docker.

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)

## Quick Start

1. **Copy the environment file**
   ```bash
   cp .env.docker.example docker/.env
   ```

2. **Update the `.env` file** in the `docker/` directory with your actual API keys and configuration:
   - `POSTGRES_PASSWORD`: Set a secure PostgreSQL password
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `COHERE_API_KEY`: Your Cohere API key
   - Other configuration as needed

3. **Build and start the services**
   ```bash
   cd docker
   docker-compose up --build
   ```

   Or run in detached mode:
   ```bash
   docker-compose up -d --build
   ```

4. **Access the application**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - PostgreSQL: localhost:5432
   - MongoDB: localhost:27007

## Services

The docker-compose setup includes:

- **app**: FastAPI application (port 8000)
- **pgvector**: PostgreSQL with pgvector extension (port 5432)
- **mongodb**: MongoDB database (port 27007)

## Management Commands

### View logs
```bash
docker-compose logs -f app
```

### Stop services
```bash
docker-compose down
```

### Stop and remove volumes (⚠️ deletes all data)
```bash
docker-compose down -v
```

### Rebuild after code changes
```bash
docker-compose up --build
```

### Run database migrations manually
```bash
docker-compose exec app bash
cd models/db_schemes/firmy
alembic upgrade head
```

### Access PostgreSQL
```bash
docker-compose exec pgvector psql -U postgres -d minirag
```

### Access MongoDB
```bash
docker-compose exec mongodb mongosh -u admin -p your_mongo_password
```

## Development Mode

The docker-compose configuration mounts the `src/` directory as a volume, enabling hot-reload for development:
- Changes to Python files will automatically reload the server
- No need to rebuild the container for code changes

## Production Considerations

For production deployment, consider:

1. **Remove volume mounts** from docker-compose.yml (code is already in the image)
2. **Use production WSGI server** with more workers:
   ```dockerfile
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
   ```
3. **Set secure passwords** for all services
4. **Enable HTTPS** using a reverse proxy (nginx, traefik, etc.)
5. **Configure proper logging** and monitoring
6. **Use Docker secrets** for sensitive information

## Troubleshooting

### Database connection errors
- Ensure PostgreSQL is fully started (check health status)
- Verify `POSTGRES_HOST=pgvector` in your `.env` file
- Check network connectivity: `docker-compose exec app ping pgvector`

### Port conflicts
If ports 8000, 5432, or 27007 are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Use port 8001 on host instead
```

### Application fails to start
Check logs for detailed error messages:
```bash
docker-compose logs app
```

### Reset everything
```bash
docker-compose down -v
docker system prune -a
docker-compose up --build
```
