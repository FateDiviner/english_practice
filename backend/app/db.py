"""数据库连接与会话管理（SQLAlchemy 2.0，参数化查询防注入）。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


def _build_engine(url: str) -> Engine:
    """按数据库类型创建引擎，MySQL 需开启重连与 utf8mb4。"""
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_recycle"] = 3600
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(target: Engine) -> None:
    """SQLite 默认不强制外键，必须显式打开。

    MySQL 的 InnoDB 默认强制，若测试环境不开，ON DELETE CASCADE / SET NULL
    在测试里形同虚设，级联清理与审计外键置空都验不到真实行为。
    """

    @event.listens_for(target, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record) -> None:  # pragma: no cover - 驱动回调
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = _build_engine(settings.database_url)

if not settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_mysql_charset(dbapi_connection, _record) -> None:  # pragma: no cover - 驱动回调
        """确保 MySQL 连接使用 utf8mb4，正确存储音标与中文释义。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话，异常时自动回滚。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# 既有表里必须存在但可能缺失的列：create_all 只建新表、不给老表加列，
# 本项目刻意不用 Alembic，因此新增字段一律在这里幂等补齐。
# DDL 写成方言无关的通用类型，SQLite 与 MySQL 都能吃下。
REQUIRED_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "role": "VARCHAR(16) DEFAULT 'user' NOT NULL",
        "status": "VARCHAR(16) DEFAULT 'active' NOT NULL",
    },
    "wordbooks": {"status": "VARCHAR(16) DEFAULT 'active' NOT NULL"},
    "words": {"status": "VARCHAR(16) DEFAULT 'active' NOT NULL"},
    "chat_messages": {"metadata": "TEXT NULL"},
}


def _ensure_columns(target: Engine | None = None) -> int:
    """给已存在的表补齐缺失列与索引，返回实际执行的 DDL 语句数。

    索引也要补：ORM 里声明了 index=True，但 create_all 不会给已有表补索引，
    只补列会让模型与实际表结构长期不一致。

    target 仅用于测试：传入一个临时引擎即可验证「旧版表结构被补齐」这条路径。
    """
    from sqlalchemy import inspect, text

    target = target or engine
    inspector = inspect(target)
    tables = set(inspector.get_table_names())
    applied = 0
    with target.begin() as conn:
        for table, columns in REQUIRED_COLUMNS.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    applied += 1
                # 列名与 SQLAlchemy 默认命名约定一致：ix_{表名}_{列名}
                index_name = f"ix_{table}_{name}"
                if index_name not in {index["name"] for index in inspector.get_indexes(table)}:
                    conn.execute(
                        text(f"CREATE INDEX {index_name} ON {table} ({name})")
                    )
                    applied += 1
    return applied


def init_db() -> None:
    """创建全部表结构并补齐缺失列（幂等）。"""
    from app import models  # noqa: F401  确保模型完成注册

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
