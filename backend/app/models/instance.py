"""
数据库实例与分组模型。
存储被监控的数据库连接配置。
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InstanceGroup(Base):
    """数据库实例分组（环境/业务线）。"""

    __tablename__ = "instance_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    group_type: Mapped[str] = mapped_column(String(32), default="environment")  # environment / business
    description: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    instances: Mapped[list["DatabaseInstance"]] = relationship(back_populates="group")


class DatabaseInstance(Base):
    """被监控的数据库实例配置。"""

    __tablename__ = "database_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    db_type: Mapped[str] = mapped_column(String(32), nullable=False)  # mysql/postgresql/redis/mongodb
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str] = mapped_column(String(128), default="")
    encrypted_password: Mapped[str] = mapped_column(Text, default="")
    database_name: Mapped[str] = mapped_column(String(128), default="")
    max_connections: Mapped[int] = mapped_column(Integer, default=100)
    # 0 = 跟随全局 COLLECTOR_INTERVAL_SECONDS
    collector_interval_seconds: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("instance_groups.id"), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    # 当前状态缓存：normal / warning / critical / offline
    status: Mapped[str] = mapped_column(String(32), default="offline")
    last_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    group: Mapped["InstanceGroup"] = relationship(back_populates="instances")
