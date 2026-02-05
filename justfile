# Default recipe (runs when you type 'just')
default:
    @just --list

# Install all dependencies excluding dev
prod-sync:
    uv sync --no-dev

# 安装全部（主依赖 + dev + 所有 extras）
full-sync:
    uv sync --all-extras

# Sync dependencies from lock file (including dev)
sync:
    uv sync

# Start dev environment (full sync + pre-commit hooks)
dev:
    uv sync --all-extras
    uv run pre-commit install

# Run the main application
run:
    uv run python main.py

# Remove cache files and build artifacts
clean:
    @echo "Cleaning cache files..."
    @rm -rf .ruff_cache
    @rm -rf __pycache__
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @find . -type f -name "*.pyo" -delete 2>/dev/null || true
    @find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    @echo "Clean complete!"

staged_changes:
    git diff --cached > staged_changes.diff
