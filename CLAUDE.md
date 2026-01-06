# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Note**: This file should be kept consistent with `AGENTS.md` (general AI agent guidelines) and `.cursor/commands/cursor.md` (Cursor IDE configuration). See `GUIDELINES_MAINTENANCE.md` for consistency maintenance guidelines.

## Project Overview

This is a minimal Python project template (skeleton) with pre-configured hooks and common utilities for code quality and rapid project setup. It's designed to be cloned and reused for new Python projects.

## Package Management (CRITICAL)

**Always use `uv` exclusively for all Python package management and execution:**

- Add dependency: `uv add <package>` (production) or `uv add --dev <package>` (development)
- Remove dependency: `uv remove <package>`
- Sync/install dependencies: `uv sync`
- Run scripts: `uv run python <script.py>`
- Run tools: `uv run <tool>` (e.g., `uv run pytest`)
- Update lock file: `uv lock`

**Never use pip, pip install, requirements.txt, poetry, or other tools.** Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. Virtual environment is auto-managed in `.venv`.

## Code Quality & Hooks

This project uses `pre-commit` for automated code quality checks before commits:

1. **Install hooks** (first time setup):
   ```powershell
   uv add --dev pre-commit
   uv run pre-commit install
   ```

2. **Run checks manually** (on all files):
   ```powershell
   uv run pre-commit run --all-files
   ```

3. **Update hook versions**:
   ```powershell
   uv run pre-commit autoupdate
   ```

The `.pre-commit-config.yaml` includes:
- Basic file hygiene (trailing whitespace, EOF fixer, YAML/TOML validation)
- Large file prevention (max 50MB)
- Python debug statement detection (pdb/ipdb)
- Ruff linter and formatter (replaces Black/Flake8)

## Architecture

### Utils Module Structure

The `utils/` directory contains reusable, project-agnostic utilities:

1. **`utils/settings.py`**: Centralized configuration management
   - Loads environment variables using `dotenv`
   - Exposes configuration via a `Config` class and `config` singleton
   - Manages paths (BASE_DIR, LOG_DIR, LOG_FILE)
   - Controls log levels via `LOG_LEVEL` environment variable
   - **Pattern**: All `os.getenv` calls should be centralized here; other modules import from `config`

2. **`utils/logger.py`**: Singleton logger implementation
   - Reads config from `utils.settings.config`
   - Dual output: console (stdout) + file
   - Windows-aware UTF-8 encoding handling
   - Includes `log_error_to_database()` method (currently references non-existent database models - template for extension)
   - **Usage**: `from utils.logger import logger` then `logger.info(...)`, `logger.error(...)`, etc.

3. **`utils/helpers.py`**: Stateless utility functions
   - Currently minimal - placeholder for pure functions
   - Keep functions small, well-documented (Google-style docstrings), and framework-agnostic

### Known Issues

- `utils/logger.py` imports from `config.settings` (line 9) but the module is actually at `utils.settings` - this will cause import errors
- `utils/logger.py:80-105` references non-existent database models (`dwcrawler.database.connection`, `dwcrawler.models.database.CrawlerErrorLog`) - this is template code to be customized or removed

## Documentation Standards (Google Style)

All code must follow Google-style docstrings with type annotations:

```python
def function_name(param1: str, param2: int) -> bool:
    """执行某个功能的函数。

    这是一个详细描述函数用途的段落。

    Args:
        param1 (str): 参数1的描述
        param2 (int): 参数2的描述

    Returns:
        bool: 返回值的描述

    Raises:
        ValueError: 当参数无效时抛出

    Examples:
        >>> function_name("hello", 42)
        True
    """
    pass
```

- Module-level docstrings required for all modules
- Public functions/classes require complete docstrings
- Use type annotations for all function signatures
- Use `# TODO: 说明` for pending tasks

## Platform-Specific Notes

This template is configured for Windows development:
- Use PowerShell syntax for shell commands
- UTF-8 encoding is explicitly handled in logger and should be used for file operations
- File paths use `pathlib.Path` for cross-platform compatibility

## Common Commands

- **Run main script**: `uv run python main.py`
- **Install new dependency**: `uv add <package-name>`
- **Run pre-commit checks**: `uv run pre-commit run --all-files`
- **Create .env file**: Copy environment variables to `.env` in project root (loaded by `utils/settings.py`)
