"""
MongoDB 指标采集器。
"""

import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient

from app.collectors.base import BaseCollector, CollectorResult


class MongoDBCollector(BaseCollector):
    """MongoDB 指标采集器。"""

    async def connect(self) -> None:
        """创建 MongoDB 连接。"""
        if self._pool is None:
            auth = f"{self.username}:{self.password}@" if self.username else ""
            uri = f"mongodb://{auth}{self.host}:{self.port}"
            if self.database_name:
                uri += f"/{self.database_name}"
            self._pool = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)

    async def close(self) -> None:
        """关闭 MongoDB 连接。"""
        if self._pool:
            self._pool.close()
            self._pool = None

    async def test_connection(self) -> tuple[bool, str, Optional[float]]:
        """测试 MongoDB 连接。"""
        start = time.monotonic()
        try:
            await self.connect()
            await self._pool.admin.command("ping")
            latency = (time.monotonic() - start) * 1000
            return True, "连接成功", latency
        except Exception as e:
            return False, f"连接失败: {e}", None
        finally:
            await self.close()

    async def collect(self) -> CollectorResult:
        """采集 MongoDB 指标。"""
        metrics: dict[str, float] = {}
        server_status = await self._pool.admin.command("serverStatus")

        # 连接数
        metrics["connections"] = float(server_status.get("connections", {}).get("current", 0))
        metrics["max_connections"] = float(
            server_status.get("connections", {}).get("available", 0)
        ) + metrics["connections"]

        # 操作计数（累计；速率由 CollectorService 差分）
        opcounters = server_status.get("opcounters", {})
        metrics["ops_insert"] = float(opcounters.get("insert", 0))
        metrics["ops_query"] = float(opcounters.get("query", 0))
        metrics["ops_update"] = float(opcounters.get("update", 0))
        metrics["ops_delete"] = float(opcounters.get("delete", 0))
        metrics["ops_total"] = sum([
            metrics["ops_insert"], metrics["ops_query"],
            metrics["ops_update"], metrics["ops_delete"],
        ])
        metrics["qps"] = metrics["ops_total"]
        metrics["page_faults_total"] = float(
            server_status.get("extra_info", {}).get("page_faults", 0)
        )

        # 复制集状态
        repl = server_status.get("repl", {})
        metrics["replica_set_state"] = 1.0 if repl.get("ismaster") or repl.get("isWritablePrimary") else 0.0

        # 性能指标
        global_lock = server_status.get("globalLock", {})
        metrics["active_clients"] = float(global_lock.get("activeClients", {}).get("total", 0))
        metrics["queued_operations"] = float(global_lock.get("currentQueue", {}).get("total", 0))

        # 页面错误（原始累计，首采集直接展示）
        metrics["page_faults"] = metrics["page_faults_total"]

        # 内存
        mem = server_status.get("mem", {})
        metrics["memory_mapped"] = float(mem.get("mapped", 0))
        metrics["memory_virtual"] = float(mem.get("virtual", 0))
        metrics["memory_usage"] = float(mem.get("resident", 0))

        # 负载代理：连接使用率
        metrics["cpu_usage"] = min(
            metrics["connections"] / max(metrics["max_connections"], 1) * 100, 100
        )
        metrics["disk_usage"] = 0.0

        return CollectorResult(success=True, metrics=metrics)
