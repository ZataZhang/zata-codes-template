# 快速开始

本文档说明如何在本地初始化并运行该模板项目。

## 环境要求

- Python 版本：`>=3.14`
- 包管理器：`uv`
- 推荐任务工具：`just`

## 安装依赖

安装主依赖和开发依赖：

```bash
just sync
```

首次启动开发环境（含 pre-commit hook 安装）：

```bash
just dev
```

## 运行项目

```bash
just run
```

## 测试

运行默认本地测试集：

```bash
just test
```

运行完整测试集：

```bash
just test all
```

## 文档预览

本项目已集成 MkDocs：

```bash
just docs-serve
```

构建静态文档：

```bash
just docs-build
```

## 目录说明

- `utils/`：通用配置、日志、数据库与工具函数。
- `ai_agent/`：模型配置加载和 AI Agent 相关工具。
- `crawler/`：爬虫基础组件、示例模型和辅助逻辑。
- `tests/`：单元测试与集成测试。
- `docs/`：项目文档源目录。
