"""
系统运维 API：采集日志、健康检查详情。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin, require_auth
from app.config import get_settings
from app.models.user import User
from app.schemas.common import ResponseModel
from app.services.collector_service import collector_service
from app.services.influxdb_service import influxdb_service

router = APIRouter(prefix="/system", tags=["系统运维"])


@router.get("/collection-logs", response_model=ResponseModel[List[dict]])
async def get_collection_logs(
    limit: int = Query(100, le=500),
    instance_id: Optional[int] = Query(None),
    _admin: User = Depends(require_admin),
):
    """获取采集日志（最近 N 条）。"""
    logs = collector_service.collection_logs[-limit:]
    if instance_id:
        logs = [l for l in logs if l.get("instance_id") == instance_id]
    return ResponseModel(data=list(reversed(logs)))


@router.get("/status", response_model=ResponseModel[dict])
async def get_system_status(_user: User = Depends(require_auth)):
    """获取系统运行状态摘要。"""
    settings = get_settings()
    success_count = sum(1 for l in collector_service.collection_logs[-50:] if l.get("success"))
    total_recent = min(len(collector_service.collection_logs), 50)
    return ResponseModel(data={
        "version": settings.app_version,
        "collector_running": collector_service._running,
        "influxdb_connected": influxdb_service.is_connected,
        "monitored_instances": len(collector_service.latest_metrics),
        "recent_success_rate": round(success_count / max(total_recent, 1) * 100, 1),
        "collection_log_count": len(collector_service.collection_logs),
    })
