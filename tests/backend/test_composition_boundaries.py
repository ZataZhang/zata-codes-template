"""验证 composition root 的公开入口与依赖边界。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from backend import composition
from backend.main import create_app


def _load_architecture_checker(project_root: Path) -> ModuleType:
    """从仓库 hook 路径加载架构检查模块。"""

    checker_path = project_root / "hooks" / "shared" / "check_architecture.py"
    module_spec = importlib.util.spec_from_file_location(
        "check_architecture_for_test",
        checker_path,
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    checker_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(checker_module)
    return checker_module


def test_composition_package_exposes_app_factory() -> None:
    """包级公开入口只暴露应用工厂。"""

    assert composition.__all__ == ["create_app"]
    assert callable(composition.create_app)
    assert callable(create_app)


def test_layer_importing_composition_is_rejected(tmp_path: Path) -> None:
    """core 反向导入 composition 时架构检查必须失败。"""

    repository_root = Path(__file__).resolve().parents[2]
    checker_module = _load_architecture_checker(repository_root)
    core_module_path = tmp_path / "src" / "sample" / "core"
    core_module_path.mkdir(parents=True)
    (core_module_path / "service.py").write_text(
        "from sample.composition import create_app\n",
        encoding="utf-8",
    )

    check_result = checker_module.run_architecture_check(tmp_path)

    assert not check_result.passed
    assert check_result.violations[0].forbidden_layer == "composition"
