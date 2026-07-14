# Alembic Migration Standards

本页定义本仓库 Alembic 迁移脚本的命名与生成约束。

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
