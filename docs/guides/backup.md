# 数据库备份与恢复

模板仓库不再自带备份服务。备份、恢复、S3 连通性诊断都迁到独立的
[`zata-ops`](https://github.com/zata/zata-ops) CLI。

## 1. 安装 `zata-ops`

```bash
cd /path/to/zata-ops
uv tool install --force .
zata-ops --version
```

`uv tool install` 会把 `zata-ops` 全局注册到 PATH 中。安装成功后，
`zata-ops --help` 会列出 `db backup`、`db restore`、`db list`、`db check`、
`db migrate` 等命令。

## 2. 配置当前项目的备份参数

在项目根目录的 `.env.local`（不要 commit）中添加：

```env
DATABASE_URL=postgresql+psycopg2://app:app@localhost:5432/app
S3_ENDPOINT=https://s3.us-east-005.backblazeb2.com
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=my-app-backups
S3_PREFIX=my-app-backups
S3_ADDRESSING_STYLE=path
RETENTION_DAYS=30
FULL_BACKUP_DAY=6
LOGS_DIR=/var/log/my-app
RESOURCES_DIR=/var/data/my-app
WORK_DIR=/tmp/backups
```

`zata-ops` 自动加载当前 CWD 的 `.env` → `.env.local`，CLI flag 优先级最高。

## 3. 通过 `just` 委托

模板的 `justfile` 已提供薄封装，避免重复输入 `cd` 与命令名：

```bash
just ops-backup --dry-run            # 看一遍计划
just ops-backup                      # 执行
just ops-backup --force-full         # 强制 full
just ops-restore --from 2026-06-07_180000 --restore-db --yes
just ops-check                       # S3 连通性
just ops-dashboard --mock            # 终端状态看板
```

## 4. 调度方式

`zata-ops` 不再常驻 scheduler，请选择以下任一方案：

- **systemd timer** / **cron**：在部署机上每天定时调用 `zata-ops db backup`。
- **GitHub Actions** `schedule:` workflow：在 CI 中拉镜像后执行。
- **Dokploy Scheduled Job**：通过 Dokploy UI 创建定时任务调用 `zata-ops`。
- **手工**：维护窗口前手动执行 `just ops-backup --force-full`。

完整示例见 `zata-ops/docs/guides/scheduling.md`。

## 5. 旧 manifest 兼容

`zata-ops db restore` 保留了原 `scripts/backup_service` 写入 S3 时的 key
layout 与 manifest shape，因此旧 backup 不需要任何迁移即可被 `zata-ops`
恢复。
