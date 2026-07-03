# E2E 测试快速开始

本仓库使用 Playwright 做端到端测试，测试包位于 `tests/playwright-e2e/`。

## 前置条件

1. 安装 Node / pnpm。
2. 准备本地环境：
   ```bash
   cp .env.example .env.local
   # 编辑 .env.local，至少配置：
   #   DATABASE_URL
   #   REDIS_URL
   #   AUTH_ADMIN_BOOTSTRAP_USERNAME
   #   AUTH_ADMIN_BOOTSTRAP_PASSWORD
   ```
3. （如使用外部数据库/Redis）启动测试中间件：
   ```bash
   docker compose -f docker-compose.testing.yml up -d
   ```

## 启动本地服务

```bash
just run
```

`just run` 会同时启动 backend、admin 前端、public 前端，并把实际端口写入项目根目录的运行状态文件（`.env.run-state`）。E2E 默认 URL 会从该 run-state 自动读取，无需手动设置环境变量。

默认端口（未被占用时）：

- backend：`http://127.0.0.1:8000`
- admin 前端：`http://localhost:5173`（Vite dev server 默认只绑定 localhost）
- public 前端：`http://127.0.0.1:3000`

## 首次安装 Playwright

```bash
just e2e-install
```

## 运行测试

`just e2e` 是单命令入口：它会自动 `just run all` 启动 backend + admin 前端 + public 前端，跑完测试后再 `just down` 清理。如果服务已经在运行，会直接复用，不会重复启停。

```bash
just e2e                          # 全部测试（不含视觉回归；需要配置 public/admin 凭据）
just e2e no-auth                  # 无需登录的测试，最快最稳
just e2e smoke                    # smoke 测试（含 admin 登录）
just e2e-report                   # 查看上一次运行的 HTML 报告
```

### 跑单个文件 / 目录

```bash
just e2e tests/smoke/public-home.no-auth.spec.ts
just e2e tests/smoke
```

### 有头模式（弹出浏览器窗口）

`--headed` 可以放在任意位置：

```bash
just e2e tests/smoke/public-home.no-auth.spec.ts --headed
just e2e --headed tests/smoke/public-home.no-auth.spec.ts
just e2e headed                   # 有头跑全部 no-auth（等效于 --grep-invert @visual --headed --workers=1）
```

### 凭据说明

- `no-auth` 测试不需要任何凭据。
- `smoke` / 全量测试默认读取项目根目录 `.env.local` 中的 public 种子凭据：
  ```bash
  APP_BOOTSTRAP_EMAIL=user@example.com
  APP_BOOTSTRAP_PASSWORD=user123
  ```
  后端启动时会自动创建该 public 用户。
- admin 相关测试默认读取 `.env.local` 中的 admin 种子凭据：
  ```bash
  AUTH_ADMIN_BOOTSTRAP_USERNAME=admin
  AUTH_ADMIN_BOOTSTRAP_PASSWORD=admin
  ```
- 如需覆盖（例如使用不同的 E2E 账号），可在 `tests/playwright-e2e/.env.e2e.local` 中设置：
  ```bash
  PLAYWRIGHT_IDENTIFIER=<public 邮箱>
  PLAYWRIGHT_PASSWORD=<密码>
  PLAYWRIGHT_ADMIN_IDENTIFIER=<admin 用户名>
  PLAYWRIGHT_ADMIN_PASSWORD=<密码>
  ```
  `.env.e2e.local` 优先级高于 `.env.local`。

### 测试结果

每次 `just e2e` 会把 artifacts（视频、截图、trace、junit.xml）写入按运行时间戳命名的目录：

```text
tests/playwright-e2e/test-results/2026-07-02T11-31-08/
├── junit.xml
└── .../video.webm
```

HTML 报告仍固定在 `tests/playwright-e2e/playwright-report/`，方便 `just e2e-report` 直接打开。

## 按 PRD 收集 E2E 证据

通用收集器会读取 PRD 中的 `Realistic Validation Plan`，执行对应 oracle，并把日志、HTML 报告、失败视频收集到 `tasks/evidence/<prd-basename>/`。

```bash
cp tests/playwright-e2e/.env.e2e.example tests/playwright-e2e/.env.e2e.local
# 编辑 tests/playwright-e2e/.env.e2e.local，填入真实 admin 密码

# 只跑某一条 oracle
just e2e-evidence tasks/pending/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests.md rv-2

# 跑该 PRD 下所有 e2e/smoke/manual oracle
just e2e-evidence tasks/pending/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests.md
```

收集到的证据示例：

```text
tasks/evidence/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests/
├── rv-2-output.log
├── rv-2-playwright-report/
└── rv-2-test-results/
    └── .../video.webm
```

## 环境变量参考

| 变量 | 说明 | 默认值（dev 模式） |
|---|---|---|
| `PLAYWRIGHT_BASE_URL` | public 前端地址 | 优先读取 run-state 中的 `FRONTEND_PUBLIC_PORT`，fallback `http://127.0.0.1:3000` |
| `PLAYWRIGHT_ADMIN_BASE_URL` | admin 前端地址 | 优先读取 run-state 中的 `FRONTEND_ADMIN_PORT`（兼容旧 `FRONTEND_PORT`），fallback `http://localhost:5173` |
| `PLAYWRIGHT_HEALTH_URL` | 后端健康检查 | `${apiBaseUrl}/health`，apiBaseUrl 优先读取 run-state 中的 `BACKEND_PORT` |
| `PLAYWRIGHT_ADMIN_IDENTIFIER` | admin 登录账号 | fallback 到 `AUTH_ADMIN_BOOTSTRAP_USERNAME` |
| `PLAYWRIGHT_ADMIN_PASSWORD` | admin 登录密码 | fallback 到 `AUTH_ADMIN_BOOTSTRAP_PASSWORD` |
| `PLAYWRIGHT_SKIP_STACK_BOOT` | 跳过 global setup 的 stack 启动 | `0` |

## 端口冲突 / worktree

如果 `3000` / `5173` / `8000` 被占用，可用：

```bash
just run backend_port=8010 frontend_admin_port=13173 frontend_public_port=3001
```

`just run` 会把实际端口写入 `.env.run-state`，`support/env.ts` 会自动读取，无需再手动设置 `PLAYWRIGHT_*_URL`。

在 worktree 场景中，`scripts/shared/worktree/create.sh` 会自动为新 worktree 分配随机端口并写入对应 run-state，避免多 worktree 同时 `just run` 冲突。
