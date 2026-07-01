# 迁移规范

当前模板通过 SQLAlchemy `Base.metadata.create_all` 演示表结构初始化，适合作为快速起步。

## 推荐迁移策略

- 开发早期：可使用 `create_all` 快速验证模型。
- 进入协作期后：建议引入 Alembic 管理版本化迁移。

## 迁移流程建议

1. 修改 SQLAlchemy 模型。
2. 生成迁移脚本。
3. 审核迁移脚本并执行测试环境迁移。
4. 在生产环境按窗口执行迁移并验证。

## 规范建议

- 每次迁移保持目标单一，避免一次改动过大。
- 在迁移说明中写明回滚方案。
- 对大表结构修改做好锁表与耗时评估。

## 文件命名规范

迁移脚本必须使用以下命名格式，便于在协作中口头引用：

```text
YYYYMMDD-HHMMSS-<slug>.py
```

示例：`20260617-153045-add_user_email_index.py`

规则：

- 由 `alembic revision -m "<message>"` 自动生成，模板定义在 `alembic.ini` 的 `file_template`。
- `<message>` 必填，**禁止空消息**（执行 `alembic revision` 时必须带 `-m`）。
- 文件名中的 `<slug>` 会被 Alembic 自动归一化为 snake_case：取 `<message>` 中的 `re.findall(r"\w+", message)` 后用下划线连接并转小写（`alembic/script/base.py:771`）。例如 `-m "Add user email index"` → `add_user_email_index`，`-m "add-user-email-index"` → `add_user_email_index`（连字符被切掉），`-m "AddUserEmailIndex"` → `adduseremailindex`（驼峰会粘连，不推荐）。
- 写 `<message>` 时按自然语言短句写即可，**不必**手工替换分隔符；动词优先，如 `Add user email index`、`Create orders table`、`Backfill user display name`、`Drop legacy column foo`。
- 时间戳精确到秒；**省略 Alembic 默认的 12 位 hash 段**——文件内的 `revision` 变量仍由 Alembic 自动生成以保证唯一性，文件名上的 hash 反而降低可读性。
- 同一秒内若出现重名，追加 `-2`、`-3` 等后缀手工解决。

## 自动化检查

提交前 `pre-commit` 会运行 `hooks/shared/check_schema_conventions.py`（注册为 `check-schema-conventions` hook），对 `alembic/versions/*.py` 强制执行以下约定：

- 文件名必须符合 `YYYYMMDD-HHMMSS-<slug>.py` 格式。
- `<slug>` 只能包含小写字母、数字和下划线，且不能以数字开头。
- 文件内 `revision` 变量长度不得超过 32 字符（Alembic 默认 `alembic_version.version_num` 列宽上限）。

派生项目若采用下划线分隔符或“文件名时间戳前缀即 revision”等额外约定，可在 `.pre-commit-config.yaml` 中调整该 hook 的参数：

```yaml
entry: uv run python hooks/shared/check_schema_conventions.py --filename-separator '_' --require-revision-equals-timestamp-prefix
```

## TODO

- TODO: 集成 Alembic 初始化脚手架。
- TODO: 增加迁移回滚示例脚本。
