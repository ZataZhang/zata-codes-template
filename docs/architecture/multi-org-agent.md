# 多组织 Agent 底座

本页记录在线 Agent、Skill 版本与 A2A 的服务端契约。组织表、成员归属和两级管理员由组织管理模块提供；Agent 能力复用该会话与角色模型，不新增第二套认证或 Run 存储。

## 组织范围

- 后端从 `session_id` 或 `admin_session_id` 解析主体与当前组织。请求体中的 `organization_id` 不参与授权。
- Agent、Skill、A2A 凭据、A2A 对端在创建时写入组织 ID。Run 同时保存创建组织、owner、Agent 快照、Skill 版本快照与会话 ID。
- 成员读取 Run 要同时匹配 owner 和 Run 的组织；组织管理员按创建组织读取。成员调组织后不能读取旧组织的数据，也不能向旧会话追加 Run。
- 平台管理员能治理组织与管理员，但不会因平台角色自动获得 Agent、Skill 或组织 Run 的读取权；组织 Run 的低敏轨迹只由当前组织管理员通过 `/admin/agent-runs` 读取。
- `RunEvent` 通过 Run 外键继承组织范围。运行轨迹只输出低敏字段；原始消息和模型结果不会放进管理轨迹响应。

## Agent 与 Canonical Run

组织管理员通过管理端 `/api/admin/agents` 创建、更新和发布 Agent。普通成员通过 `/api/agents` 查看本组织已发布 Agent，并使用 `/api/agent-runs` 创建、读取、取消与查看事件。浏览器 API 基址包含一次 `/api`，后端路由本身不带 `/api` 前缀。

Run 创建事务写入唯一 Canonical `Run` 和初始 `RunEvent`。执行器使用行锁租约领取队列，定时续租；失去租约的非终态 Run 记录 `run.interrupted`，不被第二个执行器自动重跑。模型、Skill 内容与版本号在创建时冻结，后续目录变更不会改写旧运行。成员可通过 `/api/agent-runs/{run_id}` 在新请求中读取冻结的 Skill 版本；`/api/agent-runs/{run_id}/assets` 从同一事件链投影输入资源与产物元数据，不新增第二套资产状态库。

模型通过 `load_primary_model_settings()` 读取 OpenAI-compatible 端点三件套。缺配置时健康检查和管理页面仍可用，Agent 会显示不可运行原因，Run API 返回冲突，不触发宿主命令或用户代码执行。

### 增量回复

执行器以 `stream: true` 请求端点，边读取 SSE 分片边把文本交给 Run 用例；片段按小批次写入同一条 Canonical `message.delta` 事件链，不另建流式缓存或第二套消息存储。若模型在已批准工具调用前先输出可见文本，它会按顺序与最终回复合并，确保增量内容和 `message.completed` 一致。端点忽略 `stream` 时，执行器把完整回复作为同一事件链的增量补写，前端只有一条展示路径。

成员页面打开 `GET /api/agent-runs/{run_id}/events/stream?after_seq=` 建立同源 SSE 流。公开前端由专用 Route Handler 直通转发响应体，避免通用 Next rewrite 缓冲事件；`message.delta` 到达后立即拼接到正在增长的回复，`run.started` / `run.cancelling` 更新展示状态，流关闭后重新读取持久化 Run 并刷新历史。断线后按最后处理的事件序号重连；服务端每秒校验当前会话、owner 与组织范围，Run 终止或授权失效时关闭流。运行中可从前台取消当前 Run；请求先持久化为 `cancelling`，持有执行租约的实例观察到后停止本地执行并追加 `cancelled`，未被认领的排队 Run 可立即结束。其他实例不会仅因收到了取消请求就确认远端执行已停止。Admin 和 Public 入口限流都按 HTTP 请求计数，活动 SSE 流各占一个并发请求额度；服务端每秒读取事件一次。同一时刻只允许一个流消费当前 Run，迟到的持久化详情不能让终态回退为活动状态。`run.completed` / `run.failed` / `run.cancelled` / `run.interrupted` 都作为终态处理。管理轨迹与 A2A 入站复用同一条事件链：诊断投影把 `message.delta` 归入 Run 根节点，不向管理员泄露消息正文；A2A 流式响应把每个增量映射为 `artifactUpdate` 追加片段，并在完成或中断时发送终态 `statusUpdate`。

## Skill 版本

Skill 正文只通过一个版本写入用例追加。每次更新递增版本号；恢复旧版会把旧正文作为新版本追加。SkillVersion 行为不可变，比较接口只读取两个版本。运行只引用创建时选择的版本 ID，并在 Run 快照中留存版本号、正文和摘要。创建、追加和恢复都接受 `Idempotency-Key`，数据库约束收敛并发重试，同键不同请求会被拒绝。

