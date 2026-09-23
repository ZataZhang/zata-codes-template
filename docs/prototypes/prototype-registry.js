/**
 * 原型清单的唯一事实源（single source of truth）。
 *
 * Hub（prototype-hub.html）只从这份 registry 渲染；不要在 HTML 或 Markdown 里重复手写原型条目。
 * 字段口径见 skills/interactive-ui-prototype/references/prototype-hub-contract.md 的「数据契约」：
 * 至少包含 id、title、entry、project、module、form、version、updatedAt、availability、
 * validationLevel、description、preview、source；本项目额外维护 flows 与 provenance。
 *
 * 新增原型时：把可打开的实体文件放到 docs/prototypes/，在这里追加一条，
 * 并按约定补齐 preview 与 provenance 旁车：
 * - AI 生成/编辑的图片用同名 `.prompt.md`
 * - 浏览器截图或设计导出图用同名 `.source.md`
 */
window.PROTOTYPE_REGISTRY = [
  {
    id: "admin-users",
    title: "后台用户管理",
    project: "zata_code_template",
    module: "后台 / 用户管理",
    form: "code-native",
    version: "v1.0",
    updatedAt: "2026-09-16",
    availability: "available",
    validationLevel: "interactive prototype（component preview，非功能验收证据）",
    description:
      "后台用户管理的可点击原型：搜索、状态筛选、用户详情抽屉与启用/禁用确认流程，用于评审更完整的管理体验。",
    flows: [
      "用户列表 → 搜索或状态筛选",
      "打开用户详情抽屉",
      "启用/禁用确认 → 处理中 → 状态更新与 Toast 反馈",
      "重置演示恢复初始状态；抽屉与确认框支持遮罩点击或 Escape 关闭",
    ],
    preview: "./assets/admin-users-interactive.png",
    entry: "./admin-users-interactive.html",
    source: "./admin-users-interactive.md",
    sourceLabel: "原型说明页",
    provenance: "./assets/admin-users-interactive.source.md",
  },
  {
    id: "ai-image-users",
    title: "AI 生成图片 · 用户管理",
    project: "zata_code_template",
    module: "后台 / 用户管理",
    form: "image-state",
    version: "v1.0",
    updatedAt: "2026-09-16",
    availability: "available",
    validationLevel: "component preview（AI 生成图片 + 透明热点，非功能验收证据）",
    description:
      "用 ImageGen 生成的四个后台用户管理界面状态图，通过透明热点在状态之间点击跳转，用于快速确认视觉方向。",
    flows: [
      "用户列表 → 用户详情",
      "用户详情 → 启用/禁用确认",
      "确认 → 成功态",
    ],
    preview: "./assets/ai-image-hotspot-demo.png",
    entry: "./admin-users-ai-image-hotspot.html",
    source: "./admin-users-ai-image-hotspot.md",
    sourceLabel: "原型说明页",
    provenance: "./assets/ai-image-hotspot-demo.source.md",
  },
  {
    id: "login",
    title: "登录页",
    project: "zata_code_template",
    module: "认证",
    form: "code-native",
    version: "v1.0",
    updatedAt: "2026-09-20",
    availability: "available",
    validationLevel: "interactive prototype（component preview，非功能验收证据）",
    description:
      "账号密码登录页的可点击原型：必填校验、提交中、成功与失败分支、密码可见性切换。结构与文案取自 frontend-public 的真实登录页。",
    flows: [
      "idle → 留空提交 → 必填校验错误",
      "填写后提交 → loading（按钮禁用并转圈）",
      "→ 成功（密码非 wrong）或失败（密码填 wrong，模拟 401）",
      "密码显示/隐藏切换；忘记密码提示；立即注册为范围外提示",
    ],
    preview: "./assets/login-demo.png",
    entry: "./login-demo.html",
    source: "./login-demo.md",
    sourceLabel: "原型说明页",
    provenance: "./assets/login-demo.source.md",
  },
  {
    id: "file-viewer",
    title: "只读文件与改动查看器",
    project: "zata_code_template",
    module: "开发工具链 / 代码阅读",
    form: "code-native",
    version: "v1.0",
    updatedAt: "2026-09-21",
    availability: "available",
    validationLevel: "interactive prototype（component preview，非功能验收证据）",
    description:
      "代替重型 IDE 完成「读文件 + 看改动」的本机只读查看器：左侧文件树，右侧内容区，界面内一键在文件与改动视图之间切换。文件树、文件内容与 diff 均为本地 fixture。",
    flows: [
      "文件视图 → 选文件看带行号与高亮的正文 → 点目录折叠展开",
      "切到改动视图 → 左树只列改动文件（A/M 徽标 + 增删统计）→ 右侧逐行 diff",
      "切换基线：工作区改动 / main / v1.2.0（空态）",
      "过滤文件树（输入即筛，命中路径的祖先目录自动展开）",
      "uv.lock → 文件过大提示；login-demo.png → 二进制文件提示",
      "闲置 20 秒（真实为 30 分钟）→ 服务退出态 + 重新连接指引；Dock 可重置",
    ],
    preview: "./assets/file-viewer-interactive.png",
    entry: "./file-viewer-interactive.html",
    source: "./file-viewer-interactive.md",
    sourceLabel: "原型说明页",
    provenance: "./assets/file-viewer-interactive.source.md",
  },
  {
    id: "run-tracing",
    title: "Run 执行轨迹",
    project: "zata_code_template",
    module: "后台 / 运行诊断",
    form: "code-native",
    version: "v1.0",
    updatedAt: "2026-09-23",
    availability: "available",
    validationLevel: "interactive prototype（component preview，非功能验收证据）",
    description:
      "后台执行轨迹页的可点击原型：Run 列表与详情两栏，以唯一 RUN ROOT 为根渲染模型/工具节点树，覆盖失败节点、父级 fallback、历史受限与空轨迹状态。",
    flows: [
      "Run 列表 → 选中任一条 → 右侧详情切换",
      "搜索框过滤列表；无命中显示空态",
      "状态筛选：成功 / 失败 / 运行中 / 历史受限",
      "失败节点 → 红色样式与 provider_timeout 错误码",
      "历史受限 Run → limited 提示，不伪造根节点",
      "空轨迹 Run → 仅 RUN ROOT + 空态提示",
      "未终结 Run 的下载按钮禁用；重置演示恢复初始状态",
    ],
    preview: "./assets/run-tracing.png",
    entry: "./run-tracing.html",
    source: "./run-tracing.md",
    sourceLabel: "原型说明页",
    provenance: "./assets/run-tracing.source.md",
  },
];
