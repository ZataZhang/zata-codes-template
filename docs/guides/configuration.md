# 配置说明

本项目通过 `utils/settings.py` 中的 `AppSettings` 统一管理配置，并组合多个子配置模型，实现工程化的配置分层。

## 配置来源优先级

总优先级从高到低：

1. 环境变量（含 `.env` / `.env.local`）
2. `config.toml`
3. 代码默认值

## 关键配置模块

- **应用层配置**：应用名、日志级别、日志目录。
- **数据库配置**：后端类型、主机、端口、库名、驱动。
- **模型配置**：默认聊天模型提供商、模型名和温度。
- **基础设施配置**：MinIO、Qdrant、Embedding、Chunking、Timeout 等。

## 常用实践

- 推荐在 `.env` 中存放密钥与敏感信息。
- 推荐在 `config.toml` 中维护非敏感默认项。
- 所有业务代码统一从 `config` 实例读取，不直接散落调用 `os.getenv`。

## 日志相关配置

日志位于 `logs/` 目录，默认文件为 `logs/app.log`，并通过 `TimedRotatingFileHandler` 按天切分。

## 数据库 URL 解析

`AppSettings.resolved_database_url` 支持：

- 直接使用 `DATABASE_URL`。
- 在未提供完整 URL 时，通过组件拼接生成连接字符串。
