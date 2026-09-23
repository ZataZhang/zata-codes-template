# 沙箱执行后端

沙箱执行后端提供**按会话隔离的命令执行与文件读写环境**，是 `SandboxProvider` 端口的
若干实现。它把"命令在哪台机器、以什么权限执行"从"宿主进程权限"收敛到"无凭据、非
root、按域名放行出站的独立容器或远端沙箱"。

模板只提供**执行底座**：端口契约、三档后端实现、配置加载、装配入口与部署资产。谁
来消费它（Agent 执行器、资源暂存、产物发布）由派生项目自行装配——模板刻意不内置
执行器，也不内置 LLM 客户端。

## 为什么需要它

如果业务代码在宿主进程里执行模型生成的命令，那么命令白名单只是入口清单，不是安全
边界：任何已认证用户上传的文件若含提示注入，都可能让模型以运行后端服务的进程权限
执行任意代码。沙箱后端把这个边界从"宿主进程权限"换成"隔离环境权限"。

**定位说明：** 容器与宿主共享内核，适合内部可信业务，**不是不可信多租户场景的最终
隔离边界**。需要对抗性隔离时，通过新增 `SandboxProvider` 实现接入 microVM 级方案，
不需改动消费侧代码。

## 配置

整段可选。**未配置 `[sandbox_agent]` 段时沙箱后端不注册**：`build_sandbox_provider()`
返回 `None`，调用方在装配期即拿到明确结果，而不是运行到一半才失败。

### 后端三档

| provider | 行为 | 适用 |
|---|---|---|
| `filesystem` | 只提供隔离的会话目录，**不执行命令**（`execute` 直接拒绝，不静默回落到宿主执行） | 纯文件任务；本地开发 |
| `docker` | 每会话一个受限容器 | 需要命令执行能力、且宿主有 Docker daemon |
| `e2b` | 每会话一个阿里云函数计算「云沙箱」 | 后端主机没有 Docker daemon；执行面需要弹性 |

Docker 档的隔离参数是安全边界，不是可调项：不注入宿主环境变量（模型 API 密钥就在
其中）、不挂载宿主目录与 Docker socket、以 uid 65534 运行、`cap_drop=ALL`、
`no-new-privileges`、限制内存 CPU 与进程数、命令用 `timeout` 在容器内包裹。

会话到容器的映射用容器标签查询恢复，不建数据库表——Docker 本身已经是这个状态的
真源，进程重启后也能凭标签找回容器。

### 云沙箱档

云沙箱是**同一个 `SandboxProvider` 端口的第三个实现**，不是新的来源；消费侧代码
不变，差异只在"命令与文件落到哪台机器上"。

```toml
[sandbox_agent]
provider = "e2b"
command_timeout_seconds = 120

[sandbox_agent.e2b]
api_url = "https://api.cn-beijing.e2b.fc.aliyuncs.com"
api_key_env = "E2B_API_KEY"     # 只写变量名；密钥值在 .env/.env.local
template_id = "zata-sandbox"    # 必须是平台自建模板的别名
timeout_seconds = 900           # 沙箱存活窗口
username = "user"               # 执行通道文件读写使用的沙箱用户
allow_internet_access = false   # 默认断网；仅本地排障可临时打开
```

装配是**失败闭合**的：`[sandbox_agent.e2b]` 缺段或缺 `api_url`/`template_id` 会在
启动期直接失败；凭据环境变量为空、或控制面不可达时该后端不注册（打印告警），**不存在
任何宿主执行回落路径**。

**出网姿态**：云沙箱没有按域名放行的代理通道，只有"断网"与"直连"两档，
`allow_internet_access` 直接映射到出站策略的 `none` / `open`。生产必须保持 `false`
——与本地 Docker 侧的断网姿态对齐。

**生命周期**：本函数当前**未开通暂停白名单**（官方文档把 `sandbox.pause()` 列为"需先
开通白名单"的兼容能力），实测 `/pause` 返回 400，因此 `release` 的语义是**续期保活**
而不是停机：会话文件系统保留到存活窗口耗尽，期间再次运行会复用同一个沙箱；沙箱已被
回收时后端丢弃本地映射并在下次运行时重建。会话到沙箱的映射只存在于后端进程内，不
落库——后端进程重启后旧沙箱会随存活窗口自然过期，期间可由云侧控制台或
`GET /sandboxes` 观测并按运维动作回收。

