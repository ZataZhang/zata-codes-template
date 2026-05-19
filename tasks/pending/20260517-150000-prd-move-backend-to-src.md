# PRD: 将 backend 迁移至 src/backend 并统一分层架构路径

## 1. 背景与目标

当前项目根目录直接存放 `backend/` 文件夹，包含后端四层架构（api、core、engines、infrastructure）。为了统一 Python 项目的 src-layout 规范，并确保 `src/` 下的**每个模块**（当前是 `backend`，未来可能是 `worker`、`cli` 等）都遵循相同的分层架构约束，需要将 `backend/` 整体迁移到 `src/backend/`。

**核心目标：**

1. 将 `backend/` 完整移动到 `src/backend/`，保持内部四层目录结构不变。
2. 配置 `pyproject.toml` 支持 src-layout，确保所有 `import backend.xxx` 语句**无需修改**即可继续工作。
3. 更新所有硬编码了旧 `backend/` 路径的检查脚本、配置文件、工具链命令、文档和测试。
4. **通用化 `hooks/check_architecture.py`**：自动扫描 `src/` 下所有包含四层结构的模块，对每个模块独立执行依赖方向检查，不再写死 `backend`。
5. `src/` 下的每个分层模块内部，继续严格遵循现有依赖方向规则。

## 2. 范围

### 2.1 在范围内

- 目录物理移动：`backend/` → `src/backend/`
- `pyproject.toml` 包发现配置
- `justfile` 启动命令更新
- `hooks/check_architecture.py` **通用化重构**：自动发现 `src/` 下所有分层模块，不再写死 `backend`
- `hooks/check_guidelines_consistency.py` 规范源引用更新（支持通用模块表述）
- `.pre-commit-config.yaml` files 匹配模式更新
- `docs/architecture/system-design.md` 路径与 mermaid 图更新
- `docs/ai-standards/architecture.md` 路径与规则更新
- `AGENTS.md` 依赖方向描述更新
- `.github/copilot-instructions.md` 依赖方向描述更新
- `tests/test_sync_template.py` 硬编码路径更新
- `config.toml` `project_skip_paths` 更新
- `scripts/template/sync_template.sh` skip paths 更新

### 2.2 不在范围内

- `backend/` 内部代码逻辑、分层职责、模块边界本身不做任何调整。
- 除路径迁移外，四层架构的依赖规则（谁可以 import 谁）保持不变。
- `tests/` 中除 `test_sync_template.py` 以外的测试文件，其 `from backend.xxx import ...` 语句因包配置兼容而**不需要修改**。
- `frontend/`、`tests/playwright-e2e/`、`skills/` 等非 Python 后端子树不受影响。
- **跨模块 import**（如 `backend` import `worker.core`）暂时不做严格限制；通用化检查脚本只拦截**模块内部**的违规依赖方向。

## 3. 详细方案

### 3.1 目录结构变更

变更前：

```text
zata_code_template/
├── backend/
│   ├── api/
│   ├── core/
│   ├── engines/
│   ├── infrastructure/
│   └── main.py
├── main.py
├── pyproject.toml
└── ...
```

变更后：

```text
zata_code_template/
├── src/
│   └── backend/
│       ├── api/
│       ├── core/
│       ├── engines/
│       ├── infrastructure/
│       └── main.py
├── main.py
├── pyproject.toml
└── ...
```

`src/backend/` 内部四层架构保持不变，依赖方向仍为：

```text
src/backend/api/ → src/backend/core/ → src/backend/engines/ → src/backend/infrastructure/
```

### 3.2 Python 包配置（pyproject.toml）

在 `pyproject.toml` 中添加 setuptools 包发现配置，使 `backend` 包从 `src/` 下解析，从而保持现有 `import backend.xxx` 兼容：

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

若项目使用其他构建后端（如 hatchling、PDM），则采用对应配置方式，但等效目标一致：让 `backend` 的 Python 包根映射到 `src/backend/`。

### 3.3 启动命令调整（justfile）

`justfile` 中 `backend_cmd` 从直接执行脚本文件改为通过模块方式运行：

- 旧：`backend_cmd="uv run python backend/main.py"`
- 新：`backend_cmd="uv run python -m backend.main"`

