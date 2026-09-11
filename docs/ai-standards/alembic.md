# Alembic Migration Standards

本页定义本仓库 Alembic 迁移脚本的命名、生成约束与 docstring 写法。

## File Name Format

新生成的迁移脚本必须使用：

```text
YYYYMMDD_HHMMSS_<slug>.py
```

- 时间戳取运行命令时本地 `date +%Y%m%d_%H%M%S`，必须精确到秒。
- `slug` 使用小写蛇形命名，并描述迁移目的。
- `revision` 必须等于文件名去掉 `.py` 后的时间戳前缀。
- `down_revision` 必须指向创建时 `alembic heads` 的唯一 head。

## Required Generation Entry Point

禁止手工创建、重命名或编造迁移时间戳。必须从仓库根目录执行：

```bash
just new-migration <slug>
```

该入口调用 `scripts/shared/alembic/new_migration.sh`，会验证版本图只有一个 head、调用 Alembic 模板生成文件，并同步文件名、`revision` 与 `down_revision`。只在生成后用补丁填写 `upgrade()` 和 `downgrade()`。

交付前执行：

```bash
uv run alembic heads
```

输出必须只有一个 head，且应为新迁移的 revision。

## Script Template & Docstring 写法（总分结构）

脚本模板（与 `alembic/script.py.mako` 生成结果一致，占位符 `<...>` 由编写者替换填充）：

```python
"""<slug> — <总分首句：一句话总结本次迁移改了什么（表 / 列 / 索引），及目的>

Revision ID: 20260625_145402
Revises: 20260627_000000
Create Date: 2026-06-25 14:54:02.000000

背景：<为什么需要这个变更；行为语义指向权威实现>

设计要点：<字段 / 索引 / 约束的分工与理由、锚点名称、方言差异>
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260625_145402"
down_revision: Union[str, Sequence[str], None] = "20260627_000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

模块 docstring 采用**总分结构**，读者扫迁移文件时第一需求是"这个文件动了什么"，
答案必须出现在首行；`upgrade()` / `downgrade()` 内部用编号注释说明步骤顺序理由
（如先删索引再删列的依赖顺序）。具体规则：

- **总（首行）**：`<slug> — 一句话总结变更内容（新增 / 修改 / 删除了哪些表、列、
  索引）+ 目的`。让读者不看正文就能知道迁移做了什么
- **分（正文）**：依次展开背景与动机、字段 / 索引 / 约束的分工与理由。容易产生的
  歧义（如"为什么需要两个语义相近的字段"）在正文里主动解释
- **行为语义不内联**：描述其他模块行为的内容（如"某服务写入时会带什么状态"、
  "某 API 的放行逻辑"）不要展开成细节清单——那些语义将来变化时没人会回来改迁移
  注释。压缩成一句，并指向权威实现的文件路径（如 use case 服务、模型定义）
- **写锚点**：索引名、约束名等在 docstring 里写明，让读者能把 docstring 与
  `upgrade()` 代码直接对应
- **方言差异写明**：部分索引、`server_default` 回填等在不同数据库间行为有差异
  的设计，说明兼容性理由
- **不写快照标注**：`Revises:` 行不要附 `(head)` 之类标注——迁移链推进后即失效
  （`new_migration.sh` 已在生成时剥掉该标注）

## Backfill Idempotency

回填型迁移（upgrade 中 UPDATE/DELETE 现有数据）必须容忍重复执行。`env.py` 的 `transaction_per_migration` 已防住 MySQL DDL 隐式提交导致的 version 滞后，但 `alembic_version` 仍可能因手动 `alembic stamp` 回旧版本、备份部分恢复或 downgrade 中断而落后于实际 schema；此时重跑迁移是正常路径，回填逻辑必须安全。

### 唯一约束下的回填陷阱

单条 `UPDATE` 在有唯一键时会逐行检查约束，目标值与未更新行的当前值在中间状态构成置换就会撞键：例如某 session 当前 `sequence = [1, 0, 2]`，`ROW_NUMBER()` 目标 = `[1, 2, 3]`，把第二行 `0 -> 2` 时第三行仍是 `2`，立即冲突。MySQL 逐行立即检查；PostgreSQL 默认 IMMEDIATE 唯一约束同样逐行检查（实测 PostgreSQL 17 亦报 `UniqueViolation`）。这是方言级陷阱，看 SQL 字面逻辑无法发现。

### 推荐写法

涉及唯一约束/唯一索引列的回填，用"先移除约束 -> 回填 -> 重建约束"模式，让回填不受约束限制；DDL 后刷新 inspector 再判断是否重建：

```python
if "uq_xxx" in existing_constraint_names:
    op.drop_constraint("uq_xxx", "table_name", type_="unique")
    inspector = sa.inspect(op.get_bind())  # DDL 后刷新，确保后续 create 判断反映最新 schema
op.execute(sa.text("UPDATE ... SET col = ROW_NUMBER() ..."))
if "uq_xxx" not in refreshed_constraint_names:
    op.create_unique_constraint("uq_xxx", "table_name", [...])
```

不涉及唯一约束的回填，也要保证重跑幂等：赋值在重跑时不变，或用 `WHERE col = <default>` 只处理未回填的行。downgrade 同样要可重跑。
