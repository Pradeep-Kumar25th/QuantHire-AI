# Multi-stage Dockerfile for Celery Worker

# Stage 1: Base
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY apps/worker/requirements.txt .
COPY apps/api/requirements.txt ./api-requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r api-requirements.txt

# Stage 2: Development
FROM base as development

# Copy application code
COPY apps/worker /app
COPY apps/agents /agents
COPY apps/api /api

# Run Celery worker
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

# Stage 3: Production
FROM base as production

# Copy application code
COPY apps/worker /app
COPY apps/agents /agents
COPY apps/api /api

# Create non-root user
RUN useradd -m -u 1000 celeryuser && chown -R celeryuser:celeryuser /app
USER celeryuser

# Run Celery worker with optimized settings
CMD ["celery", "-A", "worker.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "--max-tasks-per-child=1000", \
     "--time-limit=3600"]

