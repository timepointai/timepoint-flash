# TIMEPOINT Flash Deployment Guide

This guide covers deploying TIMEPOINT Flash to production environments.

---

## Quick Deploy Options

### Railway (Recommended)

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

1. Click "Deploy on Railway"
2. Connect your GitHub repository
3. Add environment variables in Railway dashboard:
   - `GOOGLE_API_KEY` or `OPENROUTER_API_KEY`
   - `DATABASE_URL` (auto-configured with PostgreSQL add-on)
4. Deploy

Railway auto-detects the `railway.json` configuration.

### Render

1. Create a new Web Service on [render.com](https://render.com)
2. Connect your repository
3. Render auto-detects the `render.yaml` Blueprint
4. Add secret environment variables:
   - `GOOGLE_API_KEY`
   - `OPENROUTER_API_KEY` (optional)
5. Deploy

The Blueprint creates both the web service and PostgreSQL database.

---

## Docker Deployment

### Production with Docker Compose

```bash
# Clone repository
git clone https://github.com/realityinspector/timepoint-flash.git
cd timepoint-flash

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f app
```

This starts:
- **app**: FastAPI application on port 8000
- **db**: PostgreSQL 15 on port 5432 (internal)

### Build Image Only

```bash
# Build production image
docker build -t timepoint-flash:latest .

# Run with external database
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/timepoint" \
  -e GOOGLE_API_KEY="your-key" \
  timepoint-flash:latest
```

### Development Mode

```bash
# Use development compose file
docker compose -f docker-compose.dev.yml up

# This enables:
# - Hot reload
# - Mounted source code
# - Test dependencies
```

---

## Database Setup

### Automatic Migrations

The Docker image runs Alembic migrations on startup via `scripts/start.sh`.

### Manual Migrations

```bash
# Check current revision
alembic current

# Apply all pending migrations
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Generate new migration (after model changes)
alembic revision --autogenerate -m "description"
```

### PostgreSQL Connection

```bash
# Standard PostgreSQL URL format
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database

# Render provides postgres:// URLs which are auto-converted
# in alembic/env.py
```

### SQLite (Development Only)

```bash
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db
```

---

## Environment Variables

### Required (at least one)

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Google AI API key for Gemini models |
| `OPENROUTER_API_KEY` | OpenRouter API key for multi-model access |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./timepoint.db` | Database connection string |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment: development, staging, production |
| `DEBUG` | `true` | Enable debug mode |
| `PORT` | `8000` | Server port |
| `RATE_LIMIT` | `60` | API rate limit (requests/minute) |

### Models

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMARY_PROVIDER` | `google` | Primary LLM provider |
| `FALLBACK_PROVIDER` | `openrouter` | Fallback provider |
| `JUDGE_MODEL` | `gemini-2.5-flash` | Fast validation model |
| `CREATIVE_MODEL` | `gemini-2.5-flash` | Creative generation model |
| `IMAGE_MODEL` | `gemini-2.5-flash-image` | Image generation model (Google native)

### Observability

| Variable | Description |
|----------|-------------|
| `LOGFIRE_TOKEN` | Logfire monitoring token (optional) |

---

## Health Checks

### Endpoints

```bash
# Basic health
curl http://localhost:8000/health

# API health (with database check)
curl http://localhost:8000/api/v1/health
```

### Response Format

```json
{
  "status": "healthy",
  "version": "2.2.1",
  "environment": "production"
}
```

### Docker Health Check

The Dockerfile includes a built-in health check:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1
```

---

## Production Checklist

### Security

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Use PostgreSQL (not SQLite)
- [ ] Configure CORS origins if needed
- [ ] Use HTTPS in production
- [ ] Rotate API keys regularly

### Performance

- [ ] Enable connection pooling (default with asyncpg)
- [ ] Configure appropriate `RATE_LIMIT`
- [ ] Set up log aggregation
- [ ] Monitor response times

### Reliability

- [ ] Configure health checks
- [ ] Set up error alerting
- [ ] Enable database backups
- [ ] Test failover with fallback provider

---

## Kubernetes Deployment

### Example Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: timepoint-flash
spec:
  replicas: 2
  selector:
    matchLabels:
      app: timepoint-flash
  template:
    metadata:
      labels:
        app: timepoint-flash
    spec:
      containers:
      - name: app
        image: timepoint-flash:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: timepoint-secrets
              key: database-url
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: timepoint-secrets
              key: google-api-key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
```

### Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: timepoint-flash
spec:
  selector:
    app: timepoint-flash
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Troubleshooting

### Common Issues

**Database connection failed**
```
Check DATABASE_URL format
Ensure database is accessible
Verify credentials
```

**Migrations failed**
```bash
# Check current state
alembic current

# Stamp to current if needed
alembic stamp head
```

**API key errors**
```
Verify GOOGLE_API_KEY or OPENROUTER_API_KEY is set
Check key permissions and quotas
```

### Logs

```bash
# Docker logs
docker compose logs -f app

# Kubernetes logs
kubectl logs -f deployment/timepoint-flash
```

---

## Support

- Issues: https://github.com/realityinspector/timepoint-flash/issues
- Documentation: https://github.com/realityinspector/timepoint-flash/tree/main/docs
