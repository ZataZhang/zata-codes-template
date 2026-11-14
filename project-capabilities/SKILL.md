---
name: project-capabilities
description: "模板仓库专用的项目初始化能力目录。用户明确选择某个组件，并提供目标项目路径时，读取对应组件的 README 与 overlay 后按需复制。此 Skill 仅通过模板仓库路径显式调用，不安装到全局 Skill 目录，也不复制进派生项目。"
---

# Project Capabilities

此目录保存供派生项目初始化或扩展时选择的组件源码。它不是模板项目的运行时模块，也不是 `skills/` 下可安装的全局 Skill。

## 使用方式

用户明确选择能力后：

1. 检查目标项目的后端分层、配置加载、composition root、授权流程、前端入口与现有对象存储实现。
2. 读取该组件自己的 `README.md`，确认其前置条件、文件边界、依赖和验证步骤。
3. 只复制用户选择的 `overlay/` 文件；不复制组件说明、该目录入口 Skill 或其他组件。
4. 按目标项目现有约定实现领域授权、业务记录、API 路由与前端调用，并执行组件说明中的验证。
5. 向维护者列出复制文件、改动的集成点、需要配置的环境变量和未执行的真实外部验证。

若用户没有选择能力，仅介绍可用目录，不修改目标项目。

## 现有组件

- [对象存储直传直取](components/object-storage-delivery/README.md)：core 对象存储端口与阿里云 OSS adapter。项目自行控制授权、对象键与业务关系。

## 分发边界

- `just sync-local-skills` 只从仓库根级 `skills/` 安装 Skill。
- `just copy` 与 `scripts/sync_template.sh` 必须排除 `project-capabilities/`。
- 不要把这里的 Skill 复制到 `~/.codex/skills/`、`~/.agents/skills/` 或其他工具的 Skill 目录。
- 目标项目只接收其明确选择的组件源码；能力目录本身不进入派生项目。
