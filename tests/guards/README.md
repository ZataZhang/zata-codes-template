# Guard Tests 守卫测试

本目录存放**守卫测试**（guard tests）：它们守护仓库自身的约定、hook 行为、
构建脚本契约和公共 API 契约，而不是业务功能逻辑。业务功能测试放在 `tests/`
根目录或 `tests/backend/`。

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

| 文件 | 守护对象 |
|---|---|
| `test_alembic_migration_naming.py` | Alembic 迁移脚本命名约定（`docs/database/migrations.md`） |
| `test_check_max_file_lines.py` | 单文件行数上限 hook |
| `test_quality_flag_hooks.py` | quality / test flag hook 行为 |
| `test_archive_tasks.py` | PRD 归档 hook |
| `test_run_jscpd_duplication_check.py` | jscpd 增量重复检查 hook 逻辑 |
| `test_duplication_check_utils.py` | duplication-check 共享 git helper |
| `test_whats_new_manifest.py` | what's-new manifest 构建脚本 |
| `test_openapi_schema.py` | 公开 HTTP 契约（OpenAPI schema） |
| `test_release_script.py` | release 归档排除规则 |
| `test_sync_template.py` | template sync 脚本 |
| `test_dokploy_environment.py` | 部署环境模板（env/compose 一致性） |
| `repo/test_compose_parity.py` | Docker Compose 仓库约定 |
| `repo/test_migrations.py` | Alembic 迁移链完整性 |
