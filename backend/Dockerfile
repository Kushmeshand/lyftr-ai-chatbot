# Multi-stage Dockerfile for FastAPI Backend

# Stage 1: Build & Dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Minimal Runtime Image
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /install /usr/local

# Create data directory for SQLite persistent volume
RUN mkdir -p /data

# Copy application source code
COPY app/ /app/app/
COPY pytest.ini /app/
COPY tests/ /app/tests/

ENV PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/app.db \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    LITELLM_MODE=PRODUCTION \
    PORT=8000

EXPOSE 8000

CMD ["python", "-m", "app.run"]
