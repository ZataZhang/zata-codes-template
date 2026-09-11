# Guard Tests 守卫测试

本目录存放**守卫测试**（guard tests）：它们守护仓库自身的约定、hook 行为、
构建脚本契约和公共 API 契约，而不是业务功能逻辑。业务功能测试放在 `tests/`
根目录或 `tests/backend/`。

## 目录划分：所有权边界

本仓库是会被分发（sync）到派生项目的模板源，因此本目录按**被测对象的所有权**
划分子目录，与 `hooks/shared/`、`scripts/shared/` 的 shared 前缀约定同构：

- `tests/guards/shared/` — 守护 **upstream-owned** 代码（`hooks/shared/*`、
  `scripts/shared/*`、`scripts/build/*` 等）的守卫测试，随 sync 一起分发到
  派生项目，与被守护的 shared 代码走同一条分发生命周期。
- `tests/guards/` 根目录 — 守护**项目自有**对象（`src/`、`alembic/`、根目录
  compose/env 模板、`pyproject.toml`、`skills/` 等）的守卫测试，不进 sync
  分发面。

新增守卫测试时按被测对象归位；两个目录的守卫测试同等生效，划分只影响
sync 分发范围。

## 核心规则

**守卫测试失败时，修复触发它的源代码、配置或脚本，不要修改本目录下的测试
文件来让测试通过。** 修改守卫测试让失败消失，等于拆掉规则本身——失败本来
就是在告诉你有人破坏了约定。

仅当**约定本身需要变更**时才修改本目录的测试，且必须同步更新对应的约定
文档（见下表）。

## 为什么单独放一个目录

守卫测试和业务测试混在一起时，AI 编码代理无法区分二者：它的默认目标是
"让测试通过"，而改测试是最短路径。把守卫测试集中到 `tests/guards/` 并在每个
文件头标注 guard test，是为了让代理第一眼识别出"这是规则本身，不是被规则
约束的对象"。详见 `docs/ai-standards/testing.md` 的 Guard Tests 小节。

## 提交保护

修改本目录文件会触发 pre-commit hook `check-guard-test-modification`：默认
拒绝提交，提示你确认这是有意的规则更新。确认后设置环境变量再提交：

```bash
GUARD_UPDATE_ACK=1 git commit ...
```

AI 代理默认不会设置该变量，因此会被 hook 拦下——这是"指令被忽略"时的最后
一道硬门禁。

## 守卫测试清单

### shared/（upstream-owned，随 sync 分发）

| 文件 | 守护对象 |
|---|---|
| `shared/test_archive_tasks.py` | PRD 归档 hook（`hooks/shared/archive_tasks.py`） |
| `shared/test_check_max_file_lines.py` | 单文件行数上限 hook（`hooks/shared/check_max_file_lines.py`） |
| `shared/test_check_schema_conventions.py` | schema convention hook（`hooks/shared/check_schema_conventions.py`）：迁移脚本命名校验、分隔符与 revision 一致性 |
| `shared/test_duplication_check_utils.py` | duplication-check 共享 git helper（`hooks/shared/duplication_check_utils.py`） |
| `shared/test_gc_worktree_databases.py` | Worktree 数据库 GC 脚本（`scripts/shared/worktree/gc_worktree_databases.py`） |
| `shared/test_quality_flag_hooks.py` | quality / test flag hook 行为（`scripts/shared/hooks/`） |
| `shared/test_release_script.py` | release 归档排除规则（`scripts/shared/release.py`） |
| `shared/test_run_jscpd_duplication_check.py` | jscpd 增量重复检查 hook 逻辑（`hooks/shared/run_jscpd_duplication_check.py`） |
| `shared/test_setup_copied_database.py` | Worktree 专用数据库派生与建库脚本契约（严格模式不静默回退共享库、日志不吐凭据） |
| `shared/test_sync_template.py` | template sync 脚本（`scripts/shared/template/sync_template.sh`），含 upstream-owned 清单契约 |
| `shared/test_whats_new_manifest.py` | what's-new manifest 构建脚本（`scripts/build/build_whats_new_manifest.py`） |

### 根目录（项目自有，不随 sync 分发）

| 文件 | 守护对象 |
|---|---|
| `test_alembic_logging_isolation.py` | 进程内 alembic 迁移不得摧毁宿主进程 logging 配置（`fileConfig` 清空 root handler、禁用已有 logger，会让 `caplog` 断言静默恒为空） |
| `test_alembic_migration_naming.py` | `alembic.ini` 的迁移脚本命名约定：`file_template` 与 slug 归一化（`docs/database/migrations.md`）；hook 行为部分见 `shared/test_check_schema_conventions.py` |
| `test_compose_parity.py` | Docker Compose 仓库约定 |
| `test_composition_boundaries.py` | composition root 公开入口，以及四层反向导入 composition 必须被架构检查拒绝 |
| `test_database_connection_pool.py` | 非 SQLite 后端不得使用 `StaticPool`（共用单连接会让事务互相覆盖、静默丢数据） |
| `test_dokploy_environment.py` | 部署环境模板（env/compose 一致性） |
| `test_migrations.py` | Alembic 迁移链完整性 |
| `test_openapi_schema.py` | 公开 HTTP 契约（OpenAPI schema） |
| `test_prd_skill_checker.py` | PRD 归档 checker 的证据链约束（缺关键值来源/必经边界/fresh-state probe 必须拒收）；被测对象是模板内部 skill 产物 |
| `test_realdb_marker_required.py` | 写真实数据库的测试必须打 `realdb` 标记（`docs/ai-standards/testing.md`） |
| `test_realdb_xdist_manifest.py` | `_REALDB_TEST_FILES` 清单必须与模块级 realdb 标记一致（`docs/ai-standards/testing.md`） |
| `test_runtime_dependency_declaration.py` | 模块级 import 必须由依赖声明覆盖：`src/backend/` 对齐裸 `uv sync`（`[project.dependencies]`），`tests/` 对齐 CI 的 `uv sync --all-extras --all-groups --frozen`（含 `[dependency-groups] dev` 与 extras） |
| `test_runtime_port_state.py` | `.env.run-state` 主机端口单一来源与 Compose 映射 |
