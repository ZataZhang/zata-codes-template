# playwright-e2e

Playwright E2E 测试包。将此目录复制到新项目，按照 TODO 注释适配即可。

## 目录结构

```
playwright-e2e/
├── fixtures/
│   └── session.fixture.ts      # 带 auth 的 test 扩展 + CleanupRegistry
├── page-objects/
│   └── LoginPage.ts            # 登录页 Page Object (需适配选择器)
├── scripts/
│   ├── global-setup.mjs        # 启动 stack + 等待就绪
│   ├── global-teardown.mjs     # 关闭 stack
│   └── stack-control.mjs       # 核心：docker/dev 模式切换 + 就绪轮询
├── support/
│   ├── api-client.ts           # 认证 HTTP 客户端 (seed / cleanup)
│   ├── cleanup.ts              # CleanupRegistry (逆序执行清理)
│   ├── demo-helpers.ts         # 演示/验收视频停顿 helper
│   ├── env.ts                  # URL / 凭证 / 路径解析 (读 env 变量)
│   └── test-data.ts            # 工具函数 (唯一名称生成等)
└── tests/
    ├── setup/
    │   └── auth.setup.ts           # 登录并持久化 session 到 .auth/
    ├── smoke/
    │   └── pages.spec.ts           # 页面冒烟测试
    └── workflows/
        ├── screenshot.spec.ts          # 截图模式 (@review / @visual)
        └── no-auth-example.no-auth.spec.ts  # 无需 auth 的测试模式
```

## 适配清单

本项目已适配：

1. **`support/env.ts`** — dev 模式默认 URL 优先读取 `just run` 写入 git run-state（`.git/vanta-run.env`）的端口；无 run-state 时 fallback public 前端 `3000`、admin 前端 `5173`、backend `8000`，健康检查路径 `/health`。
2. **`scripts/stack-control.mjs`** — 健康检查路径同步为 `/health`。
3. **`page-objects/LoginPage.ts`** — 保留模板，供需要表单登录的测试复用。
4. **`tests/setup/auth.setup.ts` / `tests/setup/admin-auth.setup.ts`** — 使用 `/api/auth/login` / `/api/admin/auth/login` 建立 session。
5. **`tests/smoke/public-home.no-auth.spec.ts`** — public 首页冒烟测试。
6. **`tests/smoke/admin-sign-in.no-auth.spec.ts`** — admin 前端表单登录冒烟测试。

## 前置条件

**Docker 模式**（默认）需要在仓库根目录存在 compose 文件（`docker-compose.yml` / `compose.yaml` 等）。
若目标服务已在运行，设置 `PLAYWRIGHT_SKIP_STACK_BOOT=1` 跳过 stack 启动即可。

本地 dev 默认端口（可被 `just run` 参数或 worktree 随机端口覆盖）：backend `8000`、admin `5173`、public `3000`。`just run` 会写入 `.git/vanta-run.env`，E2E 会据此自动定位。

在父仓库中可通过 `just` 统一入口运行 e2e 测试：

```bash
just e2e-install   # 安装依赖（首次运行）
just e2e           # 运行所有测试
just e2e smoke     # 只跑 smoke
just e2e no-auth   # 只跑无 auth 测试
just e2e report    # 查看 HTML 报告
```

也可以按 PRD 收集 E2E 证据（日志、HTML 报告、失败视频）：

```bash
cp tests/playwright-e2e/.env.e2e.example tests/playwright-e2e/.env.e2e.local
# 编辑 tests/playwright-e2e/.env.e2e.local，填入真实 admin 密码

just e2e-evidence tasks/pending/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests.md rv-2
```

## 运行命令

```bash
# 安装依赖
pnpm install
pnpm exec playwright install chromium

# 运行所有测试 (需要本地 stack 或 docker-compose.yml)
pnpm test

# 只跑截图 / 审查类测试
pnpm test:review    # playwright test --grep @review

# 视觉回归测试
pnpm test:visual
pnpm test:update    # 更新基准图

# 无 auth 的测试（指向远端环境）
PLAYWRIGHT_SKIP_STACK_BOOT=1 \
PLAYWRIGHT_BASE_URL=https://your-staging.example.com \
PLAYWRIGHT_HEALTH_URL=https://your-staging.example.com \
pnpm test:no-auth

# 带 auth 的测试（指向远端环境）
PLAYWRIGHT_SKIP_STACK_BOOT=1 \
PLAYWRIGHT_BASE_URL=https://your-admin.example.com \
PLAYWRIGHT_API_BASE_URL=https://your-api.example.com \
PLAYWRIGHT_HEALTH_URL=https://your-api.example.com/health \
PLAYWRIGHT_IDENTIFIER=admin \
PLAYWRIGHT_PASSWORD=secret \
pnpm test

# 查看 HTML 报告
pnpm report
```

## 两种 Project 模式

| Project | 文件命名 | 需要登录 | 使用场景 |
|---|---|---|---|
| `chromium` | `*.spec.ts` | ✓ (auth.setup.ts 先跑) | 需要 session 的业务测试 |
| `no-auth` | `*.no-auth.spec.ts` | ✗ | 公开页面、demo proxy、健康检查、演示视频 |

### no-auth project 与演示/验收视频

`no-auth` project 在 `playwright.config.ts` 里默认配置了 `launchOptions: { slowMo: 200 }`，让每次点击、输入都有约 200ms 的间隔，录制出来的视频不会是一瞬间完成的操作流。

如果某些关键步骤需要额外停留（例如填完表单后让观众看清），在测试里引入共享 helper：

```ts
import { humanPause } from '../support/demo-helpers'

await page.goto('/login')
await humanPause(page, 900) // 额外停留约 0.9 秒
```

设置 `PLAYWRIGHT_DEMO_PAUSE=0` 可在常规 CI 跑测时跳过这些人工停顿。