注意 `GET /sandboxes` 返回**裸数组**且有约 2 秒最终一致延迟：它适合做"有没有长期遗留"
的巡检，不适合做"这一步是否已经生效"的即时断言。按单个沙箱查存活用
`GET /sandboxes/{id}`（官方 `Sandbox.getInfo`）——实测销毁后它**立刻** 404，是权威判据。

**沙箱身份校验（不要删）**：实测沙箱被销毁后 envd 网关**不会让请求失败**，而是以
HTTP 200 返回**另一个干净环境**的执行结果（退出码 0、`/health` 也回 200，只是文件
系统是空的）。若把它当成本会话的沙箱，产物导出会在空环境上列出零个文件，最终以
"无产物但成功"收尾。因此每次取得会话时会在沙箱 `/tmp` 下写入一枚随机身份标记，每条
命令执行前先自校验该标记，标记缺失即抛"沙箱已被回收"，由调用方按"沙箱已丢失"处理。
`/health` 因此**不是**存活判据，别用它做健康探测。

#### 构建执行模板

执行镜像必须是**平台自建模板**：公开模板缺平台约定的工作目录与固定依赖，且不受平台
控制，不用于执行用户任务。

```bash
deploy/sandbox/build_e2b_template.sh              # 名称前缀取 config.toml 的 template_id
deploy/sandbox/build_e2b_template.sh <名称前缀>    # 或显式指定
```

脚本读取 `.env` / `.env.local` 中的 `E2B_*` 配置，先用 Docker Buildx 构建并推送
`linux/amd64` OCI 镜像，再通过固定版本的官方 `e2b` SDK 从该镜像发布模板，最后创建
一个断网临时沙箱做 smoke test。镜像显式关闭 provenance 与 SBOM，避免 ACR manifest
列表中的 `unknown/unknown` 附加项被 FC 判为无效镜像。`E2B_TEMPLATE_IMAGE` 必须带唯一
tag；仓库、FC Sandbox API key 和 endpoint 必须属于同一账号、同一地域。每次发布都会
在名称后添加时间戳，因为 FC 的每个 template 只允许一次 build；成功后脚本会输出不可变
的 `templateID`，把它填回 `config.toml` 的 `template_id` 后再切换后端。

生产支持路径是同 UID、同地域并绑定 VPC 的 ACR 企业版；同账号同地域的 ACR 个人版当前
也已实测可用，但不作为生产稳定性承诺。模板固化 Node.js 22 以及 openpyxl、pandas、
NumPy、SciPy。Node 基础镜像已占用 uid 1000，因此 envd 注入的 `user` 使用 uid 1001，
工作目录在构建期显式归该用户。官方 SDK 只由脚本通过 `uv run --with e2b==2.32.0` 临时
使用，不进入应用运行时依赖；应用侧使用本仓维护的协议实现（仅依赖 `httpx`）。

**模板未发布时该后端不可用**——`is_available()` 只探测控制面，模板是否存在要到创建
沙箱时才暴露（控制面会以 `template is CREATE_FAILED` 拒绝），表现为运行失败而不是
"没有产物但成功"。

### 出站网络三档

真实需求是"访问某几个服务"，所以既不是开关也不是全开：

| mode | 行为 |
|---|---|
| `none` | 完全断网。适合纯计算任务 |
| `allowlist`（默认） | 容器接入 internal 网络，只能经出站代理访问放行域名，清单外一律拒绝，每次出站记日志 |
| `open` | 直连外网。**仅限本地开发** |

放行清单为空时**拒绝以 `allowlist` 档启动**——避免"以为放行了其实全断"的静默故障。

配置示例见 `config.toml` 中被注释的 `[sandbox_agent]` 段。

### 包索引与供应链

放行清单默认含清华 PyPI 镜像。选它有个操作上的好处：**索引与包文件同域**，放行一项
即可；改用官方源需同时放行 `pypi.org` 与 `files.pythonhosted.org`，放行面反而更大。

沙箱镜像必须把 index-url 固化（`deploy/sandbox/Dockerfile.sandbox` 写入
`/etc/pip.conf`）。否则 `pip` 会先去未放行的官方源，请求被代理拒绝后安装直接失败。

