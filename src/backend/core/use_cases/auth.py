"""认证用例。"""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.shared.interfaces.session_store import ISessionStore


@dataclass(frozen=True)
class User:
    """领域用户模型。"""

    user_id: str
    display_name: str
    email: str


class AuthUseCase:
    """认证用例：登录、登出、获取当前会话。"""

    def __init__(self, session_store: ISessionStore) -> None:
        self._session_store: ISessionStore = session_store
        self._user_database: dict[str, User] = {
            "admin": User(
                user_id="admin",
                display_name="管理员",
                email="admin@example.com",
            ),
        }
        self._password_database: dict[str, str] = {"admin": "admin"}

    def login(self, identifier: str, password: str) -> tuple[str, User]:
        """验证凭据并创建 Session。

        Args:
            identifier: 用户名或邮箱。
            password: 密码。

        Returns:
            (session_token, user) 元组。

        Raises:
            ValueError: 用户名或密码错误。
        """
        normalized_identifier: str = identifier.strip().lower()
        matched_user: User | None = None
        matched_user_id: str | None = None

        for user_id, user in self._user_database.items():
            if (
                user_id == normalized_identifier
                or user.email.lower() == normalized_identifier
            ):
                matched_user = user
                matched_user_id = user_id
                break

        if matched_user_id is None:
            raise ValueError("用户名或密码错误")

        expected_password: str | None = self._password_database.get(matched_user_id)
        if expected_password is None or expected_password != password:
            raise ValueError("用户名或密码错误")

        session_token: str = self._session_store.create(matched_user_id)
        return session_token, matched_user

    def logout(self, token: str) -> None:
        """销毁指定 Session。"""
        self._session_store.delete(token)

    def get_current_session(self, token: str) -> User | None:
        """验证 Session 并在滑动窗口规则下续期。

        Args:
            token: Session token。

        Returns:
            对应用户对象；若 Session 无效或已过期则返回 None。
        """
        session_record = self._session_store.slide_expiration(token)
        if session_record is None:
            return None
        return self._user_database.get(session_record.user_id)
