---
name: manage-roadmap
description: Create, restructure, review, or update repository ROADMAP.md files with an architecture-first presentation, evidence-backed status, Now/Next/Later priorities, dependency-aware milestones, measurable exit criteria, metrics, and task links. Use when Codex is asked to 创建路线图, 更新 roadmap, 整理项目规划, synchronize a roadmap with architecture or PRDs, or fix roadmap status drift.
---

# Manage Roadmap

创建或更新一份能同时表达产品方向、目标架构和执行顺序的 `ROADMAP.md`。让路线图回答：系统要去哪里、为什么这样设计、现在先做什么、怎样证明完成。

## Resolve Scope

1. 用 `git rev-parse --show-toplevel` 确认仓库根目录；失败时使用当前工作目录。
2. 先读取仓库的 `AGENTS.md` 或等价入口规范，再按其路由读取必要标准。
3. 默认目标文件为仓库根目录的 `ROADMAP.md`；用户指定其他路径时服从用户。
4. 先检查目标文件和相关目录的 `git status` / `git diff`，保留用户已有改动。
5. 目标文件不存在时进入 **Create**；存在时进入 **Update**。

## Gather Evidence Progressively

只读取决定路线图所需的权威来源，不无差别加载整个仓库。按实际存在情况选择：

- 项目定位：`README.md`、产品说明、现有 `ROADMAP.md`；
- 目标架构：`docs/architecture/`、`docs/systems/`、架构决策记录；
- 当前任务：`tasks/pending/`、issue/PRD 目录或项目管理文件；
- 完成证据：`tasks/archive/`、验收清单、版本记录；
- 约束与质量指标：测试标准、评测文档、运维指标。

先在工作笔记中形成以下事实表，再编辑文件：

| 事实 | 必须回答 |
|------|----------|
| 项目定位 | 当前解决什么问题，长期演进为什么系统 |
| 架构枢纽 | 哪个契约、数据模型或平台边界支撑后续能力 |
| 当前主线 | 眼下唯一或最主要的业务结果是什么 |
| 依赖链 | 哪些工作必须先完成，哪些可以并行 |
| 状态证据 | 哪些已完成、正在进行、仅是候选 |
| 验收方式 | 每个近期里程碑如何通过真实入口证明 |

若优先级会因一个缺失的业务选择而发生实质变化，向用户确认；否则根据明确标注、活跃 PRD 和依赖关系作保守推断，并在文档中避免伪造承诺。

## Preserve Source-of-Truth Boundaries

- Roadmap 是优先级、结果和验收入口，不是详细架构契约的第二份真源。
- 架构细节链接到权威文档；Roadmap 保留理解路线图所必需的完整架构图和不变决策。
- 任务状态以仓库约定的 pending/archive、issue 状态或验收证据为准。
- 不手写易漂移的“共有 N 个任务”；需要数量时动态计算或省略。
- 不因文件名存在就声称完成；确认归档位置或验收状态。
- 同一任务同时出现在 active 与 archive 时，报告漂移并选择证据更完整的状态；未经授权不移动或删除任务文件。
- 不把长期工程规范、明确的 `Won't fix` 或已完成事项继续列为技术债务。

## Put Architecture First

目标架构图必须紧跟项目定位和更新时间，先于状态约定、执行摘要和里程碑。推荐顺序：

```text
项目定位
→ 目标架构图
→ 不变的架构决策
→ 文档职责与状态约定
→ Now / Next / Later / Not now
→ 当前关键路径
→ 交付里程碑
→ 指标
→ 风险与技术债务
→ 已完成基础能力
```

架构图应帮助读者理解后续任务为何存在。按项目实际情况呈现：

- 输入和外部参与者；
- 可替换 provider / engine；
- 稳定的中间契约或系统枢纽；
- 主要分支及各自输出；
- 配置、Schema、spec 等声明式输入；
- canonical 中间态与版本化输出；
- 尚未实现的 adapter 或外部副作用边界；
- 实线与虚线表达“当前已连接”和“未来能力”的区别。

不要为了减少行数把具有不同职责的节点合并。尤其不要混淆：

