# Idea Inbox

本仓库用 `tasks/inbox/` 承接"随手想法"：先逐字记录原话，再由 AI 维护一份总结。
它是任务生命周期的**第 0 阶段**，位于 PRD 之前：

```text
tasks/inbox/        →   tasks/pending/   →   tasks/archive/
随手想法：原话 + 总结      成形的 PRD          已交付的 PRD
```

## 为什么放在 tasks/inbox/

- `tasks/*` 在模板同步里"永不同步"（`scripts/shared/template/sync_template.sh` 的 `_is_never_synced`），所以每个项目的想法天然私有，不会串到其他派生项目。
- PRD 验收 hook 只校验 `tasks/` 根目录和 `tasks/archive/` 下的 PRD 文件（`hooks/check_prd_acceptance_checklist.py`），**不会扫描 `tasks/inbox/`**，因此这里可以自由记录、无需验收清单。
- 想法成熟后用 PRD 流程升级成 `tasks/pending/` 下的正式 PRD，形成闭环。

## 两层结构

inbox 里固定两类文件，职责严格分离：

| 文件 | 角色 | 谁来写 | 可否改写 |
|---|---|---|---|
| `tasks/inbox/ideas.md` | 原话日志 | 人（AI 代记时逐字转录） | **只追加，永不改写** |
| `tasks/inbox/summary.md` | AI 总结 | AI | 可随时重写 / 再生 |

想法的事实来源只有一个：`ideas.md`。`summary.md` 是派生产物，任何时候都可以从 `ideas.md` 重新生成。

## ideas.md：原话日志

- 追加式、按时间正序，最新条目追加在文件末尾。
- 每条想法一个二级标题，标题就是时间戳，可选加一个短标签：
  - `## 2026-06-14 18:30 · 标签`
- 标题下方逐字保留原话，**不要替用户润色、改写、纠错或精简**。
- 文件使用 UTF-8 编码；首次记录时若 `ideas.md` 不存在，直接按本页格式新建。

示例：

```markdown
## 2026-06-14 18:30 · 想法记录机制
> 我感觉我会有不断的想法冒出来，想要一个地方记录每一次想法的原话，同时让 AI 做总结。
```

### 给 AI 的硬性规则

- 当用户给出一段想法、或说"记一下 / 记录想法 / 帮我记下来"时：在 `ideas.md` **末尾追加**一条新条目，时间戳用当前本地时间，正文**逐字转录**用户原话。
- **禁止**编辑、合并、删除、重排或"优化"已有条目。原话是证据，不是草稿。
- 需要补充的解读、归纳或上下文，一律写进 `summary.md`，不要混进 `ideas.md`。

## summary.md：AI 总结

当用户说"总结一下想法 / 整理 inbox"，或在合适时机，AI 读取整份 `ideas.md`，重写 `summary.md`。建议结构：

- **主题聚类**：把零散想法归并到几个主题下，每条标注来源时间戳，便于回溯到原话。
- **可执行候选**：哪些想法已成熟到可以开 PRD，给出建议的优先级 / 类型。
- **待澄清问题**：还需用户拍板或补充信息的点。
- **已升级**：已进入 `tasks/pending/` 的想法，链接到对应 PRD。

`summary.md` 顶部应标明它是 AI 派生、可被重写，事实以 `ideas.md` 为准。

## 升级为 PRD

当某条想法值得动手时：

1. 用 PRD skill 在 `tasks/pending/` 下创建正式 PRD（命名与规范见 `skills/prd/SKILL.md`）。
2. 在 `summary.md` 的"已升级"区标注该想法对应的 PRD 路径。
3. 原话条目保留在 `ideas.md` 不动，作为需求溯源。

## 约定与边界

- 默认单文件 `ideas.md`；体量过大时可按年份滚动归档，例如把往年条目移到 `tasks/inbox/ideas-2025.md`，并在新文件顶部注明衔接。
- 想法内容是项目私有的，不随模板同步传播；新项目通过 `just copy` 只继承空的 `tasks/inbox/` 目录骨架和本约定，不继承任何已有想法。
- 本流程不引入新的命令、服务或 CI，它就是两个 Markdown 文件加一套读写约定。
