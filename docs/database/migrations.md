# 迁移规范

当前模板通过 SQLAlchemy `Base.metadata.create_all` 演示表结构初始化，适合作为快速起步。
模板持久层目标支持 PostgreSQL 与 MySQL；进入 Alembic 迁移阶段后，两种数据库都属于
必须验证的目标，不能只在 SQLite 或单一生产数据库上验证迁移。

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
- 迁移代码默认保持 PostgreSQL / MySQL 兼容：优先使用 Alembic 与 SQLAlchemy API，避免裸写某一数据库专属语法。
- 确需使用方言专属 SQL 时，按 `op.get_bind().dialect.name` 分支实现等价行为，并在两种数据库上执行迁移验证。
- 新迁移应在 PostgreSQL 与 MySQL 上验证 `upgrade head`、关键回填结果及可支持的 downgrade；CI 矩阵是最终兼容性证据。

### PostgreSQL / MySQL 兼容性检查

审查迁移时至少检查以下项目：

1. `INSERT` 冲突语法、布尔值、JSON、日期时间、默认值和标识符引用是否依赖某个方言。
2. 索引、唯一约束、外键与列类型的 DDL 是否在两种数据库都支持，是否有名称长度或在线改表差异。
3. UPDATE/DELETE 回填是否参数化、可重跑，并避免违反立即检查的唯一约束。
4. upgrade 与 downgrade 是否都处理“目标行已存在”“源数据为空”和“部分执行后重跑”等状态。
5. 在 PostgreSQL 与 MySQL CI job 中实际执行迁移集成测试；SQLite 仅用于快速逻辑测试，不能替代这两个数据库的验证。

例如，要幂等创建由迁移拥有的固定 ID 行，可先 `SELECT` 检查该 ID，再用绑定参数插入；不要直接在公共路径写 PostgreSQL `ON CONFLICT` 或 MySQL `ON DUPLICATE KEY`。

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

注意 `--require-revision-equals-timestamp-prefix` 的期望值按**文件名分隔符**拼接（`date_part + separator + time_part`），因此只适用于 revision 与文件名同分隔符的项目。文件名与 revision 分隔符不一致的项目不能用这个 flag——每个文件都会被报成不合规——需改用项目自有的守卫测试来守护该约定。

## TODO

- TODO: 集成 Alembic 初始化脚手架。
- TODO: 增加迁移回滚示例脚本。
