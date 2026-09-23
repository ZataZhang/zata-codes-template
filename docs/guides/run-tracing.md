# Run 执行轨迹

模板内置一个**领域无关**的 Run 执行轨迹子系统：把一次 Run 的 canonical 事件投影成
管理端可读的诊断树，并可按需 best-effort 上报到外部 OTLP/HTTP Trace 接收端。它不内置
任何业务域或执行器——派生项目负责产生 Run 与事件，本子系统负责事件契约、安全校验、
只读诊断投影、Admin API 与可选导出。

## 设计原则

- **单一事实源**：诊断树不是第二套 trace 存储。它只读取已提交的 `(run_id, seq)` 事件，
  刷新浏览器或换后端实例都从数据库重建同一棵树。
- **不猜测父子关系**：只有来源显式写下可靠父级调用 ID 时才建立模型→工具的父子关系；
  缺少声明、指向未知节点或自引用一律降级到 Run 根节点，并给出稳定诊断 code。
- **默认低敏**：默认诊断只返回模型/工具名、轮次、usage 计数、耗时、状态、长度与 checksum；
  不新增持久化 prompt、隐藏推理、正文或工具原始参数/结果。原始内容只能经受审计的显式导出通道拿到。
- **诊断不阻断运行**：投影、未知事件或外部导出失败都不得回滚事件、改变 Run 终态。
- **默认关闭外部依赖**：未配置 Trace URL 时 exporter 完全不装配；OpenTelemetry SDK 是可选依赖。

## 分层落点

| 层 | 文件 | 职责 |
|---|---|---|
| Core | `src/backend/core/shared/models/run.py` | Run/Event 领域模型、确定性 trace/span ID 派生、投影类型 |
| Core | `src/backend/core/shared/models/run_policy.py` | 事件目录、状态机、敏感字段校验 |
| Core | `src/backend/core/shared/interfaces/run_repository.py` | Run/Event/lease 事务端口 |
| Core | `src/backend/core/shared/interfaces/run_trace_sink.py` | 已提交事件的外部投影出口端口 |
| Core | `src/backend/core/run_tracing/trace_use_cases.py` | 只读诊断投影与原始事件导出用例 |
| Infrastructure | `src/backend/infrastructure/persistence/models/run.py` | `run` / `run_event` / `run_export_audit` ORM |
| Infrastructure | `src/backend/infrastructure/persistence/repos/run_repo.py` | `SqlAlchemyRunRepository` |
| Infrastructure | `src/backend/infrastructure/observability/run_otlp_exporter.py` | 可选 OTLP 导出（懒加载） |
| API | `src/backend/api/admin/run_trace_router.py` | `/admin/run-traces` 列表、详情与原始导出 |
| Composition | `src/backend/composition/run_tracing_wiring.py` | 装配 repository、用例与可选 sink |

依赖方向保持 `api -> core -> infrastructure`，`composition` 在四层之外；Core 不导入 ORM
或 OpenTelemetry。

## 数据模型

| 表 | 说明 |
|---|---|
| `run` | Run projection：状态、`last_event_seq`、幂等键、lease、主体快照 |
| `run_event` | 仅追加的 canonical 事件，复合主键 `(run_id, seq)`，`ck_run_event_positive_seq` |
| `run_export_audit` | 原始事件下载审计（管理员、Run、事件数、字节数），不保存内容 |

`run_event.trace_id` / `span_id` 由稳定来源确定性派生，因此重启或 lease 恢复后仍得到同一棵树：

```python
from backend.core.shared.models.run import derive_trace_id, derive_root_span_id, derive_span_id

derive_trace_id("run_abc")                     # 32 位十六进制，非全零
derive_root_span_id("run_abc")                 # 16 位十六进制 Run 根 span
derive_span_id("run_abc", "model", "call_1")   # 按来源调用 ID 派生模型 span
```

派生算法带版本号；换算法时旧 Run 已提交的 ID 仍原样回读，不会被重新解释。

## 事件目录

事件类型与允许载荷字段冻结在 `run_policy.EVENT_PAYLOAD_KEYS`：

| 事件类型 | 必需载荷字段 |
|---|---|
| `run.created` | `subject_id`, `subject_snapshot_checksum` |
| `input.accepted` | `input_id`, `content`, `content_checksum`, `resources` |
| `run.started` | `started_at` |
| `message.started` / `message.delta` / `message.completed` | 文本流字段 |
| `model.call.started` | `model_call_id`, `model_name`, `turn_index` |
| `model.call.completed` | `model_call_id`, `model_name`, `turn_index`, `usage`, `finish_reason` |
| `model.call.failed` | `model_call_id`, `model_name`, `turn_index`, `error` |
| `tool.call.started` | `tool_call_id`, `tool_name`, `arguments`（可选 `parent_model_call_id`） |
| `tool.call.completed` | `tool_call_id`, `result`, `result_checksum` |
| `tool.call.failed` | `tool_call_id`, `error` |
| `artifact.created` | `type`, `artifact_id`, `filename`, `content_type`, `size`, `checksum`（可选 `sync_action`） |
| `run.cancelling` | `requested_by`, `requested_at` |
| `run.completed` / `run.failed` / `run.cancelled` / `run.interrupted` | `message_id` / `error` / `external_stop_confirmed` / `reason_code`, `lease_expired_at` |

