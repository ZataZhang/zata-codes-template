# 证据报告：回迁下游已验证的本地测试分层与共享库守卫到模板

PRD：`tasks/pending/P2-PERF-20261004-235405-backport-local-test-tier-and-shared-db-guard.md`
证据目录：`tasks/evidence/P2-PERF-20261004-235405-backport-local-test-tier-and-shared-db-guard/`（原始产物仅本地保留，见 `docs/ai-standards/testing.md`「证据留存策略」）

## 人审导航（§9.1 呈递物）

| 观察对象 | 呈递物 | 10 秒自检 |
|---|---|---|
| 10 天观察结论（是否开工） | `rv-1-observation.md` | 三项判据各有一条结论：**一项无法核对、一项有真超限但非误报、一项无反例**；总判定是「带保留地开工」，与 PRD §2 决策三的「任一项不成立则不开工」并不完全对得上，由维护者指示补足 |

> 这条判定需要人确认的点：第一项（本地核心档耗时稳定）没有观察记录，不是「观察到通过」。维护者已于 2026-10-16 明确指示回迁，但 `Human-Confirmed` 的决策三仍留给人在验收时勾选。

## 证据与验收项映射

### rv-1（人工 / R2）观察结论 —— `rv-1-observation.md`

- 做了什么：用 `gh run list/view` 与 `git log` 核对下游 `ai-assistant` 在 2026-10-04 → 2026-10-14 的 CI 与提交。
- 显示了什么：棘轮在 10-08 到 10-09 因 main 已超旧上限而连续变红（真超限，非误报），10-09 配对上调后不再红；守卫窗口内无修复提交；本地耗时无记录。
- 为什么支持验收项：三项判据各有结论与可解析的运行 / 提交标识；负控方向（出现误报则应得出「不开工」）在文末逐条核对。**保留**：第一项为「无法核对」。

### rv-2（R1）冷树默认本地测试 ≤30s 且含改动相关测试 —— `rv-2-3-core-tier.txt`

- 做了什么：`scripts/rv2_rv3_core_tier.sh` 把当前工作树拷成一个干净的快照 git 仓库（无 test / lint 标记 = 冷树），向 `src/backend/api/admin/run_trace_router.py` 追加一行注释作为已知改动，真实执行 `just test`。
- 显示了什么（最终树，第二次运行）：
  - `MAPPED_TEST_IN_RUN_SET: yes (tests/backend/test_admin_run_trace_api.py)`——该测试**不在** `tests/core_set.txt`，是被改动映射进来的；
  - `just test` 退出码 0，**含 lint 前置共 13.9s**，其中 pytest 为 `524 passed, 1 skipped in 6.99s`；
  - 同一棵树不再改动再跑 `just test`，命中 warm flag，0.9s 返回 0。
- 判别力：映射项是否在运行集合里由 `--collect-only` 的真实输出判定；若 `pytest_ignore_collect` 的工作区计划接线断了，该测试不会出现（守卫 `test_local_core_tier_budget.py::test_core_tier_covers_changed_and_mapped_tests` 另钉这条接线）。
- **降级披露**：没有用 `just worktree`。实现尚未提交，worktree 从 HEAD 建出来看不到新机制；主仓工作区里还有一整批未提交改动，会让映射集合混入无关项。快照仓库与主仓共用 `.venv` 与同一份 `.env.local`。

### rv-3（R1）定点补跑 —— `rv-2-3-core-tier.txt`

- 做了什么：同一快照仓库里先打印 `test_tiers.py changed --fallback-core` 的选集，再真实执行 `just test-changed`。
- 显示了什么：选中 3 个路径，含映射到的 `tests/backend/test_admin_run_trace_api.py`（以及 `test_run_trace_export.py`、`test_run_trace_projection.py`）；`mapped test is NOT in core_set.txt`，说明选择来自改动映射而不是名单裁剪；`24 passed`，退出码 0。
- 发现并修复了一个下游缺陷：下游的 `test-changed` recipe 含 `${#selected_paths[@]+x}` 判空，在 macOS 自带 bash 3.2 下报 `bad substitution`，首次回迁运行就是红的（见本轮早先的运行记录）。模板版删除该冗余判空；此缺陷另报下游。

### rv-4（R2）成本棘轮 —— `rv-4-budget.txt`

- 做了什么：`scripts/rv4_budget.sh`。正常样本是 `just test-budget` 真实跑全量档产出的 junit；超限样本是在临时目录构造的 junit。
- 显示了什么：
  - 正常样本：738 条 / 上限 850、42.3s / 上限 75s，本机退出码 0，墙钟行注明「仅供参考」；带 `--enforce-seconds` 同样通过；
  - 条数 950 > 850，**不带强制开关**也退出码 1（条数任何环境强制），并打印「超上限的处理方式」；
  - 墙钟 200s > 75s：不带开关退出码 0 且注明仅供参考，带 `--enforce-seconds` 退出码 1；
  - 恰好等于上限（850 / 75）通过。
