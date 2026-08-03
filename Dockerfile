# ============================================================
# Stage 1: Build frontend
# ============================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ============================================================
# Stage 2: Backend + static files
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY rogers/ ./rogers/
COPY run.py build_web.py langgraph.json ./

COPY --from=frontend-builder /app/frontend/dist ./rogers/static/

ENV PYTHONPATH=/app/rogers \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "rogers"]
