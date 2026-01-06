# Cursor IDE Configuration

## Project Guidelines

This project follows specific guidelines defined in `AGENTS.md` and `CLAUDE.md`. Key points for Cursor IDE:

### Package Management
- **Always use `uv`** for Python package management
- Add dependencies: `uv add <package>` (production) or `uv add --dev <package>` (development)
- Sync dependencies: `uv sync`
- Run scripts: `uv run python <script.py>`

### Code Quality
- Use Google-style docstrings with type annotations
- Follow the documentation standards in `AGENTS.md`
- Run pre-commit checks: `uv run pre-commit run --all-files`

### Development Commands
- Install dependencies: `uv sync`
- Run main script: `uv run python main.py`
- Update pre-commit hooks: `uv run pre-commit autoupdate`

## Consistency Notes
This file should be kept in sync with `AGENTS.md` and `CLAUDE.md`. When updating project guidelines, ensure all three files are updated consistently.

See `AGENTS.md` and `CLAUDE.md` for complete project documentation.
