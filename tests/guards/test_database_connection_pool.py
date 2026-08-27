"""守卫：非 SQLite 后端不得使用 ``StaticPool``。

为什么值得一条守卫：``StaticPool`` 让整个进程共用**一条**物理数据库连接。
两个"独立"的 Session 会拿到同一条连接，于是事务互相覆盖——一个 Session 的
commit 会把另一个未完成的事务一并提交，或被它的 rollback 抹掉。

症状极具欺骗性：所有写入调用都返回成功、日志一切正常，但数据没有落库。它只在
同一进程里同时存在多个 Session 时出现（API 与后台任务同进程、请求期间另开会
话、一个长驻会话未关闭），因此单元测试通常照样全绿；而以 SQLite 跑测试的项目
更是永远碰不到，直到接上 PostgreSQL 才在生产里发作。

SQLite 是唯一合法例外：内存库的数据依附于连接，换连接等于换成一个空库。
"""

from __future__ import annotations

from sqlalchemy.pool import QueuePool, StaticPool

from backend.infrastructure.persistence.database import (
    DATABASE_URL,
    SessionLocal,
    create_database_engine,
    engine,
)


def test_process_engine_does_not_share_a_single_connection() -> None:
    """进程默认引擎在非 SQLite 后端上不得使用 ``StaticPool``。"""
    if DATABASE_URL.startswith("sqlite"):
        assert isinstance(engine.pool, StaticPool), "SQLite 应使用 StaticPool"
        return
    assert not isinstance(engine.pool, StaticPool), (
        f"{type(engine.pool).__name__} 检查失败：非 SQLite 后端使用 StaticPool 会让"
        "整个进程共用一条连接，事务互相覆盖，表现为'写入成功但数据没落库'。"
    )
    assert isinstance(engine.pool, QueuePool)


def test_two_sessions_get_distinct_connections() -> None:
    """两个 Session 必须拿到不同的物理连接。

    这是上面那条断言的行为化版本：直接验证后果，而不只是检查连接池类名。
    换用别的共享单连接的池实现同样会被这条抓住。

    需要一个可连接的非 SQLite 数据库；以 SQLite 运行时直接跳过。
    """
    if DATABASE_URL.startswith("sqlite"):
        return
    first_session = SessionLocal()
    second_session = SessionLocal()
    try:
        first_raw_connection = first_session.connection().connection.dbapi_connection
        second_raw_connection = second_session.connection().connection.dbapi_connection
        assert (
            first_raw_connection is not second_raw_connection
        ), "两个 Session 共用同一条物理连接：它们的事务会互相覆盖。"
    finally:
        first_session.close()
        second_session.close()


def test_non_sqlite_engine_enables_pool_pre_ping() -> None:
    """非 SQLite 后端必须开启 ``pool_pre_ping``。

    没有它，被数据库侧超时关掉的空连接仍会被派发出来，进程空闲一段时间后第一
    次访问数据库必然失败——而那个失败与真实原因毫无关系。
    """
    if DATABASE_URL.startswith("sqlite"):
        return
    assert engine.pool._pre_ping is True, "非 SQLite 后端应开启 pool_pre_ping"


def test_explicit_poolclass_argument_still_wins() -> None:
    """显式传入的 ``poolclass`` 优先于后端判定。

    保留这个逃生口：测试或特殊工具可能确实需要单连接语义。
    """
    explicit_engine = create_database_engine(poolclass=StaticPool)
    try:
        assert isinstance(explicit_engine.pool, StaticPool)
    finally:
        explicit_engine.dispose()
