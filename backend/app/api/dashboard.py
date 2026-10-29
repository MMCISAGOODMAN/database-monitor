"""
大屏数据 API。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_auth
from app.database import get_db
from app.models.instance import DatabaseInstance
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.metrics import DashboardKPI, MetricSeries, TreemapItem
from app.services.analytics_service import analytics_service
from app.services.collector_service import collector_service
from app.services.dashboard_service import dashboard_service
from app.services.influxdb_service import influxdb_service

router = APIRouter(prefix="/dashboard", tags=["大屏数据"])


@router.get("/kpi", response_model=ResponseModel[DashboardKPI])
async def get_kpi(_user: User = Depends(require_auth)):
    """获取顶部 KPI 卡片数据。"""
    kpi = await dashboard_service.get_kpi()
    return ResponseModel(data=kpi)


@router.get("/instances", response_model=ResponseModel[list])
async def get_instance_list(
    status: Optional[str] = Query(None, description="状态筛选: all/normal/warning/critical/offline"),
    group_id: Optional[int] = Query(None),
    _user: User = Depends(require_auth),
):
    """获取实例列表（含实时指标）。"""
    items = await dashboard_service.get_instance_list(status, group_id)
    return ResponseModel(data=items)


@router.get("/treemap", response_model=ResponseModel[List[TreemapItem]])
async def get_treemap(_user: User = Depends(require_auth)):
    """获取底部热力图数据。"""
    items = await dashboard_service.get_treemap_data()
    return ResponseModel(data=items)


@router.get("/metrics/{instance_id}", response_model=ResponseModel[List[MetricSeries]])
async def get_metrics(
    instance_id: int,
    metrics: str = Query("qps,connections,slow_queries,cpu_usage"),
    range: str = Query("-15m", description="时间范围: -15m/-1h/-6h/-24h"),
    _user: User = Depends(require_auth),
):
    """获取实例指标趋势数据。"""
    metric_names = [m.strip() for m in metrics.split(",")]
    series = influxdb_service.query_metrics(instance_id, metric_names, start=range)
    return ResponseModel(data=series)


@router.get("/alert-stats", response_model=ResponseModel[dict])
async def get_alert_stats(
    days: int = Query(7, ge=1, le=30),
    _user: User = Depends(require_auth),
):
    """获取告警统计数据（按天/级别）。"""
    stats = await analytics_service.get_alert_stats(days)
    return ResponseModel(data=stats)


@router.get("/compare", response_model=ResponseModel[list])
async def compare_instances(
    ids: str = Query(..., description="逗号分隔的实例 ID，2～3 个"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_auth),
):
    """实例对比：返回各实例最新 KPI 快照。"""
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids 格式无效")
    if len(id_list) < 2 or len(id_list) > 3:
        raise HTTPException(status_code=400, detail="请选择 2～3 个实例进行对比")

    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id.in_(id_list))
    )
    instances = {i.id: i for i in result.scalars().all()}

    items = []
    for iid in id_list:
        inst = instances.get(iid)
        if not inst:
            continue
        cached = collector_service.latest_metrics.get(iid, {})
        metrics = cached.get("metrics", {})
        items.append({
            "id": inst.id,
            "name": inst.name,
            "db_type": inst.db_type,
            "status": cached.get("status", inst.status),
            "collected_at": cached.get("collected_at"),
            "metrics": {
                "qps": metrics.get("qps"),
                "connections": metrics.get("connections"),
                "cpu_usage": metrics.get("cpu_usage"),
                "slow_queries": metrics.get("slow_queries"),
                "hit_rate": metrics.get("hit_rate") or metrics.get("cache_hit_rate")
                    or metrics.get("innodb_buffer_hit_rate"),
                "memory_usage": metrics.get("memory_usage"),
            },
        })
    return ResponseModel(data=items)


@router.get("/history/{instance_id}", response_model=ResponseModel[dict])
async def get_history_snapshot(
    instance_id: int,
    at: str = Query(..., description="ISO 时间，如 2026-06-12T10:00:00"),
    _user: User = Depends(require_auth),
):
    """历史回放：获取指定时间点前后的指标快照。"""
    from datetime import datetime, timedelta

    try:
        target = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="无效的时间格式")

    start = (target - timedelta(minutes=15)).isoformat()
    stop = (target + timedelta(minutes=15)).isoformat()
    metric_names = ["qps", "connections", "cpu_usage", "slow_queries"]
    series = influxdb_service.query_metrics(instance_id, metric_names, start=start, stop=stop)
    return ResponseModel(data={
        "instance_id": instance_id,
        "target_time": at,
        "series": [s.model_dump() for s in series],
    })
