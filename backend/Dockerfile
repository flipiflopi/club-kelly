FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency specs first (cache layer)
COPY pyproject.toml .
RUN uv pip install --system --no-cache -e .

# Copy source code
COPY backend/ backend/
COPY engine/ engine/
COPY adapters/ adapters/
COPY competitions/ competitions/

# Copy alembic config + migrations
COPY alembic.ini .
COPY migrations/ migrations/

# Entrypoint: runs migrations then starts the app
COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
