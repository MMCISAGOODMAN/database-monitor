"""
数据库实例相关模式。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class InstanceGroupCreate(BaseModel):
    """创建分组请求。"""

    name: str = Field(..., min_length=1, max_length=64)
    group_type: str = "environment"
    description: str = ""


class InstanceGroupResponse(BaseModel):
    """分组响应。"""

    id: int
    name: str
    group_type: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DatabaseInstanceCreate(BaseModel):
    """创建数据库实例请求。"""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(..., min_length=1, max_length=128)
    db_type: str = Field(..., pattern="^(mysql|postgresql|redis|mongodb)$")
    host: str
    port: int = Field(..., ge=1, le=65535)
    username: str = ""
    password: str = ""
    database_name: str = ""
    max_connections: int = 100
    collector_interval_seconds: int = Field(0, ge=0, le=3600)
    group_id: Optional[int] = None
    description: str = ""


class DatabaseInstanceUpdate(BaseModel):
    """更新数据库实例请求。"""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database_name: Optional[str] = None
    max_connections: Optional[int] = None
    collector_interval_seconds: Optional[int] = Field(None, ge=0, le=3600)
    group_id: Optional[int] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None


class DatabaseInstanceResponse(BaseModel):
    """数据库实例响应（不含密码）。"""

    id: int
    name: str
    db_type: str
    host: str
    port: int
    username: str
    database_name: str
    max_connections: int
    collector_interval_seconds: int = 0
    group_id: Optional[int]
    is_enabled: bool
    status: str
    description: str
    last_collected_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    # 实时指标预览
    connections: Optional[float] = None
    qps: Optional[float] = None
    cpu_usage: Optional[float] = None

    model_config = {"from_attributes": True}


class ConnectionTestRequest(BaseModel):
    """连接测试请求。"""

    db_type: str
    host: str
    port: int
    username: str = ""
    password: str = ""
    database_name: str = ""


class ConnectionTestResponse(BaseModel):
    """连接测试响应。"""

    success: bool
    message: str
    latency_ms: Optional[float] = None
