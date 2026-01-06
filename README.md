# Zata Codes Template

一套极简的 Python 项目骨架，带好用的 hooks 与通用工具集合，方便你在任何新项目里直接复用。

## Hooks 安装
本模板使用 [`pre-commit`](https://pre-commit.com/) 统一管理代码提交前的质量保障，配置在 `.pre-commit-config.yaml` 中，涵盖基础文件卫生检查与 Ruff（Lint + Format）。第一次克隆模板后的推荐流程：

1. **安装依赖**
   ```powershell
   pip install pre-commit
   ```
   如果你偏好隔离环境，可先创建虚拟环境（`python -m venv .venv` 并 `.\.venv\Scripts\activate`）。
2. **安装 git hooks**
   ```powershell
   pre-commit install
   ```
   这会在 `.git/hooks/pre-commit` 中落地 hook，后续每次 `git commit` 会自动运行。
3. **首次全量检查（可选但推荐）**
   ```powershell
   pre-commit run --all-files
   ```
   这样可以让 hook 自动修复尾随空格、统一文件结尾，并用 Ruff 检查/格式化已有代码。

> 若要升级 hook 中的依赖，执行 `pre-commit autoupdate`，确认 `.pre-commit-config.yaml` 中的版本无误后再提交。

## utils 目录填充
`utils/` 收纳所有跨项目都能复用的底层能力，建议保持纯函数/可注入式配置，避免引入业务耦合。

### `utils/settings.py`
- 负责集中管理环境变量、路径计算、以及对外暴露的配置对象（如 `LOG_LEVEL`、`LOG_FILE`）。
- 模板已引入 `dotenv`，可在根目录创建 `.env`，再在此处统一加载：
  ```python
  load_dotenv()
  BASE_DIR = Path(__file__).resolve().parent.parent
  LOG_DIR = BASE_DIR / "logs"
  LOG_FILE = LOG_DIR / "app.log"
  LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = os.getenv("LOG_LEVEL", "INFO")
  LOG_DIR.mkdir(exist_ok=True)
  class Config:
      LOG_LEVEL = LOG_LEVEL
      LOG_FILE = LOG_FILE
  config = Config()
  ```
- 推荐只在这里调用 `os.getenv`，其余模块都从 `config`（或显式导出的常量）读取，便于测试与集中修改。

### `utils/logger.py`
- 已实现一个简单的单例 `Logger`，会读取 `config.LOG_LEVEL` 与 `config.LOG_FILE`，同时把日志输出到控制台与文件，并在 Windows 上处理 UTF-8。
- 你只需保证 `config` 中的路径/等级可用，然后在任意模块使用：
  ```python
  from utils.logger import logger
  logger.info("Crawler started")
  ```
- `log_error_to_database` 示例展示了如何扩展日志落库，如无数据库可删除或根据自身 ORM 改写。

### `utils/helpers.py`
- 放置无状态、可复用的小工具，方便不同项目直接复制使用。
- 可以按需补充，如格式化时间、批量重试等。示例：
  ```python
  from datetime import datetime

  def utc_ts() -> str:
      """返回 ISO8601 UTC 时间戳，便于日志或文件名统一。"""
      return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
  ```
- 建议保持函数粒度小且有良好 docstring，方便团队快速查阅。

完善好 `utils/` 后，这个仓库就可以作为你新的 Python 项目脚手架，直接复制即可开工。欢迎根据自身习惯继续扩展更多通用工具模块（如 `http.py`、`retry.py` 等）。