根目录 `main.py` 的 `from backend.main import main` 因 editable install / `uv` 包发现机制而**不需要修改**。

### 3.4 架构检查脚本通用化（hooks/check_architecture.py）

核心改动：从"只检查 `backend/`"升级为"自动发现 `src/` 下所有分层模块并独立检查"。

#### 3.4.1 模块自动发现

新增 `_discover_layered_modules(project_root: Path) -> list[tuple[str, Path]]`：

- 遍历 `project_root / "src"` 下的所有子目录。
- 对每个子目录，检查是否包含至少一个已知层目录（`api`、`core`、`engines`、`infrastructure`）。
- 返回符合条件的模块列表，如 `[("backend", Path("src/backend")), ("worker", Path("src/worker"))]`。

#### 3.4.2 文件层与模块解析

将 `_resolve_layer` 重构为 `_resolve_module_and_layer`：

- **只识别 `src/<module>/<layer>/...` 格式**。根目录下遗留的 `backend/` 不再被识别（避免逃过检查）。
- 返回 `(module_name, layer_name)` 元组。例如 `src/backend/api/api.py` → `("backend", "api")`；`src/worker/core/tasks.py` → `("worker", "core")`。

#### 3.4.3 Import 解析通用化

修改 `_extract_imported_modules`：

- 当前逻辑只对 `import backend.xxx` 提取 `parts[1]`，写死了模块名判断。
- **新逻辑**：无论模块名是什么，只要 import 路径的第二段是已知层名（`api`/`core`/`engines`/`infrastructure`），就提取该层名作为 `imported_layer_name`。
- 示例：
  - `from backend.infrastructure.config import settings` → 提取 `infrastructure`
  - `from worker.core.use_cases import execute` → 提取 `core`
  - `import requests` → 提取 `requests`（不在 `LAYER_ORDER` 中，自然不触发违规）

这样，**任意模块的内部依赖方向检查都能自动生效**。

#### 3.4.4 扫描入口重构

`run_architecture_check` 改为：

1. 调用 `_discover_layered_modules` 获取所有模块。
2. 对每个模块，遍历 `LAYER_ORDER` 中的四层，扫描 `src/<module>/<layer>/**/*.py`。
3. 汇总所有模块的检查结果。

#### 3.4.5 报告输出增强

`ArchitectureViolation` 增加 `module_name` 字段，`_format_report` 输出格式从 `[source_layer]` 升级为 `[module_name/source_layer]`，例如：

```
[backend/api] → [infrastructure]  src/backend/api/api.py:42
[worker/core] → [infrastructure]  src/worker/core/tasks.py:15
```

#### 3.4.6 模块级 docstring 更新

将脚本 docstring 和注释中的路径描述更新为通用表述，例如：

> 检查 `src/` 下所有分层模块（如 `backend`、`worker`）的 import 方向是否合法。
> 层次规则：`<module>/api/ → <module>/core/ → <module>/engines/ → <module>/infrastructure/`

### 3.5 规范一致性检查（hooks/check_guidelines_consistency.py）

`check_hub_content` 中 `required_phrases["architecture"]` 的硬编码路径短语：

- `"backend/api/"` → `"src/backend/api/"`
- `"backend/core/"` → `"src/backend/core/"`
- `"docs/architecture/system-design.md"` 保留不变（仍为必须存在的引用）。

### 3.6 Pre-commit 配置（.pre-commit-config.yaml）

`check-architecture` 的 `files` 正则：

- 旧：`^(backend/(api|core|engines|infrastructure))/.*\.py$`
- 新：`^(src/[^/]+/(api|core|engines|infrastructure))/.*\.py$`

新正则匹配 `src/` 下**任意模块**的四层目录，例如 `src/backend/api/...` 或 `src/worker/core/...`。

### 3.7 架构文档更新

**docs/architecture/system-design.md**

- 所有 `backend/api/`、`backend/core/`、`backend/engines/`、`backend/infrastructure/` 文本引用改为 `src/backend/*` 形式。
- mermaid 图中节点标签同步更新。
- `backend/main.py` 改为 `src/backend/main.py`。
- 依赖规则代码块同步更新，并补充说明：该规则适用于 `src/` 下**所有**遵循四层结构的模块。