`provenance` 只接受 `source_type` / `source_event_id`。任何字段名含 `api_key`、`authorization`、
`cookie`、`password`、`reasoning`、`secret`、`token` 的事件都会被拒绝（递归检查嵌套对象）。
状态机由 `decide_projection_transition` 独占裁决：终态 Run 不可再追加事件，非法迁移抛
`ValueError`，终态冲突抛可单独识别的 `TerminalRunAppendError`。

## 诊断 code

投影会把数据异常转成稳定 code，前端按 code 映射文案，未知 code 回退原样展示：

| code | 含义 |
|---|---|
| `parent_source_unavailable` | 来源未声明父级模型调用，工具挂到 Run 根 |
| `unknown_parent` | 声明的父级不存在，降级到 Run 根 |
| `self_parent` | 节点声明自身为父级，降级到 Run 根 |
| `cyclic_parent` | 父子关系成环，环内节点降级到 Run 根 |
| `started_without_completion` | Run 已终结但节点未收到完成事件，标记 incomplete |
| `completion_without_start` | 只收到完成事件，没有开始事件 |
| `duplicate_completion` | 同一节点多次终态，保留首次结果 |
| `missing_span_id` | 事件未带 span ID，按来源调用 ID 派生并标记 |
| `no_tracing_events` | 该 Run 没有模型/工具事件，`visibility` 为 `limited` |

## Admin API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/admin/run-traces` | 分页列表；`run_id` / `subject_id` / `status` / `created_after` / `created_before` / `page` / `page_size` |
| `GET` | `/admin/run-traces/{run_id}` | 单个 Run 的 `summary`、`root_span_id`、`spans`、`tree`、`diagnostics`、`content_policy` |
| `GET` | `/admin/run-traces/{run_id}/export` | 下载已终结 Run 的完整原始事件 JSON（`409` 未终结 / 事件不完整，`413` 超上限） |

所有端点经 `get_current_admin_user` 守卫；跨 owner 回看是管理诊断的既定能力，授权判断留在
API 层的 admin 认证依赖上。原始导出会写入 `run_export_audit`（不记录内容），并带
`Cache-Control: no-store` 等响应头。

管理端页面位于 `frontend-admin` 的「执行轨迹」（路由 `/run-tracing`），只调用上述 admin API，
不读取进程内状态，刷新后从数据库重新投影。

## 可选 OTLP 导出

```bash
uv sync --extra tracing                                   # 安装可选的 OpenTelemetry 依赖
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://.../traces   # 完整 Trace URL，原样使用
```

- 只消费已提交事件的 trace/span ID，云端父子关系与本地诊断树逐节点一致。
- 通用基础地址 `OTEL_EXPORTER_OTLP_ENDPOINT` 仅在 traces 专用变量未设置时生效，
  已以 `/traces` 结尾则原样使用，否则补 `/v1/traces`。
- 未安装 SDK 或未配置 endpoint 时降级为不装配，本地诊断完全可用。
- 导出的自定义 attribute 用 `run.*` 前缀（`run.id` / `run.status` / `run.subject.id` /
  `run.model.*` / `run.tool.parent_source` / `run.error.code`），并保留标准 `gen_ai.*` 语义属性
  与 `run` / `gen_ai.chat` / `execute_tool` span 名。

## 接入方式

模板**不内置执行器**：`create_run` / `append_event` 没有生产调用方，所以 Admin 页默认是空的。
派生项目在自己的执行器里：

1. 构造 `Run`（含 `RunSubjectSnapshot`）并经 `RunRepository.create_run` 落库；
2. 在真实模型/工具边界调用 `append_event`，带上 `model_call_id` / `tool_call_id` 与可选的
   `parent_model_call_id`，以及同一 trace 下的正确 span ID；
3. 若需要外部导出，把已提交事件交给 `TraceSink.record_committed_event`（best-effort）。

`composition.build_run_tracing_components` 已经把 `run_repository`、`run_trace_use_case` 与可选的
`trace_sink` 组装好，可直接复用。

## 已知限制

- 模板无执行器，Admin 视图的空态是预期行为；测试直接经 `SqlAlchemyRunRepository` 播种。
- `RunOtlpExporter.shutdown()` 未接入 FastAPI lifespan 生命周期，批次冲刷依赖进程退出时的
  best-effort flush；需要确定性冲刷的派生项目应在自己的 lifespan 里显式调用。
- 单文件非空行上限由 `just lint` 的 max-file-lines 守卫约束。

## 相关文档

- [可观测性](observability.md) — 日志、指标与 OTLP 导出配置
- [配置说明](configuration.md) — `[observability]` 与 `.env` 约定
- [交互原型](../prototypes/run-tracing.md) — 目标界面的可点击原型（design intent，非验收证据）
