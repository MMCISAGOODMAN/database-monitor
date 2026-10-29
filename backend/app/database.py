"""
数据库连接与会话管理。
使用 SQLAlchemy 异步引擎。
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """ORM 基类。"""

    pass


settings = get_settings()

# 确保 SQLite 数据目录存在
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("///")[-1]
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化数据库表结构，并补齐增量列。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_v21_columns)


def _ensure_v21_columns(sync_conn) -> None:
    """为已有库补齐 v2.1 新增列（幂等）。"""
    dialect = sync_conn.dialect.name
    statements = []
    if dialect == "sqlite":
        statements = [
            "ALTER TABLE database_instances ADD COLUMN collector_interval_seconds INTEGER DEFAULT 0",
            "ALTER TABLE alert_rules ADD COLUMN silenced_until DATETIME",
        ]
    else:
        statements = [
            "ALTER TABLE database_instances ADD COLUMN IF NOT EXISTS collector_interval_seconds INTEGER DEFAULT 0",
            "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS silenced_until TIMESTAMPTZ",
        ]
    for sql in statements:
        try:
            sync_conn.exec_driver_sql(sql)
        except Exception:
            # 列已存在或其他可忽略错误
            pass
