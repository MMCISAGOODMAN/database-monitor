"""
分库型结构化优化顾问。
根据采集指标生成带等级、指标依据与操作建议的条目。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence


SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class AdviceItem:
    """单条优化建议。"""

    code: str
    severity: str  # critical / warning / info
    title: str
    metric: str
    value: float
    threshold: float
    advice: str

    def to_dict(self) -> dict:
        return asdict(self)


class AdvisorService:
    """数据库优化顾问。"""

    def analyze(
        self,
        db_type: str,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int] = None,
        slow_queries: Optional[Sequence[Any]] = None,
    ) -> List[dict]:
        """返回按严重度排序的结构化建议列表；健康时返回空列表。"""
        metrics = metrics or {}
        handlers = {
            "mysql": self._analyze_mysql,
            "postgresql": self._analyze_postgresql,
            "redis": self._analyze_redis,
            "mongodb": self._analyze_mongodb,
        }
        handler = handlers.get(db_type, self._analyze_generic)
        items = handler(metrics, max_connections=max_connections, slow_queries=slow_queries or [])
        items.sort(key=lambda x: SEVERITY_ORDER.get(x.severity, 9))
        return [i.to_dict() for i in items]

    def top_advice(
        self,
        db_type: str,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int] = None,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
    ) -> tuple[str, str]:
        """供告警根因分析：返回 (root_cause, suggestion)。"""
        items = self.analyze(db_type, metrics, max_connections=max_connections)
        if metric_name:
            matched = [i for i in items if i["metric"] == metric_name]
            if matched:
                top = matched[0]
                return top["title"], top["advice"]
            if metric_value is not None:
                return (
                    f"{metric_name} = {metric_value:.2f}，指标异常",
                    "请结合慢查询、连接数与资源使用进一步排查",
                )
        if items:
            top = items[0]
            return top["title"], top["advice"]
        return "指标异常，需进一步排查", "请联系 DBA 团队分析"

    def _connection_ratio(
        self, metrics: Dict[str, float], max_connections: Optional[int]
    ) -> float:
        connections = float(metrics.get("connections", 0) or 0)
        max_conn = float(
            metrics.get("max_connections")
            or max_connections
            or 0
        )
        if max_conn <= 0:
            return 0.0
        return connections / max_conn * 100

    def _analyze_mysql(
        self,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int],
        slow_queries: Sequence[Any],
    ) -> List[AdviceItem]:
        items: List[AdviceItem] = []
        ratio = self._connection_ratio(metrics, max_connections)
        if ratio > 90:
            items.append(AdviceItem(
                code="mysql_conn_critical",
                severity="critical",
                title=f"连接数使用率过高（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=90,
                advice="立即检查连接泄漏或增加 max_connections，并评估连接池配置",
            ))
        elif ratio > 80:
            items.append(AdviceItem(
                code="mysql_conn_warning",
                severity="warning",
                title=f"连接数接近上限（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=80,
                advice="建议调整 max_connections 或排查空闲长连接",
            ))

        slow_rate = float(metrics.get("slow_queries", 0) or 0)
        if slow_rate > 5:
            items.append(AdviceItem(
                code="mysql_slow_critical",
                severity="critical",
                title=f"慢查询速率过高（{slow_rate:.2f}/s）",
                metric="slow_queries",
                value=slow_rate,
                threshold=5,
                advice="立即分析慢查询日志，优化 SQL 并补充索引",
            ))
        elif slow_rate > 1 or len(slow_queries) >= 5:
            value = slow_rate if slow_rate > 0 else float(len(slow_queries))
            items.append(AdviceItem(
                code="mysql_slow_warning",
                severity="warning",
                title="慢查询偏多",
                metric="slow_queries",
                value=value,
                threshold=1,
                advice="建议开启/分析 slow_log，针对高频慢 SQL 添加索引或改写",
            ))

        hit = float(metrics.get("innodb_buffer_hit_rate", 100) or 100)
        if hit < 90:
            items.append(AdviceItem(
                code="mysql_buffer_hit",
                severity="warning",
                title=f"InnoDB Buffer Pool 命中率偏低（{hit:.1f}%）",
                metric="innodb_buffer_hit_rate",
                value=hit,
                threshold=90,
                advice="适当增大 innodb_buffer_pool_size，减少磁盘读",
            ))

        tmp = float(metrics.get("created_tmp_tables", 0) or 0)
        if tmp > 1000:
            items.append(AdviceItem(
                code="mysql_tmp_tables",
                severity="info",
                title=f"临时表创建较多（{tmp:.0f}）",
                metric="created_tmp_tables",
                value=tmp,
                threshold=1000,
                advice="检查排序/分组未走索引的查询，必要时调整 tmp_table_size",
            ))

        lag = float(metrics.get("replication_lag", 0) or 0)
        if lag > 30:
            items.append(AdviceItem(
                code="mysql_repl_lag_critical",
                severity="critical",
                title=f"主从复制延迟过高（{lag:.1f}s）",
                metric="replication_lag",
                value=lag,
                threshold=30,
                advice="检查从库 IO/SQL 线程、网络与主库写入压力",
            ))
        elif lag > 10:
            items.append(AdviceItem(
                code="mysql_repl_lag",
                severity="warning",
                title=f"主从复制延迟偏高（{lag:.1f}s）",
                metric="replication_lag",
                value=lag,
                threshold=10,
                advice="关注从库性能与主库大批量写入",
            ))

        if metrics.get("slave_io_running") == 0.0 and "slave_io_running" in metrics:
            items.append(AdviceItem(
                code="mysql_slave_io",
                severity="critical",
                title="从库 IO 线程未运行",
                metric="slave_io_running",
                value=0,
                threshold=1,
                advice="检查复制配置与错误日志，恢复 Slave_IO_Running",
            ))

        cpu = float(metrics.get("cpu_usage", 0) or 0)
        if cpu > 80:
            items.append(AdviceItem(
                code="mysql_load",
                severity="warning" if cpu < 95 else "critical",
                title=f"负载代理指标偏高（{cpu:.1f}%）",
                metric="cpu_usage",
                value=cpu,
                threshold=80,
                advice="建议检查慢查询日志，优化 SQL 语句，或考虑扩容",
            ))

        return items

    def _analyze_postgresql(
        self,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int],
        slow_queries: Sequence[Any],
    ) -> List[AdviceItem]:
        items: List[AdviceItem] = []
        ratio = self._connection_ratio(metrics, max_connections)
        if ratio > 90:
            items.append(AdviceItem(
                code="pg_conn_critical",
                severity="critical",
                title=f"连接数使用率过高（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=90,
                advice="检查连接池与泄漏连接，必要时提高 max_connections",
            ))
        elif ratio > 80:
            items.append(AdviceItem(
                code="pg_conn_warning",
                severity="warning",
                title=f"连接数接近上限（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=80,
                advice="建议优化连接复用或调整 max_connections",
            ))

        hit = float(metrics.get("cache_hit_rate", 100) or 100)
        if hit < 90:
            items.append(AdviceItem(
                code="pg_cache_hit",
                severity="warning",
                title=f"缓存命中率偏低（{hit:.1f}%）",
                metric="cache_hit_rate",
                value=hit,
                threshold=90,
                advice="考虑增大 shared_buffers，并检查冷数据扫描",
            ))

        deadlocks = float(metrics.get("deadlocks", 0) or 0)
        if deadlocks > 10:
            items.append(AdviceItem(
                code="pg_deadlocks",
                severity="warning",
                title=f"死锁次数偏高（{deadlocks:.0f}）",
                metric="deadlocks",
                value=deadlocks,
                threshold=10,
                advice="检查事务顺序与锁争用，缩短长事务",
            ))

        locks = float(metrics.get("lock_wait_time", 0) or 0)
        if locks > 5:
            items.append(AdviceItem(
                code="pg_lock_wait",
                severity="warning",
                title=f"当前锁等待较多（{locks:.0f}）",
                metric="lock_wait_time",
                value=locks,
                threshold=5,
                advice="排查阻塞查询，优化事务粒度与索引",
            ))

        idx = float(metrics.get("index_scan_ratio", 100) or 100)
        if 0 < idx < 50:
            items.append(AdviceItem(
                code="pg_index_scan",
                severity="info",
                title=f"索引扫描占比偏低（{idx:.1f}%）",
                metric="index_scan_ratio",
                value=idx,
                threshold=50,
                advice="检查缺失索引与全表扫描 SQL",
            ))

        temp_mb = float(metrics.get("temp_files_size", 0) or 0)
        if temp_mb > 512:
            items.append(AdviceItem(
                code="pg_temp_files",
                severity="warning",
                title=f"临时文件占用偏高（{temp_mb:.0f} MB）",
                metric="temp_files_size",
                value=temp_mb,
                threshold=512,
                advice="优化大排序/哈希操作，或适当调大 work_mem",
            ))

        cpu = float(metrics.get("cpu_usage", 0) or 0)
        if cpu > 80:
            items.append(AdviceItem(
                code="pg_load",
                severity="warning" if cpu < 95 else "critical",
                title=f"负载代理指标偏高（{cpu:.1f}%）",
                metric="cpu_usage",
                value=cpu,
                threshold=80,
                advice="建议检查慢查询与连接争用，必要时扩容",
            ))

        return items

    def _analyze_redis(
        self,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int],
        slow_queries: Sequence[Any],
    ) -> List[AdviceItem]:
        items: List[AdviceItem] = []
        hit = float(metrics.get("hit_rate", 100) or 100)
        if hit < 80:
            items.append(AdviceItem(
                code="redis_hit_rate",
                severity="warning",
                title=f"缓存命中率偏低（{hit:.1f}%）",
                metric="hit_rate",
                value=hit,
                threshold=80,
                advice="检查 key 过期策略与缓存穿透，评估热点预热",
            ))

        mem = float(metrics.get("memory_usage", 0) or 0)
        if mem > 90:
            items.append(AdviceItem(
                code="redis_memory_critical",
                severity="critical",
                title=f"内存使用率过高（{mem:.1f}%）",
                metric="memory_usage",
                value=mem,
                threshold=90,
                advice="清理冷 key、调整 maxmemory-policy，或扩容内存",
            ))
        elif mem > 80:
            items.append(AdviceItem(
                code="redis_memory_warning",
                severity="warning",
                title=f"内存使用率偏高（{mem:.1f}%）",
                metric="memory_usage",
                value=mem,
                threshold=80,
                advice="关注大 key 与淘汰策略，提前规划扩容",
            ))

        blocked = float(metrics.get("blocked_clients", 0) or 0)
        if blocked > 0:
            items.append(AdviceItem(
                code="redis_blocked",
                severity="warning",
                title=f"存在阻塞客户端（{blocked:.0f}）",
                metric="blocked_clients",
                value=blocked,
                threshold=0,
                advice="检查 BLPOP/BRPOP 等阻塞命令与慢消费者",
            ))

        if metrics.get("rdb_last_bgsave_status_ok") == 0.0 and "rdb_last_bgsave_status_ok" in metrics:
            items.append(AdviceItem(
                code="redis_bgsave",
                severity="critical",
                title="最近一次 RDB 后台保存失败",
                metric="rdb_last_bgsave_status_ok",
                value=0,
                threshold=1,
                advice="检查磁盘空间与 Redis 日志中的 bgsave 错误",
            ))

        return items

    def _analyze_mongodb(
        self,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int],
        slow_queries: Sequence[Any],
    ) -> List[AdviceItem]:
        items: List[AdviceItem] = []
        queued = float(metrics.get("queued_operations", 0) or 0)
        if queued > 50:
            items.append(AdviceItem(
                code="mongo_queue_critical",
                severity="critical",
                title=f"操作队列积压严重（{queued:.0f}）",
                metric="queued_operations",
                value=queued,
                threshold=50,
                advice="检查慢查询、锁与是否需要扩容读副本",
            ))
        elif queued > 10:
            items.append(AdviceItem(
                code="mongo_queue",
                severity="warning",
                title=f"操作队列积压（{queued:.0f}）",
                metric="queued_operations",
                value=queued,
                threshold=10,
                advice="排查热点集合与索引缺失",
            ))

        faults = float(metrics.get("page_faults", 0) or 0)
        if faults > 1000:
            items.append(AdviceItem(
                code="mongo_page_faults",
                severity="warning",
                title=f"页面错误偏高（{faults:.0f}）",
                metric="page_faults",
                value=faults,
                threshold=1000,
                advice="内存可能不足，考虑增加 RAM 或优化工作集",
            ))

        if "replica_set_state" in metrics and metrics.get("replica_set_state", 1) == 0.0:
            items.append(AdviceItem(
                code="mongo_replica",
                severity="info",
                title="当前节点非 Primary",
                metric="replica_set_state",
                value=0,
                threshold=1,
                advice="确认是否为预期只读节点；异常时检查 replSet 选举状态",
            ))

        ratio = self._connection_ratio(metrics, max_connections)
        if ratio > 80:
            items.append(AdviceItem(
                code="mongo_conn",
                severity="warning",
                title=f"连接数使用率偏高（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=80,
                advice="检查应用连接池配置，避免无限制新建连接",
            ))

        return items

    def _analyze_generic(
        self,
        metrics: Dict[str, float],
        *,
        max_connections: Optional[int],
        slow_queries: Sequence[Any],
    ) -> List[AdviceItem]:
        items: List[AdviceItem] = []
        ratio = self._connection_ratio(metrics, max_connections)
        if ratio > 80:
            items.append(AdviceItem(
                code="generic_conn",
                severity="warning",
                title=f"连接数使用率偏高（{ratio:.1f}%）",
                metric="connection_ratio",
                value=ratio,
                threshold=80,
                advice="检查连接池与数据库最大连接配置",
            ))
        cpu = float(metrics.get("cpu_usage", 0) or 0)
        if cpu > 80:
            items.append(AdviceItem(
                code="generic_cpu",
                severity="warning",
                title=f"负载代理指标偏高（{cpu:.1f}%）",
                metric="cpu_usage",
                value=cpu,
                threshold=80,
                advice="检查慢查询与瞬时流量，考虑扩容",
            ))
        return items


advisor_service = AdvisorService()
