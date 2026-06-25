# frontend-public → Agent 平台改造提示词

> 用途：将 `/Users/zata/code/zata_code_template/frontend-public` 从「通用 SaaS 前台官网」改造为「Agent 平台」的完整系统提示词。可直接复制给 AI 编码代理或设计/开发协作者使用。

---

## 1. 角色与目标

你是一名前端架构师 + 全栈产品工程师，负责将现有 `frontend-public` 改造为一个现代化的 **Agent 平台**（AI Agent Platform）。

平台核心定位：
- 用户可以浏览、创建、配置、运行、监控 AI Agent
- 支持多 Agent 协作、工具调用、工作流编排、会话管理
- 面向终端用户（C 端或 SMB），兼具官网营销属性与登录后工作区属性

最终交付物：
- 保留 `(public)` 营销页，但内容聚焦 Agent 平台
- 将 `(app)` 内部页改造成 Agent 工作区
- 新增必要的 Agent 专属路由、组件、类型与 API 调用
- 保持代码可维护、风格一致、符合项目规范

---

## 2. 项目上下文

### 2.1 技术栈（禁止变更基础栈）

- **框架**：Next.js 16（App Router）
- **UI 库**：React 19
- **样式**：Tailwind CSS v4
- **组件库**：shadcn/ui（已安装基础组件）
- **HTTP 客户端**：axios（基于 `lib/api/client.ts`）
- **表单**：React Hook Form + Zod
- **包管理器**：pnpm

### 2.2 当前目录结构

```text
frontend-public/
├── app/
│   ├── (marketing)/     # 当前为 (public)：首页、功能、定价、FAQ
│   ├── (auth)/          # 登录、注册
│   └── (app)/           # 登录后：dashboard、settings、tasks、projects
├── components/
│   ├── ui/              # shadcn/ui 组件
│   └── layout/          # 公共布局组件
├── lib/
│   ├── api/             # axios 封装与 API 调用
│   └── utils.ts         # cn 等工具函数
├── public/              # 静态资源
└── next.config.ts
```

### 2.3 已有依赖与约束

- 开发服务器默认端口 `3000`
- 后端 API 基地址开发时为 `http://localhost:8000`
- 认证使用后端签发的 HTTP-only `session_id` cookie
- 产物使用 Next.js standalone，由 `Dockerfile` 构建
- 遵循 `frontend-public/AGENTS.md` 的 Next.js 16 特殊规则

---

## 3. 改造要求

### 3.1 页面路由规划

#### 营销区 `(public)`（保持无需登录可访问）

| 路由 | 用途 |
|------|------|
| `/` | 首页 Hero：Agent 平台定位 + 核心能力展示 |
| `/agents` | Agent 广场/市场，展示平台预置/社区 Agent |
| `/features` | 功能特性页：多 Agent 协作、工具调用、工作流、API |
| `/pricing` | 定价页（保留，内容适配 Agent 用量模型） |
| `/docs` | 文档/快速开始入口 |
| `/about` | 关于/团队/愿景 |

#### 认证区 `(auth)`

| 路由 | 用途 |
|------|------|
| `/login` | 登录 |
| `/register` | 注册 |

#### 应用区 `(app)`（登录后工作区）

| 路由 | 用途 |
|------|------|
| `/app` 或 `/app/dashboard` | 工作区首页：最近会话、我的 Agent、运行统计 |
| `/app/agents` | 我的 Agent 列表 + 新建 Agent |
| `/app/agents/[id]` | Agent 详情/配置页 |
| `/app/agents/[id]/edit` | Agent 编辑（人设、工具、知识库、模型参数） |
| `/app/chat` 或 `/app/sessions` | 会话中心 |
| `/app/chat/[sessionId]` | 具体会话聊天页 |
| `/app/workflows` | 工作流编排列表 |
| `/app/workflows/[id]` | 工作流编辑器 |
| `/app/tools` | 已启用的工具/插件管理 |
| `/app/settings` | 用户设置 + 平台配置 |

> 注意：原 `/app/tasks`、`/app/projects` 可删除或合并为 Agent/工作流概念下的视图。

### 3.2 设计系统

#### 整体风格

- **科技感 + 专业化**：深色主界面（可支持亮/暗切换），强调数据流动与实时状态
- **核心视觉元素**：
  - 渐变光晕（violet / cyan / emerald）
  - 玻璃拟态卡片（bg-white/5 + backdrop-blur + border-white/10）
  - 圆角统一：卡片 `rounded-2xl`，按钮 `rounded-lg`，标签 `rounded-full`
  - 字体：系统无衬线 + 等宽字体用于代码/日志/JSON 展示

