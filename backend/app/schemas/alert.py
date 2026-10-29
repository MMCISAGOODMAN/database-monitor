"""
告警相关模式。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertRuleCreate(BaseModel):
    """创建告警规则。"""

    name: str
    instance_id: Optional[int] = None
    metric_name: str
    operator: str = ">"
    threshold: float
    duration_seconds: int = 300
    severity: str = "warning"
    expression: str = ""
    is_enabled: bool = True


class AlertRuleResponse(BaseModel):
    """告警规则响应。"""

    id: int
    name: str
    instance_id: Optional[int]
    metric_name: str
    operator: str
    threshold: float
    duration_seconds: int
    severity: str
    is_builtin: bool
    is_enabled: bool
    expression: str
    silenced_until: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertSilenceRequest(BaseModel):
    """告警规则静默请求。"""

    hours: float = Field(1.0, ge=0, le=168, description="静默小时数，0 表示清除静默")


class AlertResponse(BaseModel):
    """告警事件响应。"""

    id: int
    instance_id: Optional[int]
    instance_name: str
    rule_id: Optional[int]
    severity: str
    title: str
    message: str
    metric_name: str
    metric_value: float
    is_acknowledged: bool
    acknowledged_by: str
    acknowledged_at: Optional[datetime]
    root_cause: str
    suggestion: str
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationChannelCreate(BaseModel):
    """创建通知渠道。"""

    name: str
    channel_type: str = Field(..., pattern="^(wechat|dingtalk|feishu|email)$")
    webhook_url: str = ""
    email_recipients: str = ""
    is_enabled: bool = True


class NotificationChannelResponse(BaseModel):
    """通知渠道响应。"""

    id: int
    name: str
    channel_type: str
    webhook_url: str
    email_recipients: str
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}