当前输入仅接受声明式文本，拒绝 shebang、脚本或未知语言代码围栏、未闭合代码围栏、常见未围栏 Python/JavaScript 代码行、Shell 命令和含二进制控制字符的内容。恢复历史版本也重新校验正文；代码围栏只允许 text/Markdown 与 JSON、YAML、TOML、CSV、diff、Mermaid 等声明式参考格式。模板在线入口不挂载沙箱命令 API，也不接受可执行脚本或代码包。

## A2A 1.0 HTTP+JSON/REST

A2A 只用于独立 Agent 之间通信。它不代替内部模型接口或受控工具。实现按 [A2A 1.0.0 规范](https://a2a-protocol.org/v1.0.0/specification/) 使用 `ROLE_USER` / `ROLE_AGENT`、`TASK_STATE_*`、文本 Part 和 `task` / `statusUpdate` / `artifactUpdate` StreamResponse。

### 入站

每个发布 Agent 的卡片地址为 `GET /a2a/agents/{agent_id}`。卡片和任务入口要求绑定该 Agent 的 Bearer 服务凭据；数据库只保存 token 摘要。凭据撤销、Agent 撤下或组织不匹配时，服务以不可见响应拒绝访问。

| 方法 | 后端路径 | 用途 |
|---|---|---|
| GET | `/a2a/agents/{agent_id}` | 返回受权 Agent Card |
| POST | `/a2a/agents/{agent_id}/message:send` | 创建任务并按 `returnImmediately` 返回 |
| POST | `/a2a/agents/{agent_id}/message:stream` | 创建任务并流式读取 Canonical Run/Event |
| GET | `/a2a/agents/{agent_id}/tasks` | 按凭据列出任务，支持状态与分页过滤 |
| GET | `/a2a/agents/{agent_id}/tasks/{task_id}` | 读取 Task、Artifact 与可选历史 |
| POST | `/a2a/agents/{agent_id}/tasks/{task_id}:subscribe` | 订阅非终态 Run 事件 |
| POST | `/a2a/agents/{agent_id}/tasks/{task_id}:cancel` | 取消同凭据可见的任务 |

入站 Task ID 就是 Canonical Run ID。`messageId` 形成组织和凭据范围的稳定幂等键；重复发送相同请求返回已有 Run，不另建状态库。任务列表、读取、取消与订阅都按组织、Agent 和服务凭据 owner 过滤。

### 出站

组织管理员登记 A2A 对端，平台管理员审查并批准地址策略后，组织管理员还需在创建 Agent 时选择它允许调用的已批准对端；Run 创建时冻结这份对端 ID 清单。登记时拒绝 URL 内嵌凭据、查询参数和跨源 Card/REST 地址，防止审批接口把凭据回显到浏览器；出站调用前会对已有记录再次执行同一校验。执行开始时，允许列表与当前 Agent 绑定和对端启用/审批状态取交集，排队 Run 不会继承创建后新增的授权；A2A 客户端发请求前还会再次校验对端状态。空绑定表示该 Agent 不允许出站 A2A 调用。调用方不能在用户消息中提供 URL。目录按组织保存 Card URL、REST URL 与密钥别名；Bearer token 使用服务端 AES-GCM 密钥加密，密钥只从 `.env` / `.env.local` 注入。

客户端验证 A2A 版本、HTTP+JSON REST binding、Card 与 endpoint 同源、精确主机 allowlist、DNS 公网地址和无重定向策略。凭据只发送到登记对端，不转发到 Card 宣告的其他 host。出站调用开始、成功或失败时立即写入 Canonical Run 工具事件；成功事件包含远端 Task ID、peer ID、结果 checksum 与字符长度。这样后续模型调用失败时，已完成的远端 Task 仍留在父 Run 轨迹中；事件不保存远端消息正文或凭据。

卡片 origin 必须由部署配置 `A2A_PUBLIC_BASE_URL` 明确声明。该值只允许一个 `http(s)` origin，不读取未验证的请求 `Host`。生产应使用 HTTPS 公网域名；本地 HTTP 仅在显式打开 `A2A_ALLOW_LOOPBACK_FOR_DEV=true` 时可用。

## 前端与部署代理

成员前台使用 Next.js 现有应用壳呈现 Agent 目录、会话与历史；管理端使用 TanStack Router 呈现 Agent、Skill、A2A 对端与组织运行轨迹。浏览器通过同源 `/api/*` 访问普通 API。独立 A2A 服务端路径 `/a2a/*` 由前端容器直接转发到后端，避免 `/api/api/*`，也不将外部 Agent Card 塞进浏览器。

生产部署继续是后端、Admin、Public 三服务。模型 Key 留在后端环境中；不得序列化进管理/成员 API、Next 静态资源或 Vite 构建包。

## 数据迁移

迁移通过 `just new-migration <slug>` 生成。现有 Run 回填到默认组织，既有事件和 owner 关系保留。无法归属的业务数据按不可见方式保留，不在迁移时删除。PostgreSQL 与 MySQL 都需验证升级、历史数据计数、Run/Event 关联和可支持的降级。
