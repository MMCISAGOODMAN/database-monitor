# 数据库监控大屏系统

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

企业级数据库监控大屏系统，支持 MySQL、PostgreSQL、Redis、MongoDB 多种数据库的集中监控，以可视化大屏实时展示核心指标、告警与负载分布。

**仓库地址**：[https://github.com/MMCISAGOODMAN/database-monitor](https://github.com/MMCISAGOODMAN/database-monitor)

## 功能特性

### 监控采集
- 支持 **MySQL / PostgreSQL / Redis / MongoDB** 四种数据库
- 定时轮询采集（默认 30 秒，可配置），并发采集，失败自动重试 3 次
- QPS / 慢查询等采用**计数器差分速率**，避免把累计值当成瞬时指标
- 连接池复用，密码 **Fernet 加密**存储
- 首次启动自动注册 Docker 内 PostgreSQL、Redis 演示实例

### 监控大屏
- **KPI 卡片**：监控总数、平均 QPS、总连接数、今日告警、系统健康度（含真实环比趋势）
- **实例列表**：状态筛选、分组筛选，单击查看趋势，双击下钻详情
- **实时趋势图**：QPS / 连接数 / 慢查询 / CPU，支持 15m / 1h / 6h / 24h
- **历史回放**：选择历史时间点回放指标
- **告警面板**：自动滚动、优先级排序、一键确认
- **负载热力图**：矩形树图展示 QPS 与 CPU 负载
- **告警统计图**：近 7 天告警趋势柱状图
- **深色 / 浅色主题**切换，偏好本地持久化
- WebSocket 实时推送（5 秒指标 / 3 秒告警）

### 告警与通知
- 内置告警规则 + 自定义规则（增删改、启用/禁用）
- **分库型结构化优化顾问**（等级 / 指标依据 / 操作建议）
- 告警根因分析复用顾问引擎
- 告警聚合（10 分钟内相同告警只发一次）
- 通知渠道：企业微信、钉钉、飞书 Webhook、邮件

### 管理功能
- 数据库实例 CRUD（删除时自动清理关联告警/规则）、连接测试、分组管理
- 告警规则与通知渠道完整管理界面
- 采集日志查看（成功/失败/重试记录）
- 数据导出：CSV / JSON（按时间范围）+ PDF 报告
- 用户权限：管理员 / 只读用户

### 详情下钻
- **按库类型**展示关键指标卡片与趋势图（如 Redis 命中率/内存，PG 缓存命中/死锁）
- 慢查询记录、实例参数、结构化智能优化建议
- 相关告警列表；快照约 15 秒自动刷新

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│              Nginx + Vue 3 前端 (8088)                    │
└──────────┬──────────────────────────┬───────────────────┘
           │ HTTP / WebSocket          │
┌──────────▼──────────────────────────▼───────────────────┐
│                 FastAPI 后端 (8000)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ 采集器    │ │ 告警引擎  │ │ 通知服务  │ │ WebSocket │  │
│  └────┬─────┘ └────┬─────┘ └──────────┘ └───────────┘  │
│       │            │                                     │
│  ┌────▼─────┐ ┌────▼─────┐ ┌──────────┐                │
│  │ InfluxDB │ │PostgreSQL│ │  Redis   │                │
│  │ (时序)   │ │ (配置)   │ │ (缓存)   │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────┘
           │
    ┌──────┼──────┬──────────┐
    │      │      │          │
  MySQL  PG   Redis   MongoDB
```

## 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose v2+
- 可用内存 ≥ 2GB

### 一键部署

```bash
git clone https://github.com/MMCISAGOODMAN/database-monitor.git
cd database-monitor

# 启动所有服务
docker compose up -d --build

# 查看状态
docker compose ps
```

| 项目 | 值 |
|------|-----|
| 访问地址 | http://localhost:8088 |
| 默认账号 | `admin` |
| 默认密码 | `admin123` |
| API 文档 | http://localhost:8000/docs（容器内） |

> 端口被占用时：`FRONTEND_PORT=9090 docker compose up -d`

### 监控本机数据库（Docker 环境）

后端运行在容器内时，`127.0.0.1` 指向容器自身，**无法连接宿主机数据库**。

| 字段 | 填写方式 |
|------|---------|
| 主机 | `host.docker.internal` |
| 端口 | 实际端口（如 3306） |
| 用户名/密码 | 数据库凭据 |

## 服务说明

| 服务 | 容器端口 | 说明 |
|------|---------|------|
| db-monitor-frontend | 8088→80 | Vue 3 前端 + Nginx 反向代理 |
| db-monitor-backend | 8000 | FastAPI 后端 |
| influxdb | 8086 | InfluxDB 2.x 时序数据库 |
| postgres | 5432 | 配置与元数据存储 |
| redis | 6379 | 缓存（预留） |

## 项目结构

```
database-monitor/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # REST API + WebSocket
│   │   ├── collectors/      # 数据库指标采集器
│   │   ├── services/        # 业务服务层
│   │   ├── models/          # SQLAlchemy ORM
│   │   └── utils/           # 加密、认证
│   └── tests/               # 单元测试
├── frontend/                # Vue 3 + TypeScript 前端
│   └── src/
│       ├── views/           # 页面（大屏、管理、详情、登录）
│       └── components/      # 图表与 UI 组件
├── docker-compose.yml       # 一键部署
├── nginx/                   # 外部 Nginx 配置（可选）
└── README.md
```

## 本地开发

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000（自动代理 API 到 8000）
```

### 运行测试

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

## API 文档

启动后端后访问 Swagger UI：`http://localhost:8000/docs`

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录获取 JWT |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/auth/users` | 创建用户（管理员） |

### 大屏数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/kpi` | KPI 卡片（含真实环比） |
| GET | `/api/dashboard/instances` | 实例列表（支持 status/group 筛选） |
| GET | `/api/dashboard/metrics/{id}` | 指标趋势（InfluxDB） |
| GET | `/api/dashboard/treemap` | 负载热力图 |
| GET | `/api/dashboard/alert-stats` | 告警统计（近 N 天） |
| GET | `/api/dashboard/history/{id}?at=` | 历史回放 |

### 实例管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/instances` | 实例列表 / 创建 |
| GET/PUT/DELETE | `/api/instances/{id}` | 实例 CRUD |
| GET/POST | `/api/instances/groups` | 分组管理 |
| POST | `/api/instances/test-connection` | 测试连接 |
| GET | `/api/instances/{id}/snapshot` | 完整监控快照 |
| GET | `/api/instances/{id}/slow-queries` | 慢查询记录 |

### 告警管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 告警列表 |
| POST | `/api/alerts/{id}/acknowledge` | 确认告警 |
| GET/POST | `/api/alerts/rules` | 告警规则 |
| PUT/DELETE/PATCH | `/api/alerts/rules/{id}` | 规则更新/删除/开关 |
| GET/POST | `/api/alerts/channels` | 通知渠道 |
| DELETE/PATCH | `/api/alerts/channels/{id}` | 渠道删除/开关 |

### 系统运维

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system/status` | 系统运行状态 |
| GET | `/api/system/collection-logs` | 采集日志 |
| POST | `/api/export/data` | 导出 CSV/JSON |
| GET | `/api/export/report/pdf` | 导出 PDF 报告 |

### WebSocket

| 路径 | 间隔 | 说明 |
|------|------|------|
| `/ws/metrics` | 5s | KPI + 实例 + 热力图实时推送 |
| `/ws/alerts` | 3s | 告警实时推送 |

## 配置说明

通过 `docker-compose.yml` 环境变量或 `.env` 文件配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FRONTEND_PORT` | 8088 | 前端映射端口 |
| `DATABASE_URL` | postgresql+asyncpg://... | 关系数据库连接 |
| `INFLUXDB_URL` | http://influxdb:8086 | InfluxDB 地址 |
| `INFLUXDB_TOKEN` | - | InfluxDB 访问令牌 |
| `COLLECTOR_INTERVAL_SECONDS` | 30 | 采集间隔（秒） |
| `DEFAULT_ADMIN_USERNAME` | admin | 默认管理员 |
| `DEFAULT_ADMIN_PASSWORD` | admin123 | 默认密码 |
| `ENCRYPTION_KEY` | - | 密码加密密钥（生产必改） |
| `SECRET_KEY` | - | JWT 签名密钥（生产必改） |
| `SEED_DEMO_DATA` | true | 是否自动注册演示实例 |
| `PROMETHEUS_URL` | - | Prometheus 地址（可选） |

复制 `.env.example` 为 `.env` 进行本地自定义。

## 使用指南

### 添加监控实例

1. 登录 → 右上角「管理」
2. 「数据库实例」→「添加实例」
3. 填写连接信息（Docker 环境主机填 `host.docker.internal`）
4. 保存后返回大屏查看数据

### 配置告警通知

1. 管理 →「通知渠道」→ 添加 Webhook 或邮件
2. 管理 →「告警规则」→ 添加自定义规则或启用内置规则
3. 触发告警后自动推送（10 分钟内去重）

### 历史回放

1. 大屏中间趋势图 → 点击「历史回放」
2. 选择时间点 → 加载该时段指标
3. 点击「返回实时」恢复当前数据

### 数据导出

1. 管理 →「数据导出」
2. 选择实例、指标、时间范围、格式（CSV/JSON）
3. 或点击「导出 PDF 报告」生成周报

## 内置告警规则

| 规则 | 条件 | 级别 |
|------|------|------|
| CPU 使用率警告 | CPU > 80% 持续 5 分钟 | 警告 |
| CPU 使用率紧急 | CPU > 95% 持续 2 分钟 | 紧急 |
| 连接数过高 | 连接数 > 最大连接数 80% | 警告 |
| 主从延迟过高 | 延迟 > 10 秒 | 警告 |
| 慢查询过多 | 慢查询 > 100/分钟 | 警告 |
| 连接失败 | 数据库不可达 | 紧急 |

## 常见问题

### Docker Hub 拉取镜像失败？

```bash
docker pull docker.m.daocloud.io/library/node:20-alpine
docker tag docker.m.daocloud.io/library/node:20-alpine node:20-alpine
# 同理拉取 nginx:alpine、python:3.11-slim
docker compose up -d --build
```

或在 Docker Desktop → Settings → Docker Engine 配置 registry mirror。

### 端口被占用？

```bash
FRONTEND_PORT=9090 docker compose up -d
```

### 实例状态 offline？

- Docker 环境确认主机填 `host.docker.internal`，不要用 `127.0.0.1`
- 使用管理页「测试连接」验证凭据
- 查看管理页「采集日志」排查错误

### 大屏显示「连接断开」？

检查 WebSocket 是否被代理阻断，确认 `db-monitor-backend` 容器正常运行。

### 如何修改采集频率？

设置环境变量 `COLLECTOR_INTERVAL_SECONDS=60` 后重启后端容器。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11、FastAPI、SQLAlchemy、Pydantic |
| 时序库 | InfluxDB 2.x |
| 配置库 | PostgreSQL / SQLite |
| 前端 | Vue 3、TypeScript、ECharts 5、Element Plus、Pinia |
| 部署 | Docker Compose、Nginx |
| 驱动 | aiomysql、asyncpg、redis、motor |

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)。当前版本 **2.0.0**。

## 许可证

MIT License
