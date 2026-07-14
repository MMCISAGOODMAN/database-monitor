"""
优化顾问单元测试。
"""

from app.services.advisor_service import advisor_service


def test_healthy_mysql_returns_empty():
    assert advisor_service.analyze("mysql", {
        "connections": 10,
        "max_connections": 100,
        "slow_queries": 0.1,
        "innodb_buffer_hit_rate": 99,
        "replication_lag": 0,
    }) == []


def test_mysql_connection_and_buffer():
    items = advisor_service.analyze("mysql", {
        "connections": 95,
        "max_connections": 100,
        "slow_queries": 0,
        "innodb_buffer_hit_rate": 85,
        "replication_lag": 0,
    })
    codes = {i["code"] for i in items}
    assert "mysql_conn_critical" in codes
    assert "mysql_buffer_hit" in codes
    assert items[0]["severity"] == "critical"
    assert "advice" in items[0]


def test_postgresql_cache_and_deadlocks():
    items = advisor_service.analyze("postgresql", {
        "connections": 20,
        "max_connections": 100,
        "cache_hit_rate": 80,
        "deadlocks": 20,
        "lock_wait_time": 0,
        "index_scan_ratio": 80,
        "temp_files_size": 0,
    })
    codes = {i["code"] for i in items}
    assert "pg_cache_hit" in codes
    assert "pg_deadlocks" in codes


def test_redis_memory_and_hit_rate():
    items = advisor_service.analyze("redis", {
        "hit_rate": 50,
        "memory_usage": 95,
        "blocked_clients": 2,
        "rdb_last_bgsave_status_ok": 1,
    })
    codes = {i["code"] for i in items}
    assert "redis_hit_rate" in codes
    assert "redis_memory_critical" in codes
    assert "redis_blocked" in codes


def test_mongodb_queue():
    items = advisor_service.analyze("mongodb", {
        "queued_operations": 80,
        "page_faults": 10,
        "replica_set_state": 1,
        "connections": 10,
        "max_connections": 100,
    })
    assert any(i["code"] == "mongo_queue_critical" for i in items)


def test_top_advice_prefers_metric():
    cause, suggestion = advisor_service.top_advice(
        "mysql",
        {
            "connections": 90,
            "max_connections": 100,
            "slow_queries": 3,
            "innodb_buffer_hit_rate": 99,
        },
        metric_name="slow_queries",
        metric_value=3,
    )
    assert "慢查询" in cause
    assert suggestion
