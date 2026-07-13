# 前台官网

本目录是 `zata-codes-template` 的前台官网与 Agent 工作区（Public Website + App Shell），基于 Next.js 16 + React 19 + Tailwind CSS v4 + shadcn/ui 构建。

## 技术栈

- **框架**：Next.js 16（App Router）
- **UI 库**：React 19
- **样式**：Tailwind CSS v4
- **组件库**：shadcn/ui
- **HTTP 客户端**：axios
- **表单**：React Hook Form + Zod
- **工作流画布**：@xyflow/react

## 本地开发

```bash
# 安装依赖
pnpm install

# 启动开发服务器（默认端口 3000）
pnpm dev
```

开发服务器启动后访问 `http://localhost:3000`。

直接运行 `pnpm dev` 时，后端默认在 `http://localhost:8000`，前端通过 Next.js rewrites 代理 `/api/*` 到后端。通过根目录 `just run` 启动时，会注入当前 `.env.run-state` 中的后端端口。

## 构建生产产物

```bash
pnpm build
```

产物使用 Next.js standalone 输出，由根目录 `frontend-public/Dockerfile` 构建为生产镜像。

## 项目结构

```text
frontend-public/
├── app/
│   ├── (marketing)/    # 营销页面：首页、Agent 广场、功能、定价、FAQ
│   ├── (auth)/          # 登录、注册
│   ├── (app)/           # 登录后应用页面
│   │   └── app/
│   │       ├── dashboard/    # 工作区首页
│   │       ├── agents/       # Agent 列表/新建/详情/编辑
│   │       ├── chat/         # 会话中心与单会话聊天
│   │       ├── workflows/    # 工作流列表/编辑器/运行
│   │       ├── tools/        # 工具列表
│   │       └── settings/     # 用户设置
│   ├── layout.tsx       # 根布局
│   └── globals.css      # 全局样式
├── components/
│   ├── ui/              # shadcn/ui 组件
│   ├── layout/          # 公共布局（SiteHeader、SiteFooter、AppShell、AppSidebar）
│   ├── agent/           # Agent 相关组件
│   ├── chat/            # 聊天相关组件
│   └── workflow/        # 工作流画布组件
├── lib/
│   ├── api/             # axios 封装与 API 调用
│   ├── types/           # TypeScript 类型定义
│   └── utils.ts         # 工具函数
├── public/              # 静态资源
├── next.config.ts
└── Dockerfile
```

## 与后端的集成

- 开发时可通过 `BACKEND_URL` 指向后端；`just run` 会自动注入该值。
- 容器环境通过 `API_BASE_URL` 指向 Compose 内部后端服务（如 `http://zata-codes-template-backend:8000`），不使用主机随机端口。
- 认证使用后端签发的 HTTP-only `session_id` cookie，因此与 `frontend-admin/` 管理平台共享登录态。

## Agent 平台功能

- **营销页**：首页 Hero、Agent 广场（`/marketplace`）、功能、定价、FAQ
- **Agent 管理**：创建、编辑、查看 Agent，配置模型、系统提示词、工具
- **会话聊天**：与 Agent 多轮对话，查看工具调用过程与结果
- **工作流编排**：基于 React Flow 的可视化节点画布，保存/运行工作流
- **工具管理**：查看平台预置工具列表

## 容器化

```bash
docker build -t zata-codes-template-public -f Dockerfile .
```

镜像基于 Node.js 运行 Next.js standalone，端口 `3000`。
