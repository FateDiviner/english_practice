# syntax=docker/dockerfile:1
# 后端镜像：Python 3.11 + uv 依赖锁定安装 + Alembic 迁移入口脚本。
# 构建上下文必须是 backend/ 目录（docker compose 已按此配置）。

# ---------- 阶段 1：依赖安装 ----------
FROM python:3.11-slim AS deps

# uv 只负责依赖安装；镜像内固定 Python 3.11，禁止另下载解释器。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=3.11 \
    TZ=Asia/Shanghai

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# 只复制依赖描述文件，先装依赖，最大化利用层缓存。
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH \
    TZ=Asia/Shanghai \
    PORT=8000 \
    WEB_CONCURRENCY=2 \
    RUN_MIGRATIONS=true \
    SEED_ADMIN=true

WORKDIR /app

# 运行期只依赖 curl 用于容器内排错；tzdata 供 ZoneInfo 读取 APP_TIMEZONE。
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl tzdata; \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime; \
    echo "$TZ" > /etc/timezone; \
    rm -rf /var/lib/apt/lists/*

# 复制依赖阶段产出的虚拟环境。
COPY --from=deps /app/.venv /app/.venv

# 应用代码与迁移脚本。
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# 统一使用 LF 并赋予执行权限（防止 Windows 检出带入 CRLF）。
RUN set -eux; \
    sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh; \
    chmod +x /usr/local/bin/docker-entrypoint.sh; \
    mkdir -p /app/var/tts; \
    groupadd --system --gid 10001 app; \
    useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app; \
    chown -R app:app /app/var

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