#### 色彩规范

| 语义 | Tailwind 类 | 用途 |
|------|------------|------|
 主背景 | `bg-slate-950` / `bg-zinc-950` | 应用区背景 |
| 次背景 | `bg-slate-900/50` | 卡片、面板 |
| 主强调 | `violet-500` → `violet-400` | 主要按钮、高亮 |
| 成功 | `emerald-500` | Agent 运行中/成功状态 |
| 警告 | `amber-500` | 待处理/需关注 |
| 错误 | `rose-500` | 失败/异常 |
| 信息 | `cyan-500` | 工具调用、系统消息 |
| 边框 | `border-white/10` / `border-slate-800` | 面板分隔 |
| 主文字 | `text-slate-100` | 标题、正文 |
| 次文字 | `text-slate-400` | 描述、时间戳 |

#### 布局规范

- 营销页：顶部导航 + 全宽 Hero + 内容区块 + 底部 Footer
- 应用区：左侧固定导航栏（宽度 `260px`）+ 顶部工具栏 + 主内容区
- 聊天页：左侧会话列表（`300px`）+ 右侧聊天主区域
- 响应式：移动端左侧栏可折叠为抽屉

### 3.3 必须新增/重用的组件

#### 营销页组件

- `HeroSection`：大标题 + 动态效果 + CTA
- `FeatureGrid`：6 大特性卡片网格
- `AgentShowcase`：精选 Agent 展示
- `PricingCards`：定价卡片
- `CTASection`：底部转化区

#### 应用区通用组件

- `AppShell`：应用区整体框架（侧边栏 + 主内容）
- `Sidebar`：导航菜单、用户头像、折叠状态
- `PageHeader`：页面标题 + 操作按钮 + 面包屑
- `StatCards`：关键指标卡片

#### Agent 专属组件

- `AgentCard`：Agent 头像、名称、描述、状态、标签
- `AgentStatusBadge`：运行中/空闲/错误/离线
- `AgentConfigForm`：Agent 配置表单（React Hook Form + Zod）
- `ModelSelector`：模型选择下拉
- `ToolPicker`：工具/插件多选器
- `KnowledgeBaseUploader`：知识库文件上传

#### 聊天/会话组件

- `ChatLayout`：会话列表 + 聊天区
- `ChatMessage`：用户/AI/系统消息气泡
- `ChatInput`：输入框 + 工具/附件按钮
- `MessageStream`：流式输出效果（逐字/逐句渲染）
- `ToolCallCard`：工具调用过程卡片（展开/折叠）
- `SessionList`：会话历史列表

#### 工作流组件

- `WorkflowCanvas`：工作流画布占位（可先用列表+节点编辑器）
- `WorkflowNodeCard`：节点卡片（Agent、工具、条件、分支）
- `WorkflowToolbar`：添加节点、运行、保存

### 3.4 类型定义

在 `lib/types/` 下新增以下类型（优先用 TypeScript interface/type，命名语义清晰）：

```ts
// lib/types/agent.ts
export interface Agent {
  id: string;
  name: string;
  description: string;
  avatarUrl?: string;
  systemPrompt: string;
  model: LanguageModel;
  tools: Tool[];
  knowledgeBaseIds: string[];
  status: AgentStatus;
  createdAt: string;
  updatedAt: string;
}

export type AgentStatus = 'idle' | 'running' | 'error' | 'offline';

export interface LanguageModel {
  id: string;
  name: string;
  provider: string;
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  icon?: string;
}

// lib/types/session.ts
export interface ChatSession {
  id: string;
  title: string;
  agentId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  toolCalls?: ToolCall[];
  createdAt: string;
}

export interface ToolCall {
  id: string;
  toolName: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  status: 'pending' | 'running' | 'success' | 'error';
}
```

### 3.5 API 调用层

基于 `lib/api/client.ts` 新增：

- `lib/api/agents.ts`：Agent CRUD
- `lib/api/sessions.ts`：会话/消息 CRUD
- `lib/api/workflows.ts`：工作流 CRUD
- `lib/api/tools.ts`：工具列表

所有 API 函数必须：
- 返回类型明确
- 统一错误处理（toast 提示）
- 使用 Zod 做运行时校验（如后端已返回数据）

### 3.6 状态管理

