#!/usr/bin/env python3
"""为新复制出的项目设置独立的数据库。

读取目标项目的 ``.env.local``，根据项目名派生唯一的数据库名，更新
``DATABASE_URL``，并尝试在 PostgreSQL 中创建该数据库。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


def derive_database_name(project_name: str) -> str:
    """根据项目名派生 Postgres 安全的数据库名。

    Args:
        project_name: 新项目名称。

    Returns:
        小写、下划线连接、不超过 63 字节的数据库名。
    """
    db_name = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_")
    db_name = re.sub(r"_+", "_", db_name)
    if not db_name:
        db_name = "app"
    # Postgres 标识符默认限制 63 字节。
    return db_name[:63]


def update_database_url(
    env_local_path: Path,
    project_name: str,
) -> tuple[Optional[str], Optional[str]]:
    """更新 ``.env.local`` 中的 ``DATABASE_URL`` 为项目专用数据库。

    Args:
        env_local_path: 目标项目 ``.env.local`` 路径。
        project_name: 新项目名称。

    Returns:
        (新的 DATABASE_URL, 新的数据库名)；若无需更新则返回 ``(None, None)``。
    """
    if not env_local_path.exists():
        return None, None

    text = env_local_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    new_url: Optional[str] = None
    updated = False

    for index, line in enumerate(lines):
        if not line.startswith("DATABASE_URL="):
            continue
        _, _, value = line.partition("=")
        value = value.strip()
        if not value:
            continue
        parsed = urlparse(value)
        if not parsed.scheme.startswith("postgresql"):
            # 只改写 PostgreSQL URL，SQLite 等保持不变。
            continue
        db_name = derive_database_name(project_name)
        new_url = parsed._replace(path=f"/{db_name}").geturl()
        lines[index] = f"DATABASE_URL={new_url}"
        updated = True
        break

    if updated:
        env_local_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return (new_url, derive_database_name(project_name)) if updated else (None, None)


def create_postgres_database(database_url: str) -> bool:
    """尝试根据 ``DATABASE_URL`` 创建 PostgreSQL 数据库。

    Args:
        database_url: 已更新为项目专用数据库的 URL。

    Returns:
        数据库已创建或已存在返回 ``True``，否则返回 ``False``。
    """
    parsed = urlparse(database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username
    password = parsed.password
    db_name = parsed.path.lstrip("/") if parsed.path else ""

    if not db_name:
        return False

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 不可用，无法自动创建数据库。")
        return False

    connection = None
    try:
        connection = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
        )
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;",
                (db_name,),
            )
            if cursor.fetchone():
                print(f"数据库 '{db_name}' 已存在。")
                return True
            cursor.execute(f"CREATE DATABASE {db_name};")
        print(f"已创建数据库: {db_name}")
        return True
    except psycopg2.Error as exc:
        print(f"无法创建数据库 '{db_name}': {exc}")
        return False
    finally:
        if connection is not None:
            connection.close()


def main() -> int:
    """脚本入口。"""
    if len(sys.argv) != 3:
        print("Usage: python setup_copied_database.py <project_name> <project_root>")
        return 1

    project_name = sys.argv[1]
    project_root = Path(sys.argv[2])

    env_local_path = project_root / ".env.local"
    new_url, db_name = update_database_url(env_local_path, project_name)

    if new_url is None or db_name is None:
        print(".env.local 中未找到 PostgreSQL 的 DATABASE_URL，跳过数据库设置。")
        return 0

    print(f"已更新 DATABASE_URL 为项目专用数据库: {new_url}")

    if create_postgres_database(new_url):
        print("数据库已就绪。")
    else:
        print("请手动创建数据库，然后运行 `uv run alembic upgrade head`:")
        print(f"  createdb -h localhost -U <user> {db_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
