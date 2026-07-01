"""基础设施持久层的 SQLAlchemy 数据库设置。"""

from typing import Any, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.config import Config as AlembicConfig
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger

Base = declarative_base()

DATABASE_URL = config.resolved_database_url
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")

_ALEMBIC_INI_PATH = str(config.base_dir / "alembic.ini")


def _run_alembic_upgrade() -> None:
    alembic_cfg = AlembicConfig(_ALEMBIC_INI_PATH)
    command.upgrade(alembic_cfg, "head")


def create_database_engine(**kwargs: Any) -> Any:
    """创建 SQLAlchemy 引擎。

    Args:
        **kwargs: 透传给 ``create_engine`` 的额外关键字参数。

    Returns:
        Any: SQLAlchemy 引擎实例。
    """
    default_kwargs = {
        "poolclass": StaticPool,
        "echo": False,
    }
    default_kwargs.update(kwargs)
    return create_engine(DATABASE_URL, **default_kwargs)


engine = create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables(base: Any = None) -> None:  # noqa: ARG001
    """运行 Alembic 迁移以创建或升级所有表。

    Args:
        base: 未使用；为兼容性保留。
    """
    _run_alembic_upgrade()
    logger.info("数据库表创建成功！")


def get_db() -> Generator[Session, None, None]:
    """为依赖注入生成数据库会话。

    Yields:
        Session: SQLAlchemy 数据库会话。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database(base: Any = None) -> None:
    """通过 Alembic 迁移初始化数据库表。

    Args:
        base: 未使用；为兼容性保留。
    """
    if config.db_migration_mode == "auto":
        create_tables(base)
    else:
        logger.info("db_migration_mode=manual, 跳过自动迁移。")


__all__ = [
    "Base",
    "SessionLocal",
    "create_database_engine",
    "create_tables",
    "engine",
    "get_db",
    "init_database",
]