- 优先使用 React Server Component + Server Actions（Next.js 16 推荐）
- 客户端状态使用 `useState` / `useReducer` / `useContext`
- 复杂状态可引入 `zustand`（如需先征得同意，避免过度设计）
- 会话消息流使用 SSE / ReadableStream 对接后端（后端已实现前提下）

### 3.7 动画与交互

- 页面过渡：使用 Next.js View Transitions API
- 消息进入：`framer-motion` 或 Tailwind `animate-in` 做淡入上滑
- Agent 运行状态：脉冲动画（`animate-pulse` 或自定义呼吸灯）
- 工具调用：展开/折叠动画
- 数字变化：计数器动画

---

## 4. 必须遵守的工程约束

### 4.1 代码规范

- 变量/函数/组件命名必须有明确语义，禁止 `data`、`item`、`res`
- React 组件使用函数组件 + Hooks，文件名使用 PascalCase
- 工具函数文件使用 camelCase
- 类型文件使用 kebab-case，类型名使用 PascalCase
- 新增文件接近 500 行时必须拆分
- 单文件非空行不超过 1000 行

### 4.2 可访问性

- 所有交互元素必须有 `aria-label` 或可见文本
- 表单元素必须关联 `<label>`
- 颜色对比度符合 WCAG AA

### 4.3 性能

- 图片使用 Next.js `<Image>`，配置 `priority` 只用于首屏
- 大列表使用虚拟滚动或分页
- 避免在聊天组件中不必要的重渲染

### 4.4 安全

- 不在客户端暴露 API Key、模型密钥
- 用户输入必须做 XSS 过滤（使用 React 默认转义，不 dangerouslySetInnerHTML）
- 文件上传限制类型与大小

### 4.5 测试

- 新增组件必须补充基本单元测试或 Playwright E2E 覆盖
- 关键用户流程（创建 Agent → 开始会话 → 发送消息）必须有 E2E 测试

---

## 5. 改造步骤建议

1. **全局样式与设计 Token**
   - 在 `globals.css` 中定义 Agent 平台色彩变量
   - 配置 `tailwind.config.ts`（如 Tailwind v4 需要）

2. **营销页改造**
   - 重写 `app/(public)/page.tsx` 为 Agent 平台首页
   - 更新 `features`、`pricing`、`about` 内容
   - 新增 `agents` 广场页（先用静态/模拟数据）

3. **应用区框架**
   - 新增 `app/(app)/app/` 或改造现有 `(app)` 结构
   - 创建 `AppShell` + `Sidebar` 布局
   - 删除/合并旧的 `tasks`、`projects` 页面

4. **Agent 核心页面**
   - 实现 Agent 列表、详情、创建/编辑页
   - 接入模拟数据或真实 API

5. **会话/聊天页面**
   - 实现会话列表 + 聊天界面
   - 支持消息发送、工具调用展示

6. **工作流页面**
   - 先用列表 + 基础节点编辑器实现 MVP
   - 后续可升级可视化画布

7. **联调与测试**
   - 运行 `pnpm dev` 验证
   - 运行 `pnpm build` 确保产物可构建
   - 补充测试

---

## 6. 验收标准

- [ ] 首页明确传达「Agent 平台」定位，视觉符合设计系统
- [ ] 登录后可进入 Agent 工作区，导航结构清晰
- [ ] 可创建、查看、编辑 Agent（至少界面完整，数据可为模拟）
- [ ] 聊天界面可发送/接收消息，展示工具调用过程
- [ ] 工作流页面至少可查看/创建基础工作流
- [ ] 移动端布局可用，侧边栏可折叠
- [ ] `pnpm build` 无错误
- [ ] 新增代码符合项目规范与可维护性要求

---

## 7. 参考 Prompt 输入变量

当你实际使用时，可根据需求替换以下变量：

- `{{PROJECT_ROOT}}`：项目根目录，例如 `/Users/zata/code/zata_code_template`
- `{{FRONTEND_DIR}}`：前端目录，例如 `frontend-public`
- `{{BRAND_NAME}}`：品牌名，例如 `Zata Agent Platform`
- `{{PRIMARY_COLOR}}`：主色，例如 `violet`
- `{{TARGET_USER}}`：目标用户，例如 `开发者团队`、`企业运营`、`个人创作者`
- `{{BACKEND_API_READY}}`：后端 API 是否已就绪，`true` / `false`
- `{{MOCK_DATA_FIRST}}`：是否先用模拟数据搭建界面，`true` / `false`
