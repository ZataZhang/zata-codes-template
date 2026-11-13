"""守卫测试（guard test）：业务表归属组织，HTTP 路由必须显式鉴权或列入公开名单。"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from fastapi.routing import APIRoute

import backend.composition.app_factory as app_factory_module
import backend.infrastructure.persistence.models  # noqa: F401 注册 ORM metadata
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.database import Base

_AUTH_DEPENDENCIES = frozenset(
    {
        "get_current_public_user",
        "get_current_admin_user",
        "get_current_platform_admin",
        "get_current_organization_admin",
        "get_current_a2a_credential",
    }
)
_PUBLIC_HTTP_ROUTES = {
    ("POST", "/auth/login"): "建立 public 会话的登录入口",
    ("POST", "/auth/register"): "建立 public 会话的注册入口",
    ("GET", "/auth/registration-status"): "不返回敏感策略细节的公开注册状态",
    ("GET", "/auth/oidc/status"): "公开 OIDC 配置状态",
    ("GET", "/auth/oidc/start"): "启动 public OIDC 登录事务",
    ("GET", "/auth/oidc/callback"): "消费 public OIDC 登录回调",
    ("POST", "/admin/auth/login"): "建立 admin 会话的登录入口",
    ("GET", "/admin/auth/oidc/status"): "公开 OIDC 配置状态",
    ("GET", "/admin/auth/oidc/start"): "启动 admin OIDC 登录事务",
    ("GET", "/admin/auth/oidc/callback"): "消费 admin OIDC 登录回调",
    ("GET", "/health"): "容器存活探针",
    ("GET", "/ready"): "容器就绪探针",
    ("GET", "/live"): "容器存活探针",
    ("GET", "/metrics"): "部署方监控指标入口，不返回业务对象",
}
_PUBLIC_MOUNTS = {
    "/api/mcp": "可选只读 application_info 工具；默认关闭且独立限制 Host/Origin",
}
_ORGANIZATION_SCOPE_EXEMPTIONS: dict[str, str] = {}


def _unscoped_owner_tables(
    table_columns: Iterable[tuple[str, frozenset[str]]],
    exemptions: dict[str, str] | None = None,
) -> list[str]:
    """找出带 owner_id、却没有组织归属或说明豁免原因的表。"""
    allowed_exemptions = exemptions or {}
    return [
        table_name
        for table_name, columns in table_columns
        if "owner_id" in columns
        and "organization_id" not in columns
        and not allowed_exemptions.get(table_name, "").strip()
    ]


def _unauthorized_routes(
    route_keys: Iterable[tuple[str, str]], guarded_routes: set[tuple[str, str]]
) -> list[tuple[str, str]]:
    """返回既没有已识别会话守卫、也没有公开理由的路由。"""
    return [
        route_key
        for route_key in route_keys
        if route_key not in guarded_routes and route_key not in _PUBLIC_HTTP_ROUTES
    ]


def _application_routers() -> list[object]:
    """从 composition root 的真实 include_router 清单读取所有 API router。"""
    source_text = Path(app_factory_module.__file__).read_text(encoding="utf-8")
    syntax_tree = ast.parse(source_text)
    router_names: list[str] = []
    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Name):
            continue
        if node.target.id != "api_router" or not isinstance(node.iter, ast.Tuple):
            continue
        router_names.extend(
            element.id for element in node.iter.elts if isinstance(element, ast.Name)
        )
    for node in ast.walk(syntax_tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
                and node.args[0].id != "api_router"
            and node.args[0].id not in router_names
        ):
            router_names.append(node.args[0].id)
    assert router_names, "composition root 未显式列出 HTTP API routers"
    return [getattr(app_factory_module, router_name) for router_name in router_names]


def _dependency_names(route: APIRoute) -> set[str]:
    """递归展开 FastAPI 依赖名称，识别嵌套的会话守卫。"""
    found_names: set[str] = set()

    def visit(dependant: object) -> None:
        for dependency in getattr(dependant, "dependencies", []):
            dependency_call = getattr(dependency, "call", None)
            if dependency_call is not None:
                found_names.add(getattr(dependency_call, "__name__", ""))
            visit(dependency)

    visit(route.dependant)
    return found_names


def test_owner_tables_record_organization_or_have_reviewed_waiver() -> None:
    """所有业务 owner 表必须保存创建时的组织归属。"""
    table_columns = [
        (table.name, frozenset(table.c.keys())) for table in Base.metadata.tables.values()
    ]
    assert not _unscoped_owner_tables(table_columns, _ORGANIZATION_SCOPE_EXEMPTIONS)


def test_organization_guard_detects_an_unscoped_owner_table() -> None:
    """负例：新增 owner_id 但不保存 organization_id 时，检查器必须报出表名。"""
    assert _unscoped_owner_tables([("unsafe_asset", frozenset({"owner_id"}))]) == [
        "unsafe_asset"
    ]


def test_every_application_http_route_has_auth_or_public_reason() -> None:
    """所有挂载的 HTTP 路由都要绑定认证依赖或逐项说明公开理由。"""
    route_keys: list[tuple[str, str]] = []
    guarded_routes: set[tuple[str, str]] = set()
    for api_router in _application_routers():
        for route in getattr(api_router, "routes", []):
            if not isinstance(route, APIRoute):
                continue
            dependency_names = _dependency_names(route)
            methods = route.methods or set()
            for method in methods:
                route_key = (method, route.path)
                route_keys.append(route_key)
                if dependency_names & _AUTH_DEPENDENCIES:
                    guarded_routes.add(route_key)
    violations = _unauthorized_routes(route_keys, guarded_routes)
    assert not violations, f"缺少认证依赖或公开理由的路由：{violations}"
    assert all(reason.strip() for reason in _PUBLIC_HTTP_ROUTES.values())
    if config.mcp.enabled:
        assert _PUBLIC_MOUNTS.get("/api/mcp", "").strip()
        assert config.mcp.allowed_hosts


def test_route_guard_rejects_a_new_unlisted_public_endpoint() -> None:
    """负例：加入未授权且未登记的业务入口时，检查器必须返回该路由。"""
    assert _unauthorized_routes([("GET", "/agent-runs/{run_id}")], set()) == [
        ("GET", "/agent-runs/{run_id}")
    ]