**docs/ai-standards/architecture.md**

- Backend Layers 表格中的 Path 列全部更新为 `src/backend/*` 形式。
- Dependency Direction 代码块同步更新，并补充说明通用性：
  ```text
  src/<module>/api/ → src/<module>/core/ → src/<module>/engines/ → src/<module>/infrastructure/
  ```
- Composition Root 说明同步更新：
  - `backend/main.py` → `src/backend/main.py`
  - 根目录 `main.py` 仍为兼容包装器
- **Mandatory Rule** 中补充：新增模块若采用相同的四层结构，同样受 `hooks/check_architecture.py` 约束。

### 3.8 AI 入口适配文件

**AGENTS.md**

- `backend/api/ -> backend/core/ -> backend/engines/ -> backend/infrastructure/` 改为 `src/backend/*` 形式。

**.github/copilot-instructions.md**

- 同样的四层依赖方向描述更新为 `src/backend/*` 形式。

### 3.9 测试硬编码路径（tests/test_sync_template.py）

该测试使用字符串字典模拟仓库文件结构，其中硬编码了 `"backend/api/api.py"` 多处。全部替换为 `"src/backend/api/api.py"`，同时 `config.toml` 中 `project_skip_paths` 的 `"backend/"` 也需要在测试中同步替换为 `"src/backend/"`。

### 3.10 配置与脚本

**config.toml**

- `project_skip_paths` 中的 `"backend/"` 改为 `"src/backend/"`。

**scripts/template/sync_template.sh**

- `project_skip_paths` 数组中的 `"backend/"` 改为 `"src/backend/"`。

## 4. 风险与回滚

| 风险 | 缓解措施 |
|---|---|
| 移动目录后 editable install 未生效，导致 `import backend` 失败 | 修改后运行 `just sync` 或 `uv pip install -e .` 确保环境同步；CI 中也应验证 |
| 遗漏某些硬编码路径（如其他脚本、未 grep 到的文档） | 迁移后全局搜索 `backend/` 并人工复核；将 `hooks/check_architecture.py` 和 `.pre-commit-config.yaml` 的更新作为第一道防线 |
| pre-commit 的 `check-architecture` 因路径不匹配而跳过检查 | `.pre-commit-config.yaml` 的 `files` 正则必须同步更新，并在迁移后立即执行 `uv run python hooks/check_architecture.py` 验证 |

## 5. 验收清单

- [ ] `backend/` 已完整移动到 `src/backend/`，原 `backend/` 目录已删除。
- [ ] `src/backend/` 内部四层子目录（api、core、engines、infrastructure）结构完整，无文件遗漏。
- [ ] `pyproject.toml` 已配置 src-layout 包发现，使得 `from backend.main import main` 无需改动即可正常 import。
- [ ] `just run backend` 命令正常启动后端（使用 `uv run python -m backend.main`）。
- [ ] `uv run python hooks/check_architecture.py` 自动发现 `src/backend/` 模块并扫描全部四层，报告通过（0 违规）。
- [ ] `uv run python hooks/check_guidelines_consistency.py` 通过。
- [ ] `.pre-commit-config.yaml` 中 `check-architecture` 的 `files` 正则已改为通用模式 `src/[^/]+/(api|core|engines|infrastructure)`。
- [ ] `docs/architecture/system-design.md` 中所有 `backend/` 路径引用已更新为 `src/backend/`。
- [ ] `docs/ai-standards/architecture.md` 中所有 `backend/` 路径引用已更新为 `src/backend/`。
- [ ] `AGENTS.md` 和 `.github/copilot-instructions.md` 中四层依赖方向描述已更新。
- [ ] `tests/test_sync_template.py` 中所有硬编码 `"backend/api/api.py"` 已改为 `"src/backend/api/api.py"`，且测试通过。
- [ ] `config.toml` 和 `scripts/template/sync_template.sh` 中的 skip paths 已更新。
- [ ] `uv run pytest` 全量测试通过（或至少与迁移前状态一致）。
- [ ] `uv run mkdocs build` 文档构建通过。
