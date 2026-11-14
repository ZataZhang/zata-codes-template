# 模板项目能力目录

`project-capabilities/` 保存仅供模板维护阶段显式选择的组件源码与接入说明。目录里的 Skill 只通过仓库路径读取，不安装到 Codex、Claude 或其他工具的全局 Skill 目录，也不复制进派生项目。

## 派生项目接入

只有用户明确选择能力后，才读取对应组件 README 并复制其 `overlay/` 中被选定的源码。先核对目标项目的后端分层、配置加载、composition root、业务授权和前端入口，再按目标项目自己的领域模型接入。Skill 和组件 README 不作为目标项目运行时依赖。

当前提供的组件：

- `project-capabilities/components/object-storage-delivery/README.md`：core 对象存储端口、阿里云 OSS adapter、可选配置与 CORS/CDN 接入说明。此源文件位于模板仓库维护目录，不会进入 MkDocs 发布文件集。

## 分发与维护

- 根级 `skills/` 是 `just sync-local-skills` 和 `scripts/sync_template.sh --local-skills` 的唯一 Skill 扫描源；不要把项目能力 Skill 移入该目录。
- `just copy` 和 `scripts/shared/template/sync_template.sh` 都排除根级 `project-capabilities/`，包括 `--all` 候选列表。
- 复制能力时只把用户选中的 overlay 文件放进目标项目。更新模板组件不会自动回迁已存在项目的 `src/backend/`；后续更新由项目维护者显式再次应用。
- 新增能力时，为每个组件保留独立 README、源码 overlay 与验证说明；只有模板专用通用规则才写在本页。
