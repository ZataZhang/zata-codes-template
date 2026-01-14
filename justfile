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

# Run pre-commit checks on all files
lint:
    uv run pre-commit run --all-files

# Run pre-commit checks (alias for lint)
format: lint

# Run pre-commit checks (alias for lint)
check: lint

# Run tests with pytest
test:
    uv run pytest

# Run pre-commit on all files
pre-commit:
    uv run pre-commit run --all-files

# Install pre-commit hooks
hooks:
    uv run pre-commit install

# Update pre-commit hook versions
update-hooks:
    uv run pre-commit autoupdate

# Add a production dependency
add pkg:
    uv add {{pkg}}

# Add a development dependency
add-dev pkg:
    uv add --dev {{pkg}}

# Remove a dependency
remove pkg:
    uv remove {{pkg}}