- 解析与业务理解；
- 物理/版面 IR 与语义 IR；
- 识别 Schema 与 target spec；
- canonical 数据与目标 payload；
- payload 校验与真实 Delivery；
- 给人看、给机器和保版翻译等不同输出支路。

更新既有 Roadmap 时，默认保留用户已有架构图的语义密度、分组和关键标签。只有架构事实变化、图存在错误或用户明确要求简化时才重画；重画后逐项核对原图节点与边是否仍可表达。

## Express Execution Clearly

### Use one status vocabulary

除非仓库已有约定，使用：

| 状态 | 含义 |
|------|------|
| ✅ 已完成 | 有验收证据并已归档 |
| 🚧 当前 | 当前交付主线 |
| 🧭 下一步 | 当前主线完成后进入交付 |
| 💡 候选 | 方向成立但未承诺时间或资源 |
| ⏸ 暂不做 | 有意后置，需满足触发条件 |

### Separate technical direction from delivery priority

明确区分：

- “技术上最自然的下一步”；
- “产品或业务上当前真正的下一步”。

两者冲突时，以当前业务结果决定执行顺序，并把技术方向保留为候选或进入条件。

### Show the critical path

使用一个小型 Mermaid 流程图或依赖列表表达近期关键路径。只放影响执行顺序的节点，不复制完整架构图。

### Make milestones verifiable

每个当前或下一步里程碑至少包含：

1. **结果**：用户或系统获得什么；
2. **完成标准**：哪些真实证据证明完成；
3. **依赖/进入条件**：为什么现在做或为什么尚不能做；
4. **执行入口**：对应 PRD、issue 或任务链接；
5. **非通过条件**：必要时明确静默吞错、伪成功、硬编码样本等不可接受做法。

优先写结果和证据，不把“完善、增强、优化、支持”等能力名当成完成标准。

### Avoid false precision

- 近期已有承诺和资源依据时可以写月份；
- 中期优先写季度或 `Next`；
- 远期写 `Later` / `Candidate`；
- 没有依据时不编造日期、负责人、预算或数值目标；
- 指标尚无基线时，要求活跃 PRD 建立基线和目标，不在 Roadmap 中拍脑袋填数字。

## Create a New Roadmap

1. 使用 [`assets/ROADMAP.template.md`](assets/ROADMAP.template.md) 作为骨架，不逐字照搬示例内容。
2. 先替换项目定位与目标架构，删除不适用的节点和支路。
3. 从真实任务与架构依赖推导 `Now / Next / Later / Not now`。
4. 只把有证据的事项标记为已完成。
5. 为当前和下一步里程碑补齐结果、完成标准、进入条件与任务链接。
6. 将长期完成记录压缩为能力摘要，避免把 Roadmap 写成 Changelog。

## Update an Existing Roadmap

1. 完整读取现有 Roadmap，先理解作者的结构和关键技术判断。
2. 对照任务目录、架构文档和最新验收证据，列出状态漂移。
3. 优先做最小必要调整；不要因为套用模板而删除项目特有信息。
4. 将架构图移到项目定位之后，但保留原图的关键边界、分支和标签。
5. 解决互相竞争的“当前主线”，把执行顺序写成依赖链。
6. 为模糊条目补充 Outcome、Exit Criteria、Dependency 和执行入口。
7. 压缩重复架构正文、完成流水账和缺少退出标准的技术债务。
8. 更新日期，但不要把文档更新时间冒充功能完成时间。

## Validate Before Delivery

至少执行：

1. `git diff --check`；
2. 检查所有本地 Markdown 链接是否存在；
3. 确认目标架构图只出现一次且位于项目定位之后；
4. 核对 Mermaid 节点、分支、实线/虚线和标签没有在重排时丢失；
5. 搜索已经归档却仍标为未完成的项目；
6. 搜索手写任务数量、过期日期和互相冲突的“当前主线”；
7. 使用仓库既有 Markdown/MkDocs/文档校验命令；若严格校验受既有问题阻塞，区分本次问题与既有问题；
8. 用 `git status --short` 确认只修改授权范围内的文件。

最终说明修改了哪些信息层级、状态漂移和优先级表达，并如实报告验证结果。除非用户明确要求，不执行 `git add`、`git commit` 或 `git push`。
