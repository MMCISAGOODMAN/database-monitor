"""
告警规则引擎服务。
评估指标是否触发告警，支持聚合去重。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.alert import Alert, AlertRule
from app.models.instance import DatabaseInstance
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# 内置告警规则
BUILTIN_RULES = [
    {
        "name": "CPU使用率警告",
        "metric_name": "cpu_usage",
        "operator": ">",
        "threshold": 80.0,
        "duration_seconds": 300,
        "severity": "warning",
    },
    {
        "name": "CPU使用率紧急",
        "metric_name": "cpu_usage",
        "operator": ">",
        "threshold": 95.0,
        "duration_seconds": 120,
        "severity": "critical",
    },
    {
        "name": "连接数过高",
        "metric_name": "connection_ratio",
        "operator": ">",
        "threshold": 80.0,
        "duration_seconds": 60,
        "severity": "warning",
    },
    {
        "name": "主从延迟过高",
        "metric_name": "replication_lag",
        "operator": ">",
        "threshold": 10.0,
        "duration_seconds": 60,
        "severity": "warning",
    },
    {
        "name": "慢查询过多",
        "metric_name": "slow_queries",
        "operator": ">",
        "threshold": 1.0,  # 慢查询速率（次/秒）
        "duration_seconds": 60,
        "severity": "warning",
    },
    {
        "name": "缓存命中率过低",
        "metric_name": "hit_rate",
        "operator": "<",
        "threshold": 80.0,
        "duration_seconds": 120,
        "severity": "warning",
    },
    {
        "name": "内存使用率过高",
        "metric_name": "memory_usage",
        "operator": ">",
        "threshold": 90.0,
        "duration_seconds": 120,
        "severity": "warning",
    },
]


class AlertService:
    """告警引擎。"""

    def __init__(self) -> None:
        # 规则触发状态追踪：{(instance_id, rule_id): first_trigger_time}
        self._trigger_tracker: Dict[Tuple[int, int], datetime] = {}
        # 告警聚合：{(instance_id, rule_name): last_sent_time}
        self._alert_aggregate: Dict[Tuple[int, str], datetime] = {}

    async def init_builtin_rules(self) -> None:
        """初始化内置告警规则。"""
        async with AsyncSessionLocal() as session:
            for rule_data in BUILTIN_RULES:
                existing = await session.execute(
                    select(AlertRule).where(
                        and_(
                            AlertRule.name == rule_data["name"],
                            AlertRule.is_builtin == True,  # noqa: E712
                        )
                    )
                )
                if not existing.scalar_one_or_none():
                    rule = AlertRule(
                        name=rule_data["name"],
                        metric_name=rule_data["metric_name"],
                        operator=rule_data["operator"],
                        threshold=rule_data["threshold"],
                        duration_seconds=rule_data["duration_seconds"],
                        severity=rule_data["severity"],
                        is_builtin=True,
                        is_enabled=True,
                    )
                    session.add(rule)
            await session.commit()

    async def check_metrics(self, instance: DatabaseInstance, metrics: dict) -> None:
        """检查指标是否触发告警规则。"""
        # 连接比：优先采集到的 @@max_connections / max_connections，与顾问一致
        connections = metrics.get("connections", 0)
        max_conn = metrics.get("max_connections") or instance.max_connections or 0
        if max_conn > 0:
            metrics["connection_ratio"] = connections / max_conn * 100
            metrics["max_connections"] = float(max_conn)

        async with AsyncSessionLocal() as session:
            # 获取适用规则（全局 + 实例专属）
            result = await session.execute(
                select(AlertRule).where(
                    and_(
                        AlertRule.is_enabled == True,  # noqa: E712
                        (AlertRule.instance_id == instance.id) | (AlertRule.instance_id.is_(None)),
                    )
                )
            )
            rules = result.scalars().all()

            for rule in rules:
                metric_value = metrics.get(rule.metric_name)
                if metric_value is None:
                    continue

                triggered = self._evaluate(rule.operator, metric_value, rule.threshold)
                key = (instance.id, rule.id)

                if triggered:
                    if key not in self._trigger_tracker:
                        self._trigger_tracker[key] = datetime.now(timezone.utc)

                    elapsed = (
                        datetime.now(timezone.utc) - self._trigger_tracker[key]
                    ).total_seconds()

                    if elapsed >= rule.duration_seconds:
                        await self._fire_alert(session, instance, rule, metric_value)
                else:
                    self._trigger_tracker.pop(key, None)

    def _evaluate(self, operator: str, value: float, threshold: float) -> bool:
        """评估指标是否满足告警条件。"""
        ops = {
            ">": value > threshold,
            "<": value < threshold,
            ">=": value >= threshold,
            "<=": value <= threshold,
            "==": value == threshold,
        }
        return ops.get(operator, False)

    async def _fire_alert(
        self,
        session: AsyncSession,
        instance: DatabaseInstance,
        rule: AlertRule,
        metric_value: float,
    ) -> None:
        """触发告警并发送通知。"""
        settings = get_settings()
        aggregate_key = (instance.id, rule.name)
        now = datetime.now(timezone.utc)

        # 告警聚合：10分钟内相同告警只发一次
        last_sent = self._alert_aggregate.get(aggregate_key)
        if last_sent and (now - last_sent).total_seconds() < settings.alert_aggregate_window_seconds:
            return

        # 智能根因分析
        root_cause, suggestion = self._analyze_root_cause(rule, metric_value, instance)

        alert = Alert(
            instance_id=instance.id,
            instance_name=instance.name,
            rule_id=rule.id,
            severity=rule.severity,
            title=f"[{rule.severity.upper()}] {instance.name} - {rule.name}",
            message=f"{rule.metric_name} = {metric_value:.2f} (阈值: {rule.operator} {rule.threshold})",
            metric_name=rule.metric_name,
            metric_value=metric_value,
            root_cause=root_cause,
            suggestion=suggestion,
        )
        session.add(alert)

        # 更新实例状态
        if rule.severity == "critical":
            instance.status = "critical"
        elif instance.status != "critical":
            instance.status = "warning"

        await session.commit()

        self._alert_aggregate[aggregate_key] = now

        # 发送通知
        await notification_service.send_alert(alert)

        logger.warning("告警触发: %s - %s", instance.name, rule.name)

    def _analyze_root_cause(
        self, rule: AlertRule, value: float, instance: DatabaseInstance
    ) -> Tuple[str, str]:
        """智能根因分析：复用分库型优化顾问。"""
        from app.services.advisor_service import advisor_service
        from app.services.collector_service import collector_service

        cached = collector_service.latest_metrics.get(instance.id, {})
        metrics = dict(cached.get("metrics") or {})
        metrics[rule.metric_name] = value
        max_conn = float(metrics.get("max_connections") or instance.max_connections or 100)
        metrics["max_connections"] = max_conn
        if rule.metric_name == "connection_ratio":
            metrics["connections"] = max_conn * value / 100.0
        elif rule.metric_name == "cpu_usage":
            metrics["cpu_usage"] = value

        return advisor_service.top_advice(
            getattr(instance, "db_type", None) or "mysql",
            metrics,
            max_connections=int(max_conn),
            metric_name=rule.metric_name,
            metric_value=value,
        )

    async def create_connection_failure_alert(self, instance: DatabaseInstance) -> None:
        """创建连接失败紧急告警。"""
        settings = get_settings()
        aggregate_key = (instance.id, "connection_failure")
        now = datetime.now(timezone.utc)

        last_sent = self._alert_aggregate.get(aggregate_key)
        if last_sent and (now - last_sent).total_seconds() < settings.alert_aggregate_window_seconds:
            return

        async with AsyncSessionLocal() as session:
            alert = Alert(
                instance_id=instance.id,
                instance_name=instance.name,
                severity="critical",
                title=f"[CRITICAL] {instance.name} - 数据库连接失败",
                message=f"无法连接到 {instance.db_type}://{instance.host}:{instance.port}",
                metric_name="connection",
                metric_value=0,
                root_cause="数据库实例不可达，可能是服务宕机、网络故障或认证失败",
                suggestion="检查数据库服务状态、网络连通性和认证凭据",
            )
            session.add(alert)
            await session.commit()

            self._alert_aggregate[aggregate_key] = now
            await notification_service.send_alert(alert)

    async def get_today_alert_count(self) -> int:
        """获取今日告警数。"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Alert.id)).where(Alert.created_at >= today_start)
            )
            return result.scalar() or 0

    async def acknowledge_alert(self, alert_id: int, username: str) -> bool:
        """确认告警。"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalar_one_or_none()
            if alert:
                alert.is_acknowledged = True
                alert.acknowledged_by = username
                alert.acknowledged_at = datetime.now(timezone.utc)
                await session.commit()
                return True
            return False


alert_service = AlertService()
