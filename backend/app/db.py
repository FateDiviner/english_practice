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
    return create_engine(url, **kwargs)


engine = _build_engine(settings.database_url)

if not settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_mysql_charset(dbapi_connection, _record) -> None:  # pragma: no cover - 驱动回调
        """确保 MySQL 连接使用 utf8mb4，正确存储音标与中文释义。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.close()

else:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:  # pragma: no cover
        """SQLite 默认不强制外键，ON DELETE CASCADE / SET NULL 会静默失效。

        MySQL 一直强制执行，两边行为必须一致，否则测试通过的行为在线上并不存在。
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
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


def init_db() -> None:
    """创建全部表结构（幂等）。"""
    from app import models  # noqa: F401  确保模型完成注册

    Base.metadata.create_all(bind=engine)
