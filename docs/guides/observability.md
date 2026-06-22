# 可观测性

本后端模板通过行业标准格式输出遥测数据，可与任意监控平台对接。模板自带一个可选的**本地可观测性栈**（Vector + Loki + Prometheus + Grafana），每个从模板复制出去的项目都能独立运行、独立查看日志和指标，无需依赖 `zata-ops`。

`zata-ops` 则作为可选的**中央可观测性 hub**：当项目数量变多或需要跨机器部署时，把每个项目的 Vector/Prometheus 指向 `zata-ops` 的 central Loki / Mimir 即可聚合所有数据。

## 设计原则

- **项目自包含**：每个项目自带本地 Vector + Loki + Prometheus + Grafana，不依赖 `zata-ops` 也能观测自己。
- **平台无关**：只输出 JSON 日志和 Prometheus `/metrics`，不绑定具体厂商。
- **可开关**：通过 `config.toml` 的 `[observability]` section 可以彻底关闭、部分关闭或覆盖所有行为。
- **约定对接**：业务代码只负责产生遥测数据；采集、存储、展示通过 overlay compose 文件按需启用。
- **平滑升级**：本地模式和中央模式只通过环境变量切换，无需改动业务代码。

## 产生的遥测信号

### 1. JSON 结构化日志

容器运行时输出到 stdout，字段包括：

```json
{
  "timestamp": "2026-06-18T17:30:14+08:00",
  "level": "INFO",
  "logger": "app",
  "message": "用户登录成功",
  "service_name": "zata-codes-template-backend",
  "service_version": "0.1.0",
  "deployment_environment": "production",
  "request_id": "abc123def4567890",
  "source_file": "auth_router.py",
  "source_line": 37
}
```

`request_id` 会自动注入到同一次请求的所有日志中。

### 2. RED 指标

`/metrics` 端点暴露：

- `http_requests_total{method,status,path}`
- `http_request_duration_seconds{method,status,path}`

`path` 使用 FastAPI 路由模板（如 `/items/{item_id}`），避免 Prometheus cardinality 爆炸。

### 3. 请求标识

每个 HTTP 请求都会生成 `X-Request-ID`：

- 可从请求头传入，后端会透传。
- 否则后端自动生成一个 16 字符 hex ID。
- 在响应头中返回。

### 4. 健康探针

- `GET /health` —— liveness
- `GET /ready` —— readiness（当前为基础实现，可扩展数据库检查）
- `GET /live` —— liveness 别名

## 配置

所有配置默认写在 `config.toml` 的 `[observability]` section：

```toml
[observability]
enabled = true
metrics_enabled = true
request_id_enabled = true
log_format = "text"
service_name = "zata-codes-template-backend"
service_version = "0.1.0"
deployment_environment = "development"
```

默认值统一维护在 `config.toml` 的 `[observability]` section。如需在特定环境临时覆盖，可通过环境变量传入：

```env
OBSERVABILITY_LOG_FORMAT=json
OBSERVABILITY_DEPLOYMENT_ENVIRONMENT=staging
```

配置优先级遵循仓库统一约定：env > `.env`/`.env.local` > `config.toml` > 代码默认值。
非密钥可观测性配置不再写入 `.env.example`，避免与 `config.toml` 重复维护。

## 本地验证

### 查看日志格式

```bash
# text 模式（默认）
uv run python -m backend.main

# json 模式
OBSERVABILITY_LOG_FORMAT=json uv run python -m backend.main
```

访问 `http://localhost:8000/health` 后在终端观察日志输出。

### 查看指标

```bash
curl http://localhost:8000/metrics
```

### 查看 request_id

```bash
curl -v http://localhost:8000/health
# 响应头包含 X-Request-ID
```

## 关闭监控

在 `config.toml` 中：

```toml
[observability]
enabled = false
```

关闭后：

- 不注册 `request_id` middleware。
- 不注册 metrics middleware。
- 不暴露 `/metrics` 路由。
- `/health`、`/ready`、`/live` 仍然可用。

也可以单独关闭：

```toml
[observability]
enabled = true
metrics_enabled = false
request_id_enabled = true
```

## 本地可观测性栈（自包含模式）

使用 `docker-compose.monitoring.yml` 启动一个完整的本地监控栈：