**残留风险：** 清华镜像是公共源的完整镜像，放行它等于允许安装其上任意包。三层缓解：

1. 常用库预装进镜像，让运行时安装成为少数路径；
2. 安装出的包只存在于无凭据、无宿主目录、非 root 的容器内，够不到平台密钥与数据库；
3. 镜像内记录基线包清单（`/assets/baseline-packages.txt`），业务侧可在运行结束比对容器
   内已安装包与基线，新增包随运行留存。

### 审计粒度

出站流量加密，代理只能记录目标域名，**无法识别具体包名或请求路径**。包级审计需在
执行侧另做安装差异记录；非包索引类出站只有域名级记录。

要做到请求级审计需引入 TLS 拦截，那需要往沙箱植入信任证书，引入新的信任面与隐私
问题，本实现不采用。

## 装配接入

`build_sandbox_provider()` 按配置构造后端，供消费侧调用：

```python
from backend.composition.sandbox_wiring import build_sandbox_provider

sandbox_provider = build_sandbox_provider()   # 未配置或后端不可用时为 None
if sandbox_provider is not None:
    sandbox_session = sandbox_provider.acquire(thread_id)
    execution = sandbox_session.execute("echo hi", timeout_seconds=30)
```

未配置 `[sandbox_agent]` 段时返回 `None`；Docker daemon 不可达、云沙箱凭据缺失或控制面
不可达时同样返回 `None` 并打印告警——**不会**回落到宿主执行。

Docker 档需要安装可选 extra：

```bash
uv sync --extra sandbox-docker
```

### 最小可跑消费示例

`scripts/dev/sandbox_smoke.py` 是本端口的可执行消费示例，走的是真实装配路径
（`build_sandbox_provider()` → `acquire` → `execute` → 文件写入/枚举/读回 → `destroy`），
不是另一条旁路：

```bash
just sandbox-smoke
```

三档后端都适用。`filesystem` 档会在"执行命令"这一步拿到契约性的拒绝结果（该档不提供
命令执行能力，也不回落到宿主执行），脚本把该拒绝视为正确结果而不是失败；文件往返照常
完成。结束时会销毁会话环境，不留容器或云沙箱。

未配置 `[sandbox_agent]` 段时脚本以非零退出码结束并打印启用步骤——"没有沙箱可测"不应该
看起来像"测过了且通过"。

## 部署接入

Docker 档要求 backend 进程能访问 Docker daemon；**云沙箱档不需要**——执行面在云端，
后端主机既不需要 docker daemon，也不需要本地执行镜像与出网代理。

**明确排除：给 backend 容器挂载 `/var/run/docker.sock`。** 该 socket 是未认证的 root
等价接口，任何能读写它的进程都能挂载宿主目录、改网络配置——挂给一个自主运行的执行
宿主等于抹掉容器边界。Docker 官方与业界实践一致反对这种做法。

两个候选方案：

| 方案 | 做法 | 代价 |
|---|---|---|
| backend 移出容器 | 编排只跑 DB 与 nginx，backend 以低权限用户直连宿主 daemon。被隔离的是沙箱容器，不是 backend | 改变部署形态 |
| 宿主安装 Sysbox | backend 容器使用 `sysbox-runc` 运行时，容器内可运行 Docker，无需 privileged 也无需挂 socket | 宿主需安装 Sysbox |

未选定前保持 `filesystem` 档。

### 构建镜像与启动代理

```bash
docker build -f deploy/sandbox/Dockerfile.sandbox -t zata-sandbox:latest .
```

```bash
docker compose -f docker-compose.yml -f deploy/sandbox/docker-compose.sandbox.yml up -d
```

`deploy/sandbox/docker-compose.sandbox.yml` 是可选编排片段，默认部署不引入它，服务
拓扑与端口映射保持不变。

后端直接跑在宿主、不启动应用 compose 时，可改用 `zata-ops` 测试中间件里的同名出站代理
（`just testing up sandbox-egress-proxy`）：容器名与网络名与本 overlay 一致，`config.toml`
无需区分两种来源。两边二选一，不要同时启动（同名网络会冲突）。

