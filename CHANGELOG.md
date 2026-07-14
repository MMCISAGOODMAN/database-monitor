# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [2.0.0] - 2026-07-14

### Breaking

- `GET /api/instances/{id}/snapshot` 的 `suggestions` 从 `string[]` 改为结构化对象数组：
  `{ code, severity, title, metric, value, threshold, advice }`
- MySQL / MongoDB 等库的 `qps`、`slow_queries` 改为**速率**（差分或生命周期平均），不再直接使用 STATUS 累计值
- Redis `cpu_usage` 不再是 `used_cpu_sys` 累计秒数；改为 CPU 秒差分估算的单核占用%，首采样本回退为连接占比
- 内置「慢查询过多」阈值调整为 `> 1.0`（次/秒）；并新增缓存命中率 / 内存使用率内置规则（仅新库首次初始化写入）

### Added

- 分库型结构化优化顾问 `advisor_service`（MySQL / PostgreSQL / Redis / MongoDB）
- 告警根因分析复用顾问服务
- 详情页按库类型展示关键指标卡片与趋势图
- 详情页 15s 轮询刷新快照与告警
- WebSocket 指数退避重连
- `/api/system/status` 返回 `version` 字段
- 采集计数器差分（QPS / TPS / 慢查询速率 / Redis CPU）

### Fixed

- 删除实例时因 `alerts` / `alert_rules` 外键导致失败的问题（先清理关联数据）
- MySQL `max_connections` 误用 `Max_used_connections` 的问题，改为 `@@global.max_connections`
- 告警连接比与顾问、采集结果使用同一套 max 连接来源

### Changed

- 应用版本升至 `2.0.0`

## [1.0.0] - 2026-06-12

### Added

- 企业级数据库监控大屏初版：MySQL / PostgreSQL / Redis / MongoDB 采集
- 监控大屏、告警、通知渠道、管理页、Docker Compose 一键部署
