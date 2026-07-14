"""
告警引擎单元测试。
"""

import pytest

from app.services.alert_service import AlertService


@pytest.fixture
def alert_service_instance():
    """创建告警服务实例。"""
    return AlertService()


class TestAlertEvaluation:
    """告警条件评估测试。"""

    def test_greater_than(self, alert_service_instance):
        svc = alert_service_instance
        assert svc._evaluate(">", 85.0, 80.0) is True
        assert svc._evaluate(">", 75.0, 80.0) is False

    def test_less_than(self, alert_service_instance):
        svc = alert_service_instance
        assert svc._evaluate("<", 50.0, 80.0) is True
        assert svc._evaluate("<", 90.0, 80.0) is False

    def test_greater_equal(self, alert_service_instance):
        svc = alert_service_instance
        assert svc._evaluate(">=", 80.0, 80.0) is True
        assert svc._evaluate(">=", 79.0, 80.0) is False

    def test_equal(self, alert_service_instance):
        svc = alert_service_instance
        assert svc._evaluate("==", 100.0, 100.0) is True
        assert svc._evaluate("==", 99.0, 100.0) is False


class TestRootCauseAnalysis:
    """根因分析测试。"""

    def test_cpu_usage_analysis(self, alert_service_instance):
        from unittest.mock import MagicMock
        svc = alert_service_instance
        rule = MagicMock(metric_name="cpu_usage")
        instance = MagicMock(id=1, max_connections=100, db_type="mysql")
        cause, suggestion = svc._analyze_root_cause(rule, 92.5, instance)
        assert "负载" in cause or "cpu_usage" in cause
        assert "慢查询" in suggestion or "优化" in suggestion or "扩容" in suggestion

    def test_connection_ratio_analysis(self, alert_service_instance):
        from unittest.mock import MagicMock
        svc = alert_service_instance
        rule = MagicMock(metric_name="connection_ratio")
        instance = MagicMock(id=1, max_connections=200, db_type="mysql")
        cause, suggestion = svc._analyze_root_cause(rule, 85.0, instance)
        assert "连接数" in cause
        assert "max_connections" in suggestion or "连接" in suggestion
