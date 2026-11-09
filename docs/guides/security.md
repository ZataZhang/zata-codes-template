# API 与部署安全基线

本文说明模板提供的请求保护，以及生产部署仍需由运营环境提供的网络层防护。应用限流主要约束到达服务的 HTTP 请求；大流量网络攻击仍需云厂商、CDN 或上游网络提供清洗能力。

## 应用层默认策略

模板通过 `config.toml` 的 `[security]` 配置请求限制，环境变量使用 `SECURITY_` 前缀覆盖。

| 防护项 | 默认值 | 作用范围 |
| --- | --- | --- |
| 请求体上限 | 1 MiB | 应用所有 HTTP 请求；Traefik 与 Admin Nginx 在入口也限制 API body，超限返回 `413` |
| 通用 API 限流 | 每来源 IP 每分钟 120 次 | 共享 Redis 计数；`/health`、`/ready`、`/live` 除外 |
| public 登录 | 来源 IP 每 5 分钟 10 次；登录标识每 15 分钟 30 次 | 两个维度都限制；标识在 Redis key 中使用 SHA-256 摘要 |
| admin 登录 | 来源 IP 每 5 分钟 5 次；登录标识每 15 分钟 20 次 | 比 public 登录更严格 |
| public 注册 | 来源 IP 每小时 5 次 | 降低批量注册和密码哈希资源消耗 |

限流存储复用会话 Redis。Redis 连接与读写都设为 2 秒超时；Redis 无法使用时，受保护请求返回 `503`，不会在计数保护失效时继续无限执行。请求超限返回 `429` 和 `Retry-After`。计数窗口从该桶首次请求时开始，避免后续请求不断延长封锁时间。

这些默认值是模板起点，应结合正常流量、办公室或运营商 NAT、登录失败率和服务容量调整。`config.toml` 可调整应用层阈值；入口代理阈值可在 Compose 环境中调整。

按登录标识限流会让同一账户在短时间内无法继续尝试，即使请求来自不同 IP。阈值应结合用户群规模调节；面向公众的高价值账户还应考虑多因素认证、风险验证或验证码，避免恶意请求耗尽目标账户的登录额度。

认证 DTO 也限制标识、邮箱、显示名称和密码长度。密码最多 72 个 UTF-8 字节，避免 bcrypt 静默忽略尾部字符。

## 入口代理与后端网络

生产 Compose 为管理员和公开站点分别建立 `/api/` 路由，并配置 Traefik `RateLimit`、`InFlightReq` 与请求体缓冲上限。入口默认 body 上限和应用层默认一致，为 1 MiB。调大请求上限时，需同步调整 `SECURITY_REQUEST_BODY_MAX_BYTES`、`ADMIN_API_MAX_BODY_BYTES` 和 `PUBLIC_API_MAX_BODY_BYTES`；Admin Nginx 会读取对应的环境变量。

| 入口 | 平均速率 | 突发额度 | 同时请求上限 |
| --- | ---: | ---: | ---: |
| Public API | 120 次 / 分钟 | 60 | 40 |
| Admin API | 60 次 / 分钟 | 20 | 20 |

`docker-compose.dokploy.yml` 与 `deploy/vps-traefik/docker-compose.yml` 都会把后端放在独立的 `backend-app` 网络中；前端同时连接 `backend-app` 和入口网络，后端没有公网端口映射，也不加入共享 Traefik 网络。Dokploy Compose 默认将 `FORWARDED_ALLOW_IPS` 设为 `*`，仅在这个边界内使用，使 Uvicorn 能读取前端代理传来的客户端 IP；可按网络结构收窄该值。不要将后端端口发布到公网，也不要把不受信任的容器接入 `backend-app`。

若 CDN 或负载均衡位于 Traefik 前方，应先在宿主机 Traefik 配置中只信任该供应商公布的转发来源地址，再把 `TRAEFIK_CLIENT_IP_DEPTH` 设为清洗后 `X-Forwarded-For` 链中的正确位置。直连 Traefik 时保持 `0`，使用连接来源地址。不要直接信任任意客户端提供的 `X-Forwarded-For`。

前端代理禁止公开访问 `/api/metrics`。Prometheus 只能从私有监控网络访问后端 `/metrics`；指标默认关闭。启用时设置 `OBSERVABILITY_METRICS_ENABLED=true`，并确保采集器只连接私有后端网络。MCP HTTP endpoint 默认关闭；启用前应为对应工具接入身份认证、授权和独立入口策略。

## 生产环境还需配置的网络防护

仓库不能代替云账号或宿主机的 DDoS、WAF 和防火墙配置。上线时至少确认：

1. 云厂商或 CDN 已启用适合业务的网络层 DDoS 清洗和 WAF / Bot 规则。
2. 源站 IP 不会绕过 CDN/WAF 被直接访问；安全组只开放所需的 80/443，以及受来源限制的管理端口。
3. SSH 使用密钥并限制来源；生产后端端口不映射到宿主机。
4. 对 `429`、`413`、`503`、登录失败率、CPU/内存、Redis 和数据库连接池设置告警。
5. 对邮件、短信、模型 API 等按次计费的集成设置供应商额度或账单告警。

模板已有 Docker CPU / 内存限制、管理员路由鉴权、分页上限和运行记录导出上限。派生项目新增耗时或收费型接口时，再按接口增加执行超时、用户额度和并发上限；确实有长任务后再引入队列。
