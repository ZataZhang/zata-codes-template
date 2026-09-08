"""Alembic environment configuration."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

# Register all models so they are visible in Base.metadata for autogenerate.
# Importing the models package executes its __init__.py, which in turn
# imports every concrete model class so they are bound to ``Base.metadata``.
import backend.infrastructure.persistence.models  # noqa: F401  pylint: disable=unused-import
from alembic import context

# Import project Base and app config
from backend.infrastructure.config.settings import config as app_config
from backend.infrastructure.persistence.database import Base

# this is the Alembic Config object
alembic_config = context.config


def _is_running_inside_test_process() -> bool:
    """判断当前进程是否为 pytest 进程。

    Returns:
        bool: 运行在 pytest 进程内返回 ``True``，否则返回 ``False``。
    """
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


# Interpret the config file for Python logging.
# fileConfig 是"清场式"配置调用：它无条件清空 root logger 的 handler 列表、把
# root level 重置成 alembic.ini 里的 WARNING，且 disable_existing_loggers 默认
# 为 True——所有已存在且不属于 alembic.ini logger 层级的 logger 会被永久标记
# disabled。
#
# 迁移并不总是独占一个进程：database.py 的 create_tables() / init_database()
# 会在进程内调用 command.upgrade()，测试 fixture 也常在进程内跑 upgrade head。
# 在 pytest 进程里这个破坏静默且严重：caplog 依赖挂在 root logger 上的 handler，
# 会被摘掉；迁移之前 import 过的 backend.* logger 会永久 disabled。此后所有
# 基于日志的断言都退化成"records 恒为空"，通过或失败都与被测行为无关。
#
# 所以 pytest 进程内完全跳过 fileConfig（日志由 pytest 自己接管）；CLI 与进程内
# 应用路径仍需要 alembic 的迁移日志，但显式传 disable_existing_loggers=False，
# 不去动宿主进程已经建好的 logger。
# 守卫测试见 tests/guards/test_alembic_logging_isolation.py。
if alembic_config.config_file_name is not None and not _is_running_inside_test_process():
    fileConfig(alembic_config.config_file_name, disable_existing_loggers=False)

# Target metadata for autogenerate support
target_metadata = Base.metadata

# Resolve DATABASE_URL: env var > .env > project config defaults
_DATABASE_URL: str = os.getenv("DATABASE_URL") or app_config.resolved_database_url
DATABASE_URL = _DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # MySQL DDL 会隐式提交；逐 migration 开启显式事务，确保紧随 DDL
            # 的 alembic_version DML 也在连接关闭前提交，避免 schema 已变更
            # 但版本号滞后一条、下次启动重复执行同一 DDL。
            transaction_per_migration=connection.dialect.name == "mysql",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
