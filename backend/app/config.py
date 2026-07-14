"""
应用配置模块。
从环境变量读取配置，支持 Docker 部署。
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 应用基础配置
    app_name: str = "数据库监控大屏系统"
    app_version: str = "2.0.0"
    debug: bool = False

    # 关系数据库（配置存储）
    database_url: str = "sqlite+aiosqlite:///./data/monitor.db"

    # InfluxDB 时序数据库
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "db-monitor-token"
    influxdb_org: str = "db-monitor"
    influxdb_bucket: str = "metrics"

    # Redis 缓存（可选）
    redis_url: Optional[str] = "redis://localhost:6379/0"

    # 安全相关
    secret_key: str = "change-this-secret-key-in-production"
    encryption_key: str = "change-this-32-byte-encryption-key!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # 默认管理员账号
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"

    # 采集器配置
    collector_interval_seconds: int = 30
    collector_max_retries: int = 3
    collector_retry_delay_seconds: int = 5

    # 告警聚合窗口（秒）
    alert_aggregate_window_seconds: int = 600

    # Prometheus 集成（可选）
    prometheus_url: Optional[str] = None

    # 邮件通知
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    """获取缓存的配置单例。"""
    return Settings()
