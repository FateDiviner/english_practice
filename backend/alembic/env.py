import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.db.base import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic 通过 Settings 读取 .env / 环境变量，不在 alembic.ini 中保存数据库凭据。
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# 本期 Base 为空；后续 models 导入后，autogenerate 即可读取完整 metadata。
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以离线模式生成迁移 SQL，不创建数据库连接。"""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在 async 连接上执行同步迁移上下文。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """使用 asyncmy 引擎建立连接并执行迁移。"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """启动异步迁移流程。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
