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

# Run tests (usage: just test [all|local|real])
#   just test        - Run local tests (no API keys needed)
#   just test all    - Run all tests
#   just test real   - Run tests requiring API keys
@test type="local":
    #!/usr/bin/env bash
    set -e
    if [ "{{type}}" = "all" ]; then
        uv run pytest tests/ -v
    elif [ "{{type}}" = "real" ]; then
        uv run pytest tests/ -v -k "expensive or not expensive"
    else
        uv run pytest tests/ -v --ignore=tests/test_model_loader_real.py -m "not expensive"
    fi


# Export all .env* files recursively into a zip archive
export-env-zip output="":
    #!/usr/bin/env bash
    uv run python - <<'PY'
    from pathlib import Path
    import sys
    import zipfile

    project_root_path = Path(r"{{justfile_directory()}}")
    configured_output_name = r"{{output}}".strip()
    default_output_directory_path = project_root_path.parent / "mysecrets"
    default_output_zip_path = default_output_directory_path / f"{project_root_path.name}.zip"
    if configured_output_name:
        configured_output_path = Path(configured_output_name)
        output_zip_path = (
            configured_output_path
            if configured_output_path.is_absolute()
            else project_root_path / configured_output_path
        )
    else:
        output_zip_path = default_output_zip_path
    output_zip_path.parent.mkdir(parents=True, exist_ok=True)
    env_file_paths = sorted(
        path
        for path in project_root_path.rglob("*")
        if path.is_file() and path.name.startswith(".env")
    )
    env_file_paths = [path for path in env_file_paths if path != output_zip_path]

    if not env_file_paths:
        sys.exit("No files starting with .env were found in this project.")

    if output_zip_path.exists():
        output_zip_path.unlink()

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zip_archive_file:
        for env_file_path in env_file_paths:
            archived_relative_path = env_file_path.relative_to(project_root_path)
            zip_archive_file.write(env_file_path, arcname=str(archived_relative_path))

    print(f"Created {output_zip_path} with {len(env_file_paths)} files:")
    for env_file_path in env_file_paths:
        archived_relative_path = env_file_path.relative_to(project_root_path)
        print(f" - {archived_relative_path}")
    PY
