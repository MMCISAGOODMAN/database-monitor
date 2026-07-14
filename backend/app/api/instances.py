"""
数据库实例管理 API。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_auth
from app.collectors import COLLECTOR_MAP
from app.database import get_db
from app.models.alert import Alert, AlertRule
from app.models.instance import DatabaseInstance, InstanceGroup
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.instance import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    DatabaseInstanceCreate,
    DatabaseInstanceResponse,
    DatabaseInstanceUpdate,
    InstanceGroupCreate,
    InstanceGroupResponse,
)
from app.services.advisor_service import advisor_service
from app.services.collector_service import collector_service
from app.utils.encryption import decrypt_password, encrypt_password

router = APIRouter(prefix="/instances", tags=["数据库实例"])


@router.get("/groups", response_model=ResponseModel[list[InstanceGroupResponse]])
async def list_groups(db: AsyncSession = Depends(get_db), _user: User = Depends(require_auth)):
    """获取所有实例分组。"""
    result = await db.execute(select(InstanceGroup))
    groups = result.scalars().all()
    return ResponseModel(data=[InstanceGroupResponse.model_validate(g) for g in groups])


@router.post("/groups", response_model=ResponseModel[InstanceGroupResponse])
async def create_group(
    data: InstanceGroupCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """创建实例分组。"""
    group = InstanceGroup(**data.model_dump())
    db.add(group)
    await db.flush()
    return ResponseModel(data=InstanceGroupResponse.model_validate(group))


@router.get("", response_model=ResponseModel[list[DatabaseInstanceResponse]])
async def list_instances(db: AsyncSession = Depends(get_db), _user: User = Depends(require_auth)):
    """获取所有数据库实例。"""
    result = await db.execute(select(DatabaseInstance))
    instances = result.scalars().all()
    items = []
    for inst in instances:
        resp = DatabaseInstanceResponse.model_validate(inst)
        cached = collector_service.latest_metrics.get(inst.id, {})
        metrics = cached.get("metrics", {})
        resp.connections = metrics.get("connections")
        resp.qps = metrics.get("qps")
        resp.cpu_usage = metrics.get("cpu_usage")
        items.append(resp)
    return ResponseModel(data=items)


@router.post("", response_model=ResponseModel[DatabaseInstanceResponse])
async def create_instance(
    data: DatabaseInstanceCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """创建数据库实例。"""
    instance = DatabaseInstance(
        name=data.name,
        db_type=data.db_type,
        host=data.host,
        port=data.port,
        username=data.username,
        encrypted_password=encrypt_password(data.password),
        database_name=data.database_name,
        max_connections=data.max_connections,
        group_id=data.group_id,
        description=data.description,
    )
    db.add(instance)
    await db.flush()
    return ResponseModel(data=DatabaseInstanceResponse.model_validate(instance))


@router.get("/{instance_id}", response_model=ResponseModel[DatabaseInstanceResponse])
async def get_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取单个实例详情。"""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="实例不存在")
    resp = DatabaseInstanceResponse.model_validate(instance)
    cached = collector_service.latest_metrics.get(instance.id, {})
    metrics = cached.get("metrics", {})
    resp.connections = metrics.get("connections")
    resp.qps = metrics.get("qps")
    resp.cpu_usage = metrics.get("cpu_usage")
    return ResponseModel(data=resp)


@router.put("/{instance_id}", response_model=ResponseModel[DatabaseInstanceResponse])
async def update_instance(
    instance_id: int,
    data: DatabaseInstanceUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """更新数据库实例。"""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="实例不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        instance.encrypted_password = encrypt_password(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(instance, key, value)

    await db.flush()
    return ResponseModel(data=DatabaseInstanceResponse.model_validate(instance))


@router.delete("/{instance_id}", response_model=ResponseModel)
async def delete_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """删除数据库实例（先清理关联告警/规则，避免外键阻塞）。"""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="实例不存在")

    # alerts.rule_id / alerts.instance_id 均有外键，必须先删告警事件
    await db.execute(delete(Alert).where(Alert.instance_id == instance_id))
    await db.execute(delete(AlertRule).where(AlertRule.instance_id == instance_id))
    await db.delete(instance)

    collector_service.latest_metrics.pop(instance_id, None)
    collector_service._counter_snapshots.pop(instance_id, None)
    from app.services.alert_service import alert_service

    alert_service._trigger_tracker = {
        k: v for k, v in alert_service._trigger_tracker.items() if k[0] != instance_id
    }
    alert_service._alert_aggregate = {
        k: v for k, v in alert_service._alert_aggregate.items() if k[0] != instance_id
    }

    return ResponseModel(message="删除成功")


@router.get("/{instance_id}/slow-queries", response_model=ResponseModel[list])
async def get_slow_queries(
    instance_id: int,
    _user: User = Depends(require_auth),
):
    """获取实例最近慢查询记录。"""
    cached = collector_service.latest_metrics.get(instance_id, {})
    return ResponseModel(data=cached.get("slow_queries", []))


@router.get("/{instance_id}/snapshot", response_model=ResponseModel[dict])
async def get_instance_snapshot(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """获取实例完整监控快照（指标 + 参数 + 建议）。"""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="实例不存在")

    cached = collector_service.latest_metrics.get(instance_id, {})
    metrics = cached.get("metrics", {})
    slow_queries = cached.get("slow_queries", [])

    suggestions = advisor_service.analyze(
        instance.db_type,
        metrics,
        max_connections=instance.max_connections,
        slow_queries=slow_queries,
    )

    return ResponseModel(data={
        "instance": DatabaseInstanceResponse.model_validate(instance),
        "metrics": metrics,
        "slow_queries": slow_queries,
        "collected_at": cached.get("collected_at"),
        "status": cached.get("status", instance.status),
        "suggestions": suggestions,
        "params": {
            "max_connections": instance.max_connections,
            "db_type": instance.db_type,
            "host": instance.host,
            "port": instance.port,
        },
    })


@router.post("/test-connection", response_model=ResponseModel[ConnectionTestResponse])
async def test_connection(
    data: ConnectionTestRequest,
    _user: User = Depends(require_auth),
):
    """测试数据库连接。"""
    collector_cls = COLLECTOR_MAP.get(data.db_type)
    if not collector_cls:
        return ResponseModel(data=ConnectionTestResponse(
            success=False, message=f"不支持的数据库类型: {data.db_type}"
        ))

    collector = collector_cls(
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        database_name=data.database_name,
    )
    success, message, latency = await collector.test_connection()
    return ResponseModel(data=ConnectionTestResponse(
        success=success, message=message, latency_ms=latency
    ))
