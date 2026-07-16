"""后端应用依赖装配包。

普通调用方应继续通过 :mod:`backend.main` 使用兼容入口；本包公开
``create_app`` 供需要直接访问 composition root 的内部工具使用。
"""

from backend.composition.app_factory import create_app

__all__ = ["create_app"]
