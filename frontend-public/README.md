# 前台官网

本目录是 `zata-codes-template` 的前台官网（Public Website + App Shell），基于 Next.js 16 + React 19 + Tailwind CSS v4 +
shadcn/ui 构建。

## 技术栈

- **框架**：Next.js 16（App Router）
- **UI 库**：React 19
- **样式**：Tailwind CSS v4
- **组件库**：shadcn/ui
- **HTTP 客户端**：axios
- **表单**：React Hook Form + Zod

## 本地开发

```bash
# 安装依赖
pnpm install

# 启动开发服务器（默认端口 3000）
pnpm dev
```

开发服务器启动后访问 `http://localhost:3000`。

## 构建生产产物

```bash
pnpm build
```

产物使用 Next.js standalone 输出，由根目录 `frontend-public/Dockerfile` 构建为生产镜像。

## 项目结构

```text
frontend-public/
├── app/
│   ├── (marketing)/    # 营销页面：首页、功能、定价、FAQ
│   ├── (app)/          # 登录后应用页面：dashboard、settings、tasks、projects
│   ├── layout.tsx      # 根布局
│   └── globals.css     # 全局样式
├── components/
│   ├── ui/             # shadcn/ui 组件
│   └── ...             # 项目级业务组件
├── lib/
│   ├── api.ts          # axios 封装与 API 调用
│   └── auth.tsx        # 会话状态与受保护布局
├── public/             # 静态资源
├── next.config.ts
└── Dockerfile
```

## 与后端的集成

- 开发时直接请求 `http://localhost:8000`。
- 生产时通过环境变量 `API_BASE_URL` 指向后端服务（如 `http://zata-codes-template-backend:8000`）。
- 认证使用后端签发的 HTTP-only `session_id` cookie，因此与 `frontend/` 管理平台共享登录态。

## 容器化

```bash
docker build -t zata-codes-template-public -f Dockerfile .
```

镜像基于 Node.js 运行 Next.js standalone，端口 `3000`。
