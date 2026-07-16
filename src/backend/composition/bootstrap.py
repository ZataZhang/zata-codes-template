"""数据库迁移与初始数据装配。"""

from __future__ import annotations

import os
import uuid

from alembic import command
from alembic.config import Config
from backend.core.shared.models.user_account import UserAccount
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.tool import ToolModel
from backend.infrastructure.persistence.repos.user_account_repo import (
    SqlAlchemyUserAccountRepository,
)


def run_migrations() -> None:
    """启动时自动执行 Alembic 迁移到最新版本。"""

    alembic_ini_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "alembic.ini",
    )
    command.upgrade(Config(alembic_ini_path), "head")


def seed_tools() -> None:
    """写入模板内置工具种子数据。"""

    database_session = SessionLocal()
    try:
        if database_session.query(ToolModel).first() is not None:
            return
        seed_tool_models = [
            ToolModel(
                id="web_search",
                name="网页搜索",
                description="通过关键词搜索网页并返回摘要结果。",
                handler_path="backend.engines.skills.tools.web_search",
                schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                    "required": ["query"],
                },
            ),
            ToolModel(
                id="code_runner",
                name="代码执行",
                description="执行一段代码并返回运行结果。",
                handler_path="backend.engines.skills.tools.code_runner",
                schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "代码内容"},
                        "language": {"type": "string", "description": "编程语言"},
                    },
                    "required": ["code"],
                },
            ),
        ]
        for seed_tool_model in seed_tool_models:
            database_session.add(seed_tool_model)
        database_session.commit()
    finally:
        database_session.close()


def seed_admin_user(
    admin_repository: SqlAlchemyUserAccountRepository,
    password_hasher: BcryptPasswordHasher,
) -> None:
    """根据环境变量幂等创建初始管理员。

    Args:
        admin_repository: admin 域用户仓库。
        password_hasher: 密码哈希实现。
    """

    bootstrap_username = config.auth.admin_bootstrap_username.strip()
    bootstrap_password = config.auth.admin_bootstrap_password.get_secret_value()
    if not bootstrap_username or not bootstrap_password:
        logger.info("未配置 AUTH_ADMIN_BOOTSTRAP_*，跳过初始管理员种子。")
        return
    normalized_username = bootstrap_username.lower()
    existing_admin = admin_repository.find_by_identifier(normalized_username)
    password_hash = password_hasher.hash(bootstrap_password)
    if existing_admin is not None:
        admin_repository.set_password(existing_admin.id, password_hash)
        logger.info("已同步初始管理员密码：%s", normalized_username)
        return
    admin_repository.create(
        UserAccount(
            id=uuid.uuid4().hex,
            identifier=normalized_username,
            display_name=bootstrap_username,
            password_hash=password_hash,
            is_active=True,
        )
    )
    logger.info("已创建初始管理员：%s", normalized_username)


def seed_public_user(
    public_repository: SqlAlchemyUserAccountRepository,
    password_hasher: BcryptPasswordHasher,
) -> None:
    """根据环境变量幂等创建本地开发用 public 用户。

    Args:
        public_repository: public 域用户仓库。
        password_hasher: 密码哈希实现。
    """

    bootstrap_email = os.getenv("APP_BOOTSTRAP_EMAIL", "").strip()
    bootstrap_password = os.getenv("APP_BOOTSTRAP_PASSWORD", "").strip()
    if not bootstrap_email or not bootstrap_password:
        logger.info("未配置 APP_BOOTSTRAP_*，跳过初始 public 用户种子。")
        return
    normalized_email = bootstrap_email.lower()
    existing_public_user = public_repository.find_by_identifier(normalized_email)
    password_hash = password_hasher.hash(bootstrap_password)
    if existing_public_user is not None:
        public_repository.set_password(existing_public_user.id, password_hash)
        logger.info("已同步初始 public 用户密码：%s", normalized_email)
        return
    public_repository.create(
        UserAccount(
            id=uuid.uuid4().hex,
            identifier=normalized_email,
            display_name=bootstrap_email.split("@")[0],
            password_hash=password_hash,
            is_active=True,
        )
    )
    logger.info("已创建初始 public 用户：%s", normalized_email)


__all__ = ["run_migrations", "seed_admin_user", "seed_public_user", "seed_tools"]
