---
title: PRD - just implement 自动默认 Prompt
date: 2026-05-19
status: pending
tags: [tooling, justfile, developer-experience]
---

# PRD: just implement 自动默认 Prompt

## 背景

`just implement` 是创建 worktree 并从 PRD 启动 AI 辅助实现的便捷命令。原来必须传入三段参数：

```bash
just implement <prd-file> <clauded|kim> "<prompt>"
```

其中 prompt 为必填。但大多数场景下 prompt 内容完全可由 PRD 文件名推导（"请根据 PRD 实现该功能"），每次都要手动输入重复内容，操作冗余。

## 目标

让 `prompt` 参数可选。不传时自动生成默认 prompt，让用户只输 PRD 文件和 AI 工具名称即可快速启动实现。

## 变更范围

- 只涉及 `justfile` 中 `implement` recipe

## 具体变更

| 项目 | 改前 | 改后 |
|---|---|---|
| 参数签名 | `implement prd_file ai_tool prompt:` | `implement prd_file ai_tool prompt="":` |
| 空 prompt 处理 | 报错退出 | 自动默认 prompt |
| 默认 prompt | 无 | `请根据 PRD《{display_name}》的要求实现该功能，完成验收清单` |
| 用法注释 | 只列必填用法 | 新增不传 prompt 示例 |

分支名派生逻辑不变（与 PRD 文件名一致）。

## 验收清单

- [x] `prompt` 参数已改为可选（`prompt=""`）
- [x] 不传 prompt 时自动生成含 PRD 名称的默认 prompt
- [x] 传 prompt 时行为不变
- [x] 更新了 usage 注释
- [x] 已确认修改可运行（`just implement tasks/pending/xxx.md clauded` 不报错）
