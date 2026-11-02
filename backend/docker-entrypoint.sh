#!/usr/bin/env sh
# 后端容器入口：等待数据库 → 执行 Alembic 迁移 → 可选管理员 seed → 启动 uvicorn。
set -eu

log() { printf '[entrypoint] %s\n' "$*"; }

# ---- 1. 等待数据库可用 ----
if [ "${WAIT_FOR_DB:-true}" = "true" ]; then
  log "等待数据库就绪..."
  attempt=1
  max_attempts="${DB_WAIT_ATTEMPTS:-60}"
  until python - <<'PY'
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def probe() -> None:
    engine = create_async_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
    finally:
        await engine.dispose()


asyncio.run(probe())
PY
  do
    if [ "$attempt" -ge "$max_attempts" ]; then
      log "数据库在 ${max_attempts} 次尝试后仍不可用，退出。"
      exit 1
    fi
    log "第 ${attempt} 次连接失败，2 秒后重试。"
    attempt=$((attempt + 1))
    sleep 2
  done
  log "数据库已就绪。"
fi

# ---- 2. 执行数据库迁移 ----
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  log "执行 alembic upgrade head..."
  alembic upgrade head
  log "迁移完成。"
fi

# ---- 3. 可选的幂等管理员 seed ----
if [ "${SEED_ADMIN:-true}" = "true" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
  log "执行管理员 seed..."
  python -m scripts.create_admin || log "管理员 seed 失败（不阻塞启动）。"
fi

# ---- 4. 启动应用 ----
if [ "$#" -eq 0 ]; then
  set -- uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
fi
# 第一个参数是 uvicorn 且未显式指定 worker 时，按 WEB_CONCURRENCY 展开。
if [ "$1" = "uvicorn" ] && ! printf '%s\n' "$@" | grep -qx -- '--workers'; then
  set -- "$@" --workers "${WEB_CONCURRENCY:-2}" --proxy-headers --forwarded-allow-ips='*'
fi

log "启动: $*"
exec "$@"
