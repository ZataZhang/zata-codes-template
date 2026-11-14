# Pre-PR 审查报告：可复用的对象存储与文件直传直取能力

## 状态

**VERDICT: CHANGES REQUESTED** — 已完成当前 feature 的代码与需求边界审查；这不代表独立真实行为验证 PASS。

## 验收视图

交付边界是按需复制的 core 契约、OSS adapter、配置装配与模板分发规则。消费项目拥有领域授权与对象引用；普通文件字节由浏览器直接传给 OSS/CDN；不新增模板产品路由、ORM 或页面。

## 发现与修复

[HIGH][requirement] 专用 RV 源码仍在代码提交中。已将消费 API/页面、Playwright oracle/config 全部移入 evidence scripts/，并调整 runner、文档和 PRD Change Log。修复待 runner 提交；验收行为未削减。

[HIGH][validation] PRD §9 Validation Acceptance 要求 rv-1 至 rv-3 通过真实 OSS/CDN 入口。逐项重跑仍因缺少隔离 endpoint、region、Bucket、服务端测试凭据、写入授权及 CDN 域名而 exit 3。没有观察 POST policy 大小约束、fresh OSS GET 摘要、CDN 缓存、私有签名过期拒绝，也没有对应负向对照与截图，无法批准安全与交付边界。此项需要环境负责人提供隔离资源，不能通过改 exit code、mock 或放宽 oracle 修复。

[MEDIUM][validation] 分发回归测试默认克隆远端默认分支，不能可靠验证当前工作树。已修复为运行当前过滤器并覆盖允许/拒绝对照，设置五秒上限；不将该单元测试当成完整 copy/list 证据。

## 代码审查

已阅读 core 契约、OSS PostObject/GET 签名适配、可选配置、composition、分发规则及全部 RV 路径。本轮未发现另一项置信度超过 80% 的产品代码缺陷。服务端密钥只从环境读取，bearer grant 的 repr 已隐藏，普通 API 不转发对象正文。

## 文档与验证

文档和导航覆盖按需集成、权限、CORS、CDN、缓存与异步字节处理。最终修复树已通过 just test（核心档与 OIDC 包）、架构检查、mkdocs build、迁移后 oracle 枚举与 TypeScript/Python 静态检查。真实 RV 继续保持 BLOCKED，Acceptance Checklist 与 Human-Confirmed 未勾选。

结论：必需真实验证门禁未满足，禁止将阻塞记录解释为行为通过。
