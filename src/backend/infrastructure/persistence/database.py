"""SQLAlchemy database setup for infrastructure persistence."""

from typing import Any, Generator

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.infrastructure.config.settings import config
from backend.infrastructure.logging.logger import logger

Base = declarative_base()

DATABASE_URL = config.resolved_database_url
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://")

_ALEMBIC_INI_PATH = str(config.base_dir / "alembic.ini")


def _run_alembic_upgrade() -> None:
    alembic_cfg = AlembicConfig(_ALEMBIC_INI_PATH)
    command.upgrade(alembic_cfg, "head")


def create_database_engine(**kwargs: Any) -> Any:
    """Create a SQLAlchemy engine.

    Args:
        **kwargs: Extra keyword arguments forwarded to ``create_engine``.

    Returns:
        Any: SQLAlchemy engine instance.
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
    """Run Alembic migrations to create or upgrade all tables.

    Args:
        base: Unused; kept for backward compatibility.
    """
    _run_alembic_upgrade()
    logger.info("数据库表创建成功！")


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection.

    Yields:
        Session: SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database(base: Any = None) -> None:
    """Initialize database tables via Alembic migration.

    Args:
        base: Unused; kept for backward compatibility.
    """
    if config.db_migration_mode == "auto":
        create_tables(base)
    else:
        logger.info("db_migration_mode=manual, skipping auto migration.")


__all__ = [
    "Base",
    "SessionLocal",
    "create_database_engine",
    "create_tables",
    "engine",
    "get_db",
    "init_database",
]
