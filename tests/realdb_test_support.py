"""真实数据库测试的自动清理与残留检测支持。

部分 integration 测试经 ``TestClient(create_app())`` 或 ``SessionLocal``
直接写入由 ``DATABASE_URL`` 指向的真实数据库（跨连接会话失效、两域物理
隔离等语义在 SQLite / 内存替身下无法复现）。本模块为这类测试提供三类能力：

- ``TrackedEntityRegistry``：登记测试创建的实体 ID，teardown 时按精确 ID
  删除。模板当前只有 ``admin_user`` / ``public_user`` 两张无关联的用户表，
  删除无需考虑外键顺序；新增带外键的表时应按外键逆序扩展清理逻辑。
- ``TrackedTestClient``：包装 ``TestClient``，把创建型接口
  （``/auth/register``）响应中的用户 ID 自动登记进注册表。
- ``residue_table_models`` / ``snapshot_residue_tables`` /
  ``diff_residue_tables``：哨兵在测试前后对比覆盖表的主键集合，任何净变化
  让测试失败并列出泄漏行。覆盖表与 ORM 模型均惰性加载，避免模块导入时
  强制初始化应用数据库配置。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import delete, select

# Registry teardown 用的惰性 session 工厂：模块加载时不绑定应用配置，第一次
# 清理时按当前 ``DATABASE_URL`` 建引擎，避免表导入触发应用配置副作用。
_local_session_factory = None


def _session_factory():
    """返回惰性绑定当前 ``DATABASE_URL`` 的 session 工厂。"""
    global _local_session_factory
    if _local_session_factory is None:
        from sqlalchemy.orm import sessionmaker

        from backend.infrastructure.persistence.database import engine

        _local_session_factory = sessionmaker(bind=engine)
    return _local_session_factory


def _orm_models():
    """惰性加载哨兵/清理涉及的 ORM 模型，返回按表名字典。

    Returns:
        dict[str, type]: 表名到 ORM 模型类的映射。
    """
    from backend.infrastructure.persistence.models.admin_user import AdminUserModel
    from backend.infrastructure.persistence.models.public_user import PublicUserModel

    return {
        "public_user": PublicUserModel,
        "admin_user": AdminUserModel,
    }


def residue_table_models() -> dict[str, type]:
    """返回哨兵覆盖的表名到 ORM 模型映射（惰性加载）。

    新增真实库测试数据表时应同步加入 ``_orm_models``。
    """
    return _orm_models()


def snapshot_residue_tables() -> dict[str, frozenset[tuple]]:
    """记录哨兵覆盖的每张表的主键集合。

    惰性绑定当前 ``DATABASE_URL``，确保串行快照与其他测试对同一条数据库
    连接可见。

    Returns:
        dict[str, frozenset[tuple]]: 表名到主键元组集合的映射，
        供 ``diff_residue_tables`` 做前后对比。
    """
    from backend.infrastructure.persistence.database import engine

    table_snapshots: dict[str, frozenset[tuple]] = {}
    with engine.connect() as connection:
        for table_name, residue_model in _orm_models().items():
            primary_key_columns = [
                column for column in residue_model.__table__.columns if column.primary_key
            ]
            primary_key_rows = connection.execute(select(*primary_key_columns)).all()
            table_snapshots[table_name] = frozenset(
                tuple(primary_key_row) for primary_key_row in primary_key_rows
            )
    return table_snapshots


def diff_residue_tables(
    snapshot_before: dict[str, frozenset[tuple]],
    snapshot_after: dict[str, frozenset[tuple]],
) -> dict[str, dict[str, set[tuple]]]:
    """计算两张快照的净新增与净删除主键。

    Args:
        snapshot_before: 测试前快照。
        snapshot_after: 测试后快照。

    Returns:
        dict[str, dict[str, set[tuple]]]: 表名到
        ``{"added": ..., "removed": ...}`` 的映射；无变化的表不进入结果。
    """
    residue_diff: dict[str, dict[str, set[tuple]]] = {}
    for table_name, before_keys in snapshot_before.items():
        after_keys = snapshot_after[table_name]
        added_keys = set(after_keys) - set(before_keys)
        removed_keys = set(before_keys) - set(after_keys)
        if added_keys or removed_keys:
            residue_diff[table_name] = {"added": added_keys, "removed": removed_keys}
    return residue_diff


def _delete_where(database_session, model, entity_ids) -> None:
    """删除主键命中 ID 集合的行；空集合直接跳过。"""
    if not entity_ids:
        return
    database_session.execute(delete(model).where(model.id.in_(entity_ids)))


def has_realdb_marker(request) -> bool:
    """判断测试是否带 ``realdb`` 标记。

    pytest 9 起 ``Mark.__eq__`` 不再与字符串相等，且 ``Mark`` 不可哈希，
    因此 ``"realdb" in request.node.iter_markers()`` 恒为假。必须显式比较
    ``mark.name``。

    Args:
        request: 当前 pytest 请求的 ``request`` 对象（含 ``node``）。

    Returns:
        bool: 节点或其任意父级是否带 ``realdb`` 标记。
    """
    return any(mark.name == "realdb" for mark in request.node.iter_markers())


@dataclass
class TrackedEntityRegistry:
    """一个测试经 fixture 创建、需按精确 ID 删除的全部实体。

    Attributes:
        admin_user_ids: 种入或注册的管理员 ID 列表。
        public_user_ids: 注册的用户 ID 列表。
    """

    admin_user_ids: list[str] = field(default_factory=list)
    public_user_ids: list[str] = field(default_factory=list)

    def delete_tracked_entities(self) -> None:
        """删除登记的全部实体，缺失行按 no-op 处理。

        绝不按名称前缀匹配，避免误伤真实数据。当前两张用户表无关联，无需
        外键顺序；新增带外键的表时应按外键逆序删除。
        """
        orm_models = _orm_models()
        with _session_factory().begin() as database_session:
            _delete_where(database_session, orm_models["public_user"], self.public_user_ids)
            _delete_where(database_session, orm_models["admin_user"], self.admin_user_ids)


class TrackedTestClient:
    """包装 ``TestClient``，把创建型接口响应中的实体 ID 登记进注册表。

    测试继续按 ``TestClient`` 的接口使用（``__getattr__`` 委托其余方法），
    额外获得自动登记：``/auth/register`` → user_id。
    """

    def __init__(self, test_client: TestClient, entity_registry: TrackedEntityRegistry) -> None:
        """初始化被包装的客户端与注册表。

        Args:
            test_client: 底层 ``TestClient`` 实例。
            entity_registry: 实体登记目标注册表。
        """
        self._test_client = test_client
        self._entity_registry = entity_registry

    @property
    def app(self) -> FastAPI:
        """透传底层应用对象，供测试访问 ``app.state`` 装配。"""
        return self._test_client.app

    def __getattr__(self, attribute_name: str):
        """委托其余方法与属性到被包装的客户端。"""
        return getattr(self._test_client, attribute_name)

    def __enter__(self) -> TrackedTestClient:
        """进入上下文并保持包装类型（``with`` 不丢失登记能力）。"""
        self._test_client.__enter__()
        return self

    def __exit__(self, *exception_info) -> None:
        """退出底层客户端上下文。"""
        self._test_client.__exit__(*exception_info)

    def post(self, url: str, *args, **kwargs) -> Response:
        """转发 POST 并把创建型接口返回的实体 ID 登记进注册表。

        Args:
            url: 请求路径。
            *args: 透传位置参数。
            **kwargs: 透传关键字参数。

        Returns:
            Response: 底层客户端响应。
        """
        response = self._test_client.post(url, *args, **kwargs)
        if response.status_code != 201:
            return response
        response_body = response.json()
        if url == "/auth/register":
            self._entity_registry.public_user_ids.append(response_body["user_id"])
        return response
