# Idea Inbox — 总结（AI 派生，可重写；事实以 ideas.md 为准）

_最后更新：2026-06-15 11:04_

## 主题聚类

- **模板工具链分层** — 将 `scripts/` 目录也按"模板共享 / 项目私有"分层，与已有的 `justfile` / `justfile.shared` 拆分保持一致（来源：2026-06-15 10:49）。

## 可执行候选

- 把会随 `just sync-template` 同步的脚本集中到 `scripts/shared/`，保留 `scripts/sync_template.sh` 作为项目私有包装器 → 建议 PRD：P2-REFACTOR，理由：范围清晰、与现有 justfile 分层对称、不影响 `hooks/` 和 pre-commit。（来源：2026-06-15 10:49）

## 待澄清问题

- 无。

## 已升级

- `Scripts 我觉得要不也抽一个模板scripts 文件夹,把会同步的都放在模板script文件夹里面` → `tasks/archive/P2-REFACTOR-20260615-110433-isolate-template-scripts.md`（来源：2026-06-15 10:49）
