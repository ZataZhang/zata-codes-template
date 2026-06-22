# 评测与测试

本文档用于统一项目测试与 AI 能力评测实践。

## 测试命令

- 本地测试：`just test`
  - 默认排除标记为 `slow` 或 `real_api` 的测试，并使用 `pytest-xdist` 并行执行。
  - 如果当前分支、HEAD 与测试有效 tree 均未变化，会直接跳过测试并提示。
- 全量测试：`just test all`
  - 运行全部测试，不受默认 marker 过滤影响，仍使用 `pytest-xdist` 并行。
- 真实依赖测试：`just test real`
  - 只运行标记为 `real_api` 的测试，通常需要真实 API key 或外部服务。

## 测试标记约定

模板在 `pyproject.toml` 中定义了两个 pytest marker，供下游项目给测试分类：

- `@pytest.mark.slow`：真实 git、子进程、网络或其他重 I/O 导致的慢测试。
- `@pytest.mark.real_api`：需要真实 API key 或外部在线服务的测试。

日常开发使用 `just test` 即可跳过这两类测试；CI 或交付前使用 `just test all` 做全量回归。

## 测试分层建议

- **单元测试**：聚焦函数级逻辑，快速反馈。
- **集成测试**：覆盖模块协作边界。
- **真实环境测试**：针对依赖外部 API 的能力进行验证。

## AI 评测建议

- 建立黄金样本集并定期回归。
- 记录模型版本、Prompt 版本、评测时间和指标。
- 在 CI 中设置最低质量阈值。

## 建议指标

- 正确率或任务完成率
- 响应时延
- 稳定性与失败率
- 成本指标（按调用量或 token 统计）

## TODO

- TODO: 增加标准评测数据集格式。
- TODO: 增加自动化评测脚本入口。
