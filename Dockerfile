# ============================================================
# Runtime: backend + 前端静态产物
# 前端 dist 由部署脚本本地构建后上传到服务器构建上下文 rogers/static/，
# 镜像不在服务器上构建前端（无 Node/pnpm 依赖）。exercises 为绑定挂载，
# 由 .dockerignore 排除不进镜像。
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

# 复制后端代码 + 前端 dist（rogers/static/assets 等，由部署脚本上传到构建上下文）
COPY rogers/ ./rogers/
COPY run.py build_web.py langgraph.json ./

ENV PYTHONPATH=/app/rogers \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "rogers"]
