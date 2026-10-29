"""
操作审计服务。
复用 operation_logs 表记录管理操作。
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OperationLog, User


class AuditService:
    """写入与查询操作审计日志。"""

    async def log(
        self,
        db: AsyncSession,
        *,
        user: Optional[User],
        action: str,
        resource: str = "",
        detail: str = "",
        ip_address: str = "",
    ) -> None:
        entry = OperationLog(
            user_id=user.id if user else None,
            action=action,
            resource=resource,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()

    async def list_logs(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
    ) -> list[dict]:
        result = await db.execute(
            select(OperationLog).order_by(OperationLog.created_at.desc()).limit(limit)
        )
        logs = result.scalars().all()
        items = []
        for log in logs:
            username = ""
            if log.user_id:
                u = await db.get(User, log.user_id)
                username = u.username if u else ""
            items.append({
                "id": log.id,
                "user_id": log.user_id,
                "username": username,
                "action": log.action,
                "resource": log.resource,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })
        return items


audit_service = AuditService()
