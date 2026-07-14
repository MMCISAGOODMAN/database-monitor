"""
MySQL 指标采集器。
采集连接数、QPS、慢查询、InnoDB、主从延迟等指标。
"""

import time
from typing import Optional

import aiomysql

from app.collectors.base import BaseCollector, CollectorResult


class MySQLCollector(BaseCollector):
    """MySQL 数据库指标采集器。"""

    async def connect(self) -> None:
        """创建 MySQL 连接池。"""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.username or "root",
                password=self.password,
                db=self.database_name or None,
                minsize=1,
                maxsize=3,
                autocommit=True,
            )

    async def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def test_connection(self) -> tuple[bool, str, Optional[float]]:
        """测试 MySQL 连接。"""
        start = time.monotonic()
        try:
            await self.connect()
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
            latency = (time.monotonic() - start) * 1000
            return True, "连接成功", latency
        except Exception as e:
            return False, f"连接失败: {e}", None
        finally:
            await self.close()

    async def _query_value(self, sql: str, default: float = 0.0) -> float:
        """执行查询并返回单个数值。"""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql)
                row = await cur.fetchone()
                if row and row[0] is not None:
                    return float(row[0])
        return default

    async def _query_status(self, var_name: str) -> float:
        """查询 SHOW GLOBAL STATUS 变量值。"""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SHOW GLOBAL STATUS LIKE '{var_name}'")
                row = await cur.fetchone()
                if row:
                    return float(row[1])
        return 0.0

    async def collect(self) -> CollectorResult:
        """采集 MySQL 全部指标。"""
        metrics: dict[str, float] = {}

        # 基础指标（计数器原始值；速率由 CollectorService 差分计算）
        metrics["connections"] = await self._query_status("Threads_connected")
        metrics["max_connections"] = await self._query_value("SELECT @@global.max_connections")
        metrics["max_used_connections"] = await self._query_status("Max_used_connections")
        metrics["questions_total"] = await self._query_status("Questions")
        metrics["com_commit_total"] = await self._query_status("Com_commit")
        metrics["com_rollback_total"] = await self._query_status("Com_rollback")
        metrics["slow_queries_total"] = await self._query_status("Slow_queries")
        metrics["uptime"] = await self._query_status("Uptime")

        uptime = max(metrics["uptime"], 1.0)
        # 首次/无差分时的近似速率（生命周期平均）
        metrics["qps"] = metrics["questions_total"] / uptime
        metrics["tps"] = (
            metrics["com_commit_total"] + metrics["com_rollback_total"]
        ) / uptime
        metrics["slow_queries"] = metrics["slow_queries_total"] / uptime

        # InnoDB 性能指标
        buffer_reads = await self._query_status("Innodb_buffer_pool_read_requests")
        buffer_miss = await self._query_status("Innodb_buffer_pool_reads")
        if buffer_reads > 0:
            metrics["innodb_buffer_hit_rate"] = (1 - buffer_miss / buffer_reads) * 100
        else:
            metrics["innodb_buffer_hit_rate"] = 100.0

        metrics["innodb_data_read"] = await self._query_status("Innodb_data_read")
        metrics["innodb_data_written"] = await self._query_status("Innodb_data_written")
        metrics["created_tmp_tables"] = await self._query_status("Created_tmp_tables")

        # 主从复制延迟
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SHOW SLAVE STATUS")
                    row = await cur.fetchone()
                    if row:
                        cols = [d[0] for d in cur.description]
                        if "Seconds_Behind_Master" in cols:
                            idx = cols.index("Seconds_Behind_Master")
                            val = row[idx]
                            metrics["replication_lag"] = float(val) if val is not None else 0.0
                        if "Slave_IO_Running" in cols:
                            metrics["slave_io_running"] = (
                                1.0 if row[cols.index("Slave_IO_Running")] == "Yes" else 0.0
                            )
        except Exception:
            metrics["replication_lag"] = 0.0

        # 负载代理：连接使用率（非宿主机真实 CPU%）
        max_conn = metrics["max_connections"] or float(self.max_connections) or 1.0
        metrics["cpu_usage"] = min(metrics.get("connections", 0) / max_conn * 100, 100)
        metrics["memory_usage"] = await self._query_status("Innodb_buffer_pool_bytes_data") / (
            1024 * 1024
        )
        metrics["disk_usage"] = 0.0

        slow_queries = []
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT start_time, query_time, lock_time, rows_examined, sql_text "
                        "FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10"
                    )
                    rows = await cur.fetchall()
                    for row in rows:
                        slow_queries.append({
                            "timestamp": str(row[0]),
                            "query_time": float(row[1]),
                            "lock_time": float(row[2]),
                            "rows_examined": int(row[3]),
                            "sql_text": str(row[4])[:500],
                        })
        except Exception:
            pass

        return CollectorResult(
            success=True,
            metrics=metrics,
            slow_queries=slow_queries,
        )