```bash
# 直接启动业务服务 + 监控栈
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d --build
```

启动的服务：

| 服务 | 容器名 | 端口 | 说明 |
|---|---|---|---|
| backend | `zata-codes-template-backend` | 8000 | 业务后端，自动输出 JSON 日志 |
| Vector | `zata-codes-template-vector` | - | 采集本项目的 Docker 日志 |
| Loki | `zata-codes-template-loki` | 3100 | 本地日志存储 |
| Prometheus | `zata-codes-template-prometheus` | 9090 | 抓取本地 `/metrics` |
| Grafana | `zata-codes-template-grafana` | 3000 | 本地面板（默认 admin/admin） |

### 可选环境变量

在启动命令前设置，或写入 `.env.monitoring`（gitignored）：

```env
COMPOSE_PROJECT_NAME=zata-codes-template
OBSERVABILITY_SERVICE_NAME=zata-codes-template-backend
OBSERVABILITY_SERVICE_VERSION=0.1.0
OBSERVABILITY_DEPLOYMENT_ENVIRONMENT=development
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
GRAFANA_ROOT_URL=http://localhost:3000
```

### 产生流量并验证

```bash
for i in {1..10}; do
  curl -s http://localhost:8000/health >/dev/null
  curl -s -X POST http://localhost:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"identifier":"admin","password":"wrong"}' >/dev/null
done
```

打开 Grafana：`http://localhost:3000`

- Explore → Loki：`{compose_service="zata-codes-template-backend"}`
- Explore → Prometheus：`http_requests_total`
- Dashboards → RED + Logs

## 中央模式（接入 zata-ops）

当项目数量变多或需要跨机器部署时，把每个项目采集到的数据转发到 `zata-ops` 的中央监控栈。

### 日志中央化

修改每个项目的环境变量，让 Vector 把日志写到 central Loki：

```env
LOKI_ENDPOINT=http://zata-ops-loki.example.com:3100
```

然后重启 Vector：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d observability-vector
```

### 指标中央化

编辑 `observability/prometheus/prometheus.yml`，取消 `remote_write` 注释并配置 central endpoint：

```yaml
remote_write:
  - url: "http://zata-ops-mimir.example.com:9090/api/v1/push"
```

然后重启 Prometheus：

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d observability-prometheus
```

### 推荐的多机架构

```text
┌─────────────────────────────────────────┐
│              zata-ops Central           │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  Loki   │ │  Mimir  │ │  Grafana  │ │
│  └────▲────┘ └────▲────┘ └─────┬─────┘ │
└───────┼───────────┼────────────┼───────┘
        │ push      │ remote_write│ query
┌───────┼───────────┼────────────┼───────┐
│       │           │            │       │
│  ┌────┴────┐ ┌────┴────┐       │       │
│  │ Vector  │ │Prometheus│       │       │
│  │ (agent) │ │ (agent)  │       │       │
│  └────┬────┘ └────┬────┘       │       ││       │           │            │       │
│   Docker containers (project)  │       │
└────────────────────────────────┘       │
              Project Host 1 ────────────┘

┌─────────────────────────────────────────┐
│  ┌────┐ ┌──────────┐                   │
│  │Vector│ │Prometheus│                   │
│  └────┘ └──────────┘                   │
│   Docker containers (project)          │
└─────────────────────────────────────────┘
              Project Host 2
```

每台被监控机器只需要部署项目自身的 compose 栈（包含 Vector + Prometheus agent），数据统一汇聚到 `zata-ops` 的 central Loki / Mimir，Grafana 从 central 查询所有项目。

## 与 zata-ops 监控栈的关系

| 能力 | 本仓库 | zata-ops |
|---|---|---|
| 产生 JSON 日志 | ✅ `logger.py` | - |
| 产生 RED 指标 | ✅ `/metrics` | - |
| 本地日志/指标查看 | ✅ Vector + Loki + Prometheus + Grafana | - |
| 跨项目/跨机器聚合 | 通过 remote_write / sink 指向 | ✅ central Loki / Mimir / Grafana |
| 生产级高可用 | - | ✅ cluster / object storage |

本仓库的监控栈面向**本地开发和单项目自包含运行**；`zata-ops` 面向**多项目 central hub 和高可用生产部署**。
