"""
PostgreSQL 指标采集器。
"""

import time
from typing import Optional

import asyncpg

from app.collectors.base import BaseCollector, CollectorResult


class PostgreSQLCollector(BaseCollector):
    """PostgreSQL 数据库指标采集器。"""

    async def connect(self) -> None:
        """创建 PostgreSQL 连接池。"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                user=self.username or "postgres",
                password=self.password,
                database=self.database_name or "postgres",
                min_size=1,
                max_size=3,
            )

    async def close(self) -> None:
        """关闭连接池。"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def test_connection(self) -> tuple[bool, str, Optional[float]]:
        """测试 PostgreSQL 连接。"""
        start = time.monotonic()
        try:
            await self.connect()
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            latency = (time.monotonic() - start) * 1000
            return True, "连接成功", latency
        except Exception as e:
            return False, f"连接失败: {e}", None
        finally:
            await self.close()

    async def collect(self) -> CollectorResult:
        """采集 PostgreSQL 指标。"""
        metrics: dict[str, float] = {}

        async with self._pool.acquire() as conn:
            # 连接数
            metrics["connections"] = float(
                await conn.fetchval(
                    "SELECT count(*) FROM pg_stat_activity WHERE state IS NOT NULL"
                )
            )
            metrics["max_connections"] = float(
                await conn.fetchval("SHOW max_connections")
            )

            # 事务统计（累计值；速率由 CollectorService 差分）
            row = await conn.fetchrow(
                "SELECT sum(xact_commit) as commits, sum(xact_rollback) as rollbacks "
                "FROM pg_stat_database"
            )
            metrics["transactions_commit"] = float(row["commits"] or 0)
            metrics["transactions_rollback"] = float(row["rollbacks"] or 0)
            metrics["xact_total"] = (
                metrics["transactions_commit"] + metrics["transactions_rollback"]
            )
            metrics["tps"] = metrics["xact_total"]  # 首采集先用累计，后续由服务改写为速率

            # 死锁
            metrics["deadlocks"] = float(
                await conn.fetchval(
                    "SELECT sum(deadlocks) FROM pg_stat_database"
                ) or 0
            )

            # 缓存命中率
            cache_row = await conn.fetchrow(
                "SELECT sum(blks_hit) as hits, sum(blks_read) as reads FROM pg_stat_database"
            )
            hits = float(cache_row["hits"] or 0)
            reads = float(cache_row["reads"] or 0)
            total = hits + reads
            metrics["cache_hit_rate"] = (hits / total * 100) if total > 0 else 100.0

            # 索引扫描效率
            idx_row = await conn.fetchrow(
                "SELECT sum(idx_scan) as idx_scan, sum(seq_scan) as seq_scan FROM pg_stat_user_tables"
            )
            idx_scan = float(idx_row["idx_scan"] or 0)
            seq_scan = float(idx_row["seq_scan"] or 0)
            scan_total = idx_scan + seq_scan
            metrics["index_scan_ratio"] = (idx_scan / scan_total * 100) if scan_total > 0 else 0.0

            # 临时文件
            metrics["temp_files_size"] = float(
                await conn.fetchval(
                    "SELECT sum(temp_bytes) FROM pg_stat_database"
                ) or 0
            ) / (1024 * 1024)

            # 锁等待
            metrics["lock_wait_time"] = float(
                await conn.fetchval(
                    "SELECT count(*) FROM pg_locks WHERE NOT granted"
                ) or 0
            )

            # 语句调用累计（pg_stat_statements 存在时）
            if await self._table_exists(conn, "pg_stat_statements"):
                metrics["statements_total"] = float(
                    await conn.fetchval("SELECT sum(calls) FROM pg_stat_statements") or 0
                )
                metrics["qps"] = metrics["statements_total"]
            else:
                metrics["statements_total"] = metrics["xact_total"]
                metrics["qps"] = metrics["tps"]

            # 负载代理：连接使用率（非 OS CPU%）
            metrics["cpu_usage"] = min(
                metrics["connections"] / max(metrics["max_connections"], 1) * 100, 100
            )
            metrics["memory_usage"] = 0.0
            metrics["disk_usage"] = 0.0

        return CollectorResult(success=True, metrics=metrics)

    async def _table_exists(self, conn, table_name: str) -> bool:
        """检查表/视图是否存在。"""
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relname = $1 AND n.nspname = 'public')",
            table_name,
        )
        return bool(result)
