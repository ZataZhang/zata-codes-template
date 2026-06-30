"""Migration sanity checks.

Guards against two failure modes seen in derived projects:

1. A migration cannot be applied to a fresh database from base to head.
2. The database schema after running all migrations drifts from the SQLAlchemy
   model definitions (e.g. a column exists in code but is missing from the
   migration chain).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from backend.infrastructure.persistence.database import Base

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]


def _alembic_config() -> AlembicConfig:
    """Return an Alembic config pointed at this project's migration scripts."""
    cfg = AlembicConfig(str(_PROJECT_ROOT_PATH / "alembic.ini"))
    cfg.set_main_option("script_location", str(_PROJECT_ROOT_PATH / "alembic"))
    return cfg


@pytest.fixture()
def migration_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    """Create a fresh SQLite database migrated to head.

    Args:
        tmp_path: Pytest temporary directory.
        monkeypatch: Pytest monkeypatch fixture for environment isolation.

    Yields:
        SQLAlchemy engine connected to the migrated test database.
    """
    sqlite_database_path = tmp_path / "migration-test.sqlite3"
    database_url = f"sqlite:///{sqlite_database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    try:
        yield engine
    finally:
        engine.dispose(close=True)


def test_migrations_upgrade_downgrade_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The migration chain must be reversible and re-appliable on a fresh DB."""
    sqlite_database_path = tmp_path / "migration-roundtrip.sqlite3"
    database_url = f"sqlite:///{sqlite_database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    alembic_cfg = _alembic_config()
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


def test_migrated_schema_matches_models(migration_engine: Engine) -> None:
    """Every column declared in SQLAlchemy models must exist after migrations.

    This catches the class of bug where ``alembic_version`` has been stamped to
    a new revision but the actual DDL failed to add a column: the model code
    references the column, and this assertion fails because the migrated schema
    does not contain it.
    """
    inspector = inspect(migration_engine)
    mismatches: list[str] = []

    for table_name, table in Base.metadata.tables.items():
        actual_columns = {
            column_metadata["name"]
            for column_metadata in inspector.get_columns(table_name)
        }
        expected_columns = set(table.columns.keys())
        missing_columns = expected_columns - actual_columns
        if missing_columns:
            mismatches.append(
                f"{table_name}: missing columns {sorted(missing_columns)}"
            )

    assert not mismatches, (
        "Migrated database schema is missing columns defined in models:\n"
        + "\n".join(mismatches)
    )
