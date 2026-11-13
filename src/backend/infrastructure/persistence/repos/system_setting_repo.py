"""系统设置键值仓库的 SQLAlchemy 实现。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.shared.interfaces.system_setting_repository import SystemSettingRepository
from backend.infrastructure.persistence.models.system_setting import SystemSettingModel


class SqlAlchemySystemSettingRepository(SystemSettingRepository):
    """以独立短事务读取或写入系统设置。"""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        """初始化系统设置仓库。

        Args:
            session_factory (sessionmaker[Session]): 为每次调用创建短会话的工厂。
        """
        self._session_factory = session_factory

    def get(self, key: str) -> str | None:
        """按键读取设置值。

        Args:
            key (str): 设置键。

        Returns:
            str | None: JSON 文本；键不存在时返回 None。
        """
        with self._session_factory() as session:
            setting_model = session.get(SystemSettingModel, key)
            return setting_model.value if setting_model is not None else None

    def put(self, key: str, value_json: str) -> None:
        """创建或更新 JSON 设置，使用可移植的读后写事务。

        Args:
            key (str): 设置键。
            value_json (str): 已序列化的 JSON 文本。
        """
        try:
            with self._session_factory.begin() as session:
                setting_model = session.get(SystemSettingModel, key)
                if setting_model is None:
                    now: datetime = datetime.now(timezone.utc)
                    session.add(
                        SystemSettingModel(
                            key=key,
                            value=value_json,
                            updated_at=now,
                        )
                    )
                else:
                    setting_model.value = value_json
                    setting_model.updated_at = datetime.now(timezone.utc)
                session.flush()
        except IntegrityError as insert_conflict:
            self._update_after_concurrent_insert(key, value_json, insert_conflict)

    def _update_after_concurrent_insert(
        self,
        key: str,
        value_json: str,
        insert_conflict: IntegrityError,
    ) -> None:
        """并发首次写入撞唯一键时，在新事务内更新胜出的记录。"""
        with self._session_factory.begin() as session:
            setting_model = session.get(SystemSettingModel, key)
            if setting_model is None:
                raise insert_conflict
            setting_model.value = value_json
            setting_model.updated_at = datetime.now(timezone.utc)
            session.flush()


__all__ = ["SqlAlchemySystemSettingRepository"]