- 最终树静态断言：`ci.yml` 的全量步骤带 `--junit-xml=.test-budget-junit.xml`，末尾的 `Check full-tier test budget` 步骤调用 `scripts/shared/testing/check_test_budget.py ... --enforce-seconds`；守卫 `test_ci_enforces_full_tier_budget_including_seconds` 解析 YAML 钉住这一点。
- 披露：模板 CI 上的首次棘轮运行尚未发生；`baseline.tests = 745` 是估算（CI 692 + 新增 53），首次 CI 后需复核。

### rv-5（R2）库名不同放行 / rv-6（R2）同库与旧格式拦截 + 负控 —— `rv-5-6-guard.txt`

- 做了什么：`tests/guards/test_shared_database_guard.py` 用**真实本地监听 socket** 与**真实 run-state 文件**触达 `tests/conftest.py` 的 `_guard_shared_database_external_writer`；只有「本次测试写哪个库」用 monkeypatch 固定。
- 显示了什么（最终树，8 passed）：库名不同放行；同库拦截并在提示里带库名与 `ALLOW_SHARED_DATABASE`；旧格式（无 `DATABASE_NAME`）保守拦截；同库但端口无监听者放行；`ALLOW_SHARED_DATABASE=1` 放行；项目未提供活跃运行钩子时不崩溃且不影响端口 + 库名信号；钩子报告活跃运行时拦截；钩子抛 SQLAlchemy 错误时不拦。
- 负控（临时改写 conftest 判据、跑完立即还原，不碰生产代码）：
  1. 把判据改成「只看端口」→ `test_listener_on_a_different_database_does_not_block` **FAILED**；
  2. 删掉旧格式保守分支 → `test_legacy_run_state_without_database_name_blocks_conservatively` **FAILED**；
  3. 还原后复跑回到 8 passed。两次红灯都是用例失败（断言），而不是会话被终止——为此把守卫测试改成「捕获 `pytest.exit` 再断言」。
- `just run` 侧契约：`tests/guards/test_runtime_port_state.py` 用真实 `just run backend backend_cmd=env` 与临时 `.env.local` 验证 run-state 写入 `DATABASE_NAME=guard_test_db`。

### 架构 / 文档验收 —— `static-assertions.txt`

- `_is_upstream_owned` 对 `scripts/shared/testing/*`、`tests/guards/shared/test_test_tiers.py`、`test_check_test_budget.py`、`docs/ai-standards/*` 均判 owned（随 sync 分发）；`tests/conftest.py`、`justfile`、`tests/core_set.txt`、`test-budget.json` 判 project（项目自有）。
- 模板 conftest 不含下游业务词（`agent_run` / `reconcile_expired` 等）；业务探测只经可选钩子 `find_live_nonterminal_runs` 外置，模板的 `realdb_test_support.py` 不定义它。
- 文档引用的符号、环境变量与 recipe 在代码里都存在，6 个 recipe 都在 `tooling.md` 命令表里；无「三层防线」「scripts/dev/test_tiers」等旧描述残留。

### 交付门禁

| 命令 | 结果 | 证据 |
|---|---|---|
| `just lint --reuse` | exit 0 | `final-lint.txt` |
| `just lint --full` | exit 0 | `final-lint.txt` |
| `just test` | exit 0，`525 passed, 1 skipped in 7.43s`（核心档） | `final-just-test.txt` |
| `just test all` | exit 0，`740 passed, 6 skipped in 41.34s` | `final-just-test-all.txt` |
| `uv run mkdocs build --strict` | exit 0 | `final-mkdocs.txt` |

## 验收清单对照

- 架构：共享脚本落在分发面 ✔；守卫通用化拆分 ✔（证据：`static-assertions.txt`）
- 依赖：门禁已解除，三项判据 **带保留** 成立（证据：`rv-1-observation.md`）
- 行为：核心档（rv-2）✔、定点补跑（rv-3）✔、棘轮（rv-4）✔、守卫（rv-5 / rv-6）✔
- 文档：`testing.md` 的「测试分层与本地核心档」与「与 dev server 共用数据库」与实现一致 ✔
- 验证：真实 CLI 入口（rv-2，降级为快照仓库）✔；守卫真实监听（rv-5 / rv-6）✔
- 交付记录路径：PRD 与证据目录不计入代码 diff；RV 脚本只在证据目录 `scripts/` 下 ✔

## 未覆盖与已知限制

1. 没有真实 `just worktree` 验证（见 rv-2 降级披露）。
2. 模板 CI 首次棘轮运行未发生，`baseline.tests` 为估算。
3. rv-1 第一项（本地耗时稳定）无观察记录。
4. 本地并行度 `-n4` 与 `-n auto` 的取舍沿用下游结论，未在模板上另做对比。
5. 下游 `test-changed` 缺陷（bash 3.2 判空）已在模板修复，尚未向下游提交修复。

## Open Items For Human Review

- `Human-Confirmed` 四项（决策一、二、三与 §9.1 呈递方式）留给人勾选；决策三请特别看第一项「无法核对」的取舍。
