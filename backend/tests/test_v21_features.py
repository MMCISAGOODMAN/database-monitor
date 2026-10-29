"""
v2.1 功能测试：采集间隔判定、告警静默、审计日志、实例对比。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.alert_service import AlertService
from app.services.collector_service import CollectorService


def test_should_collect_respects_instance_interval():
    svc = CollectorService()
    inst = MagicMock()
    inst.collector_interval_seconds = 60
    inst.last_collected_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    assert svc._should_collect(inst) is False

    inst.last_collected_at = datetime.now(timezone.utc) - timedelta(seconds=90)
    assert svc._should_collect(inst) is True


def test_should_collect_when_never_collected():
    svc = CollectorService()
    inst = MagicMock()
    inst.collector_interval_seconds = 0
    inst.last_collected_at = None
    assert svc._should_collect(inst) is True


@pytest.mark.asyncio
async def test_fire_alert_skipped_when_silenced():
    svc = AlertService()
    session = MagicMock()
    instance = MagicMock(id=1, name="demo", status="normal", db_type="mysql", max_connections=100)
    rule = MagicMock(
        id=1,
        name="CPU",
        metric_name="cpu_usage",
        operator=">",
        threshold=80,
        severity="warning",
        silenced_until=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    await svc._fire_alert(session, instance, rule, 90.0)
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_silence_and_audit_and_compare(client):
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/instances", json={
        "name": "cmp-a",
        "db_type": "mysql",
        "host": "127.0.0.1",
        "port": 3306,
        "username": "root",
        "password": "x",
        "collector_interval_seconds": 45,
    }, headers=headers)
    assert create.status_code == 200
    id_a = create.json()["data"]["id"]
    assert create.json()["data"]["collector_interval_seconds"] == 45

    create_b = await client.post("/api/instances", json={
        "name": "cmp-b",
        "db_type": "redis",
        "host": "127.0.0.1",
        "port": 6379,
        "password": "",
    }, headers=headers)
    id_b = create_b.json()["data"]["id"]

    rule_resp = await client.post("/api/alerts/rules", json={
        "name": "临时静默规则",
        "metric_name": "cpu_usage",
        "operator": ">",
        "threshold": 90,
        "duration_seconds": 60,
        "severity": "warning",
    }, headers=headers)
    assert rule_resp.status_code == 200
    rule_id = rule_resp.json()["data"]["id"]
    silence = await client.post(
        f"/api/alerts/rules/{rule_id}/silence",
        json={"hours": 1},
        headers=headers,
    )
    assert silence.status_code == 200
    assert silence.json()["data"]["silenced_until"] is not None

    compare = await client.get(
        f"/api/dashboard/compare?ids={id_a},{id_b}",
        headers=headers,
    )
    assert compare.status_code == 200
    assert len(compare.json()["data"]) == 2

    audit = await client.get("/api/system/audit-logs", headers=headers)
    assert audit.status_code == 200
    actions = [x["action"] for x in audit.json()["data"]]
    assert "create" in actions
    assert "silence" in actions
