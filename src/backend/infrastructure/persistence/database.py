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

    连接池按后端区分：

    - **SQLite**：用 ``StaticPool``。内存库的数据依附于连接，换连接就换成一个
      空库；文件库并发写也无益，共享单连接反而更简单。
    - **其它后端（PostgreSQL / MySQL）**：用默认的 ``QueuePool``，并开启
      ``pool_pre_ping``。这里**不能**用 ``StaticPool``——它让整个进程共用一条
      物理连接，两个"独立"的 Session 会拿到同一条连接、事务互相覆盖：一个
      Session 的 commit 会把另一个未完成的事务一起提交，或被其 rollback 抹掉。
      症状是"所有写入看起来都成功，但数据没落库"，且只在同时存在多个 Session
      时出现（API 与 Worker 同进程、或请求期间另开会话），极难排查。
      ``pool_pre_ping`` 用来丢弃被数据库侧超时关掉的空连接，避免进程空闲一段
      时间后第一次访问数据库必失败。

    Args:
        **kwargs: 透传给 ``create_engine`` 的额外关键字参数；显式传入的
            ``poolclass`` 优先于这里的判定。

    Returns:
        Any: SQLAlchemy 引擎实例。
    """
    is_sqlite_backend = DATABASE_URL.startswith("sqlite")
    default_kwargs: dict[str, Any] = {"echo": False}
    if is_sqlite_backend:
        default_kwargs["poolclass"] = StaticPool
    else:
        default_kwargs["pool_pre_ping"] = True
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
