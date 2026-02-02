---
name: mkdocs-docs-writer
description: Generate or improve MkDocs documentation (Material for MkDocs) for a Python project. Use when asked to create or update mkdocs.yml, write docs under docs/, analyze code structure for documentation, or reorganize documentation in Chinese by default.
---

# Mkdocs Docs Writer

## Overview

Generate or improve a project's MkDocs documentation with the Material theme, focusing on accurate, code-backed content and a clear navigation structure.

## Workflow

### 1. Inspect project structure

- List key directories and entry points (e.g., `src/`, `main.py`, `pyproject.toml`, `README.md`).
- Identify public modules, CLI entry points, and configuration files.
- Avoid fabricating APIs; document only what exists.

### 2. Evaluate `mkdocs.yml`

- If missing, create a complete configuration with:
  - `site_name`, `theme: material`, and language settings.
  - `nav` aligned to actual docs and modules.
  - Common plugins: `search`, `minify` (if available).
- If present, update `nav` based on new/changed docs.

### 3. Write or update docs (Chinese by default)

Create or update markdown files under `docs/` with:

- 简介（项目概览、目标用户）
- 安装与快速开始（基于 `pyproject.toml`/`README`）
- 核心模块/功能（按模块拆分，含代码示例）
- 配置说明（读取现有配置项）

Use fenced code blocks with language identifiers.

### 4. Suggest docs structure cleanup

If `docs/` is messy, propose a clear structure (e.g., `index.md`, `getting-started.md`, `api/`, `config/`, `guides/`) and map existing files to it.

## Output Rules

- Use standard Markdown.
- Default language: Chinese (unless user requests otherwise).
- Provide Mermaid flowcharts only when the process is complex enough to benefit.
- Keep tone professional and concise.
