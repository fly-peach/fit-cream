# ============================================================
# Stage 1: Build frontend
# ============================================================
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# 配置 pnpm 镜像源，加速依赖安装
RUN corepack enable && pnpm config set registry https://registry.npmmirror.com

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ============================================================
# Stage 2: Backend + static files
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# 配置国内 Debian 源，加速系统包安装
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# 直接用 pip 安装 uv，避免从 ghcr.io 拉取（国内镜像）
RUN pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple

# 配置 uv 使用国内 PyPI 源
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

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
