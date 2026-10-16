# 验证计划：回迁下游已验证的本地测试分层与共享库守卫到模板

PRD：`tasks/pending/P2-PERF-20261004-235405-backport-local-test-tier-and-shared-db-guard.md`
所有命令的原始输出已 `tee` 进本目录；可重跑脚本在 `scripts/`。

| 验收项 | 可执行验证 | 证据文件 | 最高可行保真度 |
|---|---|---|---|
| rv-1 观察结论 | 人工整理下游 `gh run list/view` 与 `git log` | `rv-1-observation.md` | 真实 CI 记录；结论为「带保留地开工」，本地耗时一项无记录可核 |
| rv-2 默认本地测试冷树 ≤30s 且含改动相关测试 | `bash scripts/rv2_rv3_core_tier.sh`：把工作树拷成干净快照仓库，注入一行改动，真实执行 `just test` 两次 | `rv-2-3-core-tier.txt` | 真实 CLI 入口（`just test`），**降级**：用快照仓库而非 `just worktree`（实现未提交，worktree 看不到新机制；主仓未提交改动会污染映射集合） |
| rv-3 定点补跑 | 同一脚本：`test_tiers.py changed` 选集 + 真实执行 `just test-changed` | `rv-2-3-core-tier.txt` | 真实 CLI 入口 |
| rv-4 成本棘轮 | `bash scripts/rv4_budget.sh`：`just test-budget` 真实全量 junit 过检；构造 junit 样本做超限负控 | `rv-4-budget.txt` | 真实脚本 + 真实 junit；负控样本为构造的 junit，不改生产代码 |
| rv-5 / rv-6 守卫库名判据 | `bash scripts/rv5_rv6_guard.sh`：真实本地监听 socket + 真实 run-state 文件触达 conftest 守卫；两个负控临时改写判据后立即还原 | `rv-5-6-guard.txt` | 真实监听与真实代码路径；负控靠临时改写 conftest 判据得红 |
| 架构：分发面 / 守卫无业务耦合 / 文档一致 | `bash scripts/static_assertions.sh` | `static-assertions.txt` | 静态断言 |
| 交付门禁 | `just lint --reuse`、`just lint --full`、`just test`、`just test all`、`uv run mkdocs build --strict` | `final-just-test.txt`、`final-just-test-all.txt`、`final-mkdocs.txt` | 真实命令；lint 输出见证据报告 |

## 未覆盖与披露

- **没有用 `just worktree` 做真实 worktree 验证**：实现尚未提交，见上表 rv-2 的降级说明；快照仓库同样是「无 test/lint 标记的冷树」，且与主仓共用 `.venv` 与同一份 `.env.local` 数据库。
- **模板 CI 上的首次棘轮运行尚未发生**：`test-budget.json` 的 `baseline.tests = 745` 是 CI 692 + 新增 53 条的估算，需首次 CI 运行后复核。
- rv-1 的第一项（本地耗时稳定）没有观察记录，见 `rv-1-observation.md`。
