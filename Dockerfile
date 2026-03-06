# Multi-stage Dockerfile for production-ready FastAPI app

# Stage 1: Build stage
FROM python:3.9-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Ensure script installs (e.g. uvicorn, alembic) are on PATH to avoid pip warnings
ENV PATH=/root/.local/bin:$PATH

# Install Python dependencies (cache mount speeds up rebuilds when deps change)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime stage (default for api service; test stage is last so we set target in compose)
FROM python:3.9-slim as runtime

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder to appuser's home
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY . .

# Set ownership
RUN chown -R appuser:appuser /app /home/appuser/.local

# Switch to non-root user
USER appuser

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Health check (stdlib only; requests is not in requirements)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# Migrations run once per deploy via CI/CD (one-off ECS task), not at container startup
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 2b: Migration-only image (no docling/opencv/torch); for ECS one-off migration tasks
FROM python:3.9-slim as migration

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY requirements-migration.txt .
ENV PATH=/root/.local/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user -r requirements-migration.txt

RUN cp -r /root/.local /home/appuser/.local && chown -R appuser:appuser /home/appuser/.local

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH

# Default command; ECS run-task overrides to: python -m alembic upgrade head
CMD ["python", "-m", "alembic", "upgrade", "head"]

# Stage 3: Test (CI lint + migrate + pytest inside compose)
# Reuse builder so we only add dev deps; avoids re-downloading torch/docling (~5+ min saved).
FROM builder as test

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt .
ENV PATH=/root/.local/bin:$PATH
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --user -r requirements-dev.txt

COPY . .

# Default: run lint, migrations, then pytest (overridable for quick pytest-only)
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics && flake8 app --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics && alembic upgrade head && pytest tests/ -v --tb=short -n auto --cov=app --cov-report=term"]