出站代理仅在启用 Docker 档时需要；它不承载业务逻辑，但位于安全路径上——代理失效会让
沙箱完全无法出站（失败方向安全），配置错误则可能放行过宽。放行清单（`squid.conf` 与
`config.toml` 的 `allowed_domains`）应纳入变更审查。

## 运维排查

| 现象 | 首先检查 |
|---|---|
| 调用 `build_sandbox_provider()` 得到 `None` | `config.toml` 是否有 `[sandbox_agent]` 段；Docker daemon 是否可达；启动日志中的 `sandbox runtime 未注册` 警告 |
| 云沙箱档不注册 | `provider` 是否为 `e2b` 且 `[sandbox_agent.e2b]` 段完整；`api_key_env` 指向的环境变量是否已注入；控制面是否可达 |
| 云沙箱运行报 `template is CREATE_FAILED` | `template_id` 指向的平台模板是否已构建完成：跑 `deploy/sandbox/build_e2b_template.sh` 看构建结论 |
| 模板构建报 `invalid image format`（构建日志为空） | 不要把 Dockerfile 文本直接 POST 到 `/templates`；运行仓库脚本，经 `Template.from_image()` 提交已推送的 OCI 镜像。确认镜像是 `linux/amd64`、关闭 provenance/SBOM，且 ACR、API key 与 endpoint 同账号同地域 |
| 模板构建报 401 / `user jurisdiction error` / `no such host` | 依次检查 API key 是否属于 endpoint 地域、ACR 与 FC 是否属于同一账号、该 FC 地域是否受支持；跨账号或跨地域不能靠更换镜像 tag 修复 |
| 模板内 `python` / `python3` 找不到已安装依赖 | envd 使用 login shell，不能只依赖 Dockerfile 的 `ENV PATH`；模板须保留 `/usr/local/bin/python`、`python3` 与 `pip3` 包装入口 |
| 云沙箱运行报"工作区初始化失败" | 执行模板是否在构建期建好 `/workspace/inputs`、`/workspace/outputs` 并归属 envd 的 `user`（本镜像为 uid 1001）；运行时不会替你 chown |
| 云沙箱内命令报沙箱不存在(404) | 沙箱已过期或被回收；后端会在下次运行时重建，本次运行以失败收尾 |
| 运行报"云沙箱身份校验失败" | 这不是配置问题：沙箱被回收后网关转到了另一个环境，后端已按"沙箱丢失"处理。检查是否跨越了存活窗口（`timeout_seconds`），或后端进程是否重启过 |
| 云端留下未销毁的沙箱 | 后端进程重启会丢失"会话 → 沙箱"映射，旧沙箱随存活窗口自动过期；期间可在云侧控制台或 `GET /sandboxes` 观测并按运维动作回收 |
| 沙箱内命令报"不提供命令执行能力" | provider 仍是 `filesystem`，需切换到 `docker` |
| 沙箱内 `pip install` 失败 | 镜像是否固化了 index-url；`pypi.tuna.tsinghua.edu.cn` 是否在放行清单 |
| 沙箱内访问内部服务被拒 | 该域名是否在 `allowed_domains`；查代理访问日志的拒绝记录 |
| 启动时报 egress 配置非法 | `allowlist` 档需要 `proxy_url`、`network_name` 与非空 `allowed_domains` |
| 沙箱工作区初始化失败 | 自定义镜像是否预建 `/workspace/inputs`、`/workspace/outputs`、`/assets` 并归属 uid 65534。运行时**不会** chown——`cap_drop=ALL` 已弃掉 `CAP_CHOWN`，属主必须在镜像构建期确定 |
| 代理容器启动即退出 | squid 以 `proxy` 用户运行，写不了 `/dev/stdout`；访问日志必须落到 `/var/log/squid/` |

查看出站审计日志：

```bash
docker exec zata-sandbox-egress-proxy cat /var/log/squid/access.log
```

日志形如 `TCP_TUNNEL/200 CONNECT pypi.tuna.tsinghua.edu.cn:443` 与
`TCP_DENIED/403 CONNECT example.com:443`——放行与拒绝都有记录，但**只到域名**，这也是
包级审计必须另走安装差异记录的原因。

容器按会话保留文件系统（运行结束只停止不删除），同一会话下次运行复用。会话容器的清理
触发时机（会话删除、TTL）作为后续运维项跟进。
