"""
Redis 指标采集器。
"""

import time
from typing import Optional

import redis.asyncio as aioredis

from app.collectors.base import BaseCollector, CollectorResult


class RedisCollector(BaseCollector):
    """Redis 指标采集器。"""

    async def connect(self) -> None:
        """创建 Redis 连接。"""
        if self._pool is None:
            self._pool = aioredis.Redis(
                host=self.host,
                port=self.port,
                password=self.password or None,
                db=int(self.database_name) if self.database_name.isdigit() else 0,
                decode_responses=True,
            )

    async def close(self) -> None:
        """关闭 Redis 连接。"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def test_connection(self) -> tuple[bool, str, Optional[float]]:
        """测试 Redis 连接。"""
        start = time.monotonic()
        try:
            await self.connect()
            await self._pool.ping()
            latency = (time.monotonic() - start) * 1000
            return True, "连接成功", latency
        except Exception as e:
            return False, f"连接失败: {e}", None
        finally:
            await self.close()

    async def collect(self) -> CollectorResult:
        """采集 Redis 指标。"""
        info = await self._pool.info()
        metrics: dict[str, float] = {}

        # 基础指标
        metrics["memory_used"] = float(info.get("used_memory", 0)) / (1024 * 1024)
        metrics["memory_peak"] = float(info.get("used_memory_peak", 0)) / (1024 * 1024)
        metrics["connections"] = float(info.get("connected_clients", 0))
        metrics["max_connections"] = float(self.max_connections)

        # 命中率
        hits = float(info.get("keyspace_hits", 0))
        misses = float(info.get("keyspace_misses", 0))
        total = hits + misses
        metrics["hit_rate"] = (hits / total * 100) if total > 0 else 100.0

        # Key 统计
        metrics["total_keys"] = sum(
            float(db_info.get("keys", 0))
            for key, db_info in info.items()
            if key.startswith("db") and isinstance(db_info, dict)
        )
        metrics["expired_keys"] = float(info.get("expired_keys", 0))

        # 性能指标
        metrics["ops_per_sec"] = float(info.get("instantaneous_ops_per_sec", 0))
        metrics["qps"] = metrics["ops_per_sec"]
        metrics["blocked_clients"] = float(info.get("blocked_clients", 0))

        # 持久化
        metrics["rdb_last_save_time"] = float(info.get("rdb_last_save_time", 0))
        metrics["aof_enabled"] = 1.0 if info.get("aof_enabled") else 0.0
        metrics["rdb_last_bgsave_status_ok"] = 1.0 if info.get("rdb_last_bgsave_status") == "ok" else 0.0

        # 资源
        maxmem = float(info.get("maxmemory", 0))
        if maxmem > 0:
            metrics["memory_usage"] = float(info.get("used_memory", 0)) / maxmem * 100
        else:
            metrics["memory_usage"] = 0.0

        # 累计 CPU 秒，供服务差分估算单核占用百分比
        metrics["used_cpu_sys"] = float(info.get("used_cpu_sys", 0))
        metrics["used_cpu_user"] = float(info.get("used_cpu_user", 0))
        metrics["cpu_seconds_total"] = metrics["used_cpu_sys"] + metrics["used_cpu_user"]
        # 无差分时用连接占比作为负载代理，避免把累计秒数当百分比
        max_conn = metrics["max_connections"] or float(self.max_connections) or 1.0
        metrics["cpu_usage"] = min(metrics["connections"] / max_conn * 100, 100)
        metrics["disk_usage"] = 0.0

        return CollectorResult(success=True, metrics=metrics)
