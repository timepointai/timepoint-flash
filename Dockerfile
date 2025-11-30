# TIMEPOINT Flash v2.0 Dockerfile
# Multi-stage build for optimized production image

# ============================================================================
# Stage 1: Builder
# ============================================================================
FROM python:3.10-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /app/wheels -e .

# ============================================================================
# Stage 2: Production
# ============================================================================
FROM python:3.10-slim as production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY app/ ./app/

# Copy Alembic migrations
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Copy startup script
COPY scripts/start.sh ./

# Set ownership to non-root user
RUN chown -R appuser:appuser /app && chmod +x /app/start.sh

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run with startup script (migrations + uvicorn)
CMD ["./start.sh"]

# ============================================================================
# Stage 3: Development (optional)
# ============================================================================
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-asyncio httpx

# Copy tests
COPY tests/ ./tests/
COPY pyproject.toml ./

RUN chown -R appuser:appuser /app

USER appuser

# Override CMD for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
