"""
告警管理 API。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth
from app.database import get_db
from app.models.alert import Alert, AlertRule, NotificationChannel
from app.models.user import User
from app.schemas.alert import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertSilenceRequest,
    NotificationChannelCreate,
    NotificationChannelResponse,
)
from app.schemas.common import ResponseModel
from app.services.alert_service import alert_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/alerts", tags=["告警管理"])


@router.get("", response_model=ResponseModel[List[AlertResponse]])
async def list_alerts(
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取告警列表。"""
    query = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if severity:
        query = query.where(Alert.severity == severity)
    if acknowledged is not None:
        query = query.where(Alert.is_acknowledged == acknowledged)

    result = await db.execute(query)
    alerts = result.scalars().all()
    return ResponseModel(data=[AlertResponse.model_validate(a) for a in alerts])


@router.post("/{alert_id}/acknowledge", response_model=ResponseModel)
async def acknowledge_alert(
    alert_id: int,
    user: User = Depends(require_auth),
):
    """确认告警。"""
    success = await alert_service.acknowledge_alert(alert_id, user.username)
    if not success:
        return ResponseModel(code=404, message="告警不存在")
    return ResponseModel(message="告警已确认")


@router.get("/rules", response_model=ResponseModel[List[AlertRuleResponse]])
async def list_rules(db: AsyncSession = Depends(get_db), _user: User = Depends(require_auth)):
    """获取告警规则列表。"""
    result = await db.execute(select(AlertRule))
    rules = result.scalars().all()
    return ResponseModel(data=[AlertRuleResponse.model_validate(r) for r in rules])


@router.post("/rules", response_model=ResponseModel[AlertRuleResponse])
async def create_rule(
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """创建自定义告警规则。"""
    rule = AlertRule(**data.model_dump())
    db.add(rule)
    await db.flush()
    await audit_service.log(
        db, user=_admin, action="create", resource=f"rule:{rule.id}",
        detail=f"创建告警规则 {rule.name}",
    )
    return ResponseModel(data=AlertRuleResponse.model_validate(rule))


@router.get("/channels", response_model=ResponseModel[List[NotificationChannelResponse]])
async def list_channels(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """获取通知渠道列表。"""
    result = await db.execute(select(NotificationChannel))
    channels = result.scalars().all()
    return ResponseModel(data=[NotificationChannelResponse.model_validate(c) for c in channels])


@router.post("/channels", response_model=ResponseModel[NotificationChannelResponse])
async def create_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """创建通知渠道。"""
    channel = NotificationChannel(**data.model_dump())
    db.add(channel)
    await db.flush()
    await audit_service.log(
        db, user=_admin, action="create", resource=f"channel:{channel.id}",
        detail=f"创建通知渠道 {channel.name}",
    )
    return ResponseModel(data=NotificationChannelResponse.model_validate(channel))


@router.put("/rules/{rule_id}", response_model=ResponseModel[AlertRuleResponse])
async def update_rule(
    rule_id: int,
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """更新告警规则。"""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if rule.is_builtin:
        raise HTTPException(status_code=400, detail="内置规则不可修改")
    for k, v in data.model_dump().items():
        setattr(rule, k, v)
    await db.flush()
    await audit_service.log(
        db, user=_admin, action="update", resource=f"rule:{rule.id}",
        detail=f"更新告警规则 {rule.name}",
    )
    return ResponseModel(data=AlertRuleResponse.model_validate(rule))


@router.post("/rules/{rule_id}/silence", response_model=ResponseModel[AlertRuleResponse])
async def silence_rule(
    rule_id: int,
    data: AlertSilenceRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """静默告警规则（hours=0 清除静默）。"""
    from datetime import datetime, timedelta, timezone

    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    if data.hours <= 0:
        rule.silenced_until = None
        detail = f"清除规则静默 {rule.name}"
    else:
        rule.silenced_until = datetime.now(timezone.utc) + timedelta(hours=data.hours)
        detail = f"静默规则 {rule.name} {data.hours}h"

    await db.flush()
    await audit_service.log(
        db, user=_admin, action="silence", resource=f"rule:{rule.id}", detail=detail,
    )
    return ResponseModel(data=AlertRuleResponse.model_validate(rule), message=detail)


@router.delete("/rules/{rule_id}", response_model=ResponseModel)
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除告警规则。"""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if rule.is_builtin:
        raise HTTPException(status_code=400, detail="内置规则不可删除")
    name = rule.name
    await db.delete(rule)
    await audit_service.log(
        db, user=_admin, action="delete", resource=f"rule:{rule_id}",
        detail=f"删除告警规则 {name}",
    )
    return ResponseModel(message="删除成功")


@router.patch("/rules/{rule_id}/toggle", response_model=ResponseModel[AlertRuleResponse])
async def toggle_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """启用/禁用告警规则。"""
    result = await db.execute(select(AlertRule).where(AlertRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.is_enabled = not rule.is_enabled
    await db.flush()
    return ResponseModel(data=AlertRuleResponse.model_validate(rule))


@router.delete("/channels/{channel_id}", response_model=ResponseModel)
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除通知渠道。"""
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    name = channel.name
    await db.delete(channel)
    await audit_service.log(
        db, user=_admin, action="delete", resource=f"channel:{channel_id}",
        detail=f"删除通知渠道 {name}",
    )
    return ResponseModel(message="删除成功")


@router.patch("/channels/{channel_id}/toggle", response_model=ResponseModel[NotificationChannelResponse])
async def toggle_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """启用/禁用通知渠道。"""
    result = await db.execute(
        select(NotificationChannel).where(NotificationChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    channel.is_enabled = not channel.is_enabled
    await db.flush()
    return ResponseModel(data=NotificationChannelResponse.model_validate(channel))
