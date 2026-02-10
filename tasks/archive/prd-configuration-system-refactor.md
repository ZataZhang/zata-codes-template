# PRD: Configuration System Refactor

## Introduction & Goals

Refactor the centralized configuration management from a simple class-based `os.getenv` approach to a robust, type-safe `pydantic-settings` based system with TOML and environment variable support.

### Measurable Objectives
- Type-safe configuration with runtime validation
- Clear separation: non-sensitive defaults in `config.toml`, secrets in `.env`
- Three-layer configuration priority: env vars > TOML > code defaults
- Improved code structure following AI-Native patterns (fully qualified names, SSA)
- Maintainable and self-documenting configuration system

---

## Implementation Guide

### Tech Stack Analysis
- **Current**: `python-dotenv` + plain class with `os.getenv`
- **Target**: `pydantic-settings` with custom TOML source
- **Files importing settings.py**: 5 files across utils/, crawler/, ai_agent/
- **Encoding**: UTF-8 explicit (per CLAUDE.md Windows requirements)

### Core Logic Changes

1. **New Dependencies** (`pyproject.toml`):
   - Add `pydantic-settings>=2.0.0` to main dependencies
   - Remove `python-dotenv` (handled by pydantic-settings)

2. **Configuration Architecture**:
   ```
   ┌─────────────────┐
   │  Environment    │  (Secrets: API keys, passwords)
   │  Variables /    │  Highest Priority
   │  .env / .env.local
   └────────┬────────┘
            │
   ┌────────▼────────┐
   │   config.toml   │  (Non-sensitive defaults)
   │   [database]    │  Medium Priority
   │   [minio] etc.  │
   └────────┬────────┘
            │
   ┌────────▼────────┐
   │  Code Defaults  │  (Pydantic Field defaults)
   │  in Settings    │  Lowest Priority
   └─────────────────┘
   ```

3. **Database URL Resolution** (Hybrid Approach):
   - Priority 1: `DATABASE_URL` environment variable (complete URL)
   - Priority 2: Construct from components (`DB_HOST`, `DB_PORT`, `POSTGRES_USER`, etc.)
   - Validation: At least one complete method must be provided

4. **MinIO Credentials Resolution**:
   - Priority 1: `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`
   - Priority 2: `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` (Docker compatibility)
   - Priority 3: Defaults (`minioadmin`)

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `pyproject.toml` | Modify | Add `pydantic-settings`, remove `python-dotenv` |
| `utils/settings.py` | Rewrite | New pydantic-settings based implementation |
| `utils/database.py` | Modify | Update to use `config.database.url` or `config.resolved_database_url` |
| `utils/logger.py` | Modify | Update to use `config.app.name`, `config.log.level` |
| `.env.example` | Create | Template for all secret/sensitive configuration |
| `config.toml` | Create | Non-sensitive defaults organized by section |
| `utils/__init__.py` | Modify | Update exports if structure changes |

### Data Flow Changes

**Current (os.getenv)**:
```python
config.APP_NAME  # direct attribute
config.LOG_LEVEL  # direct attribute
config.DATABASE_URL  # direct from env
```

**New (pydantic nested)**:
```python
config.app_name  # direct attribute
config.log.level  # nested via LogSettings
config.database.url  # nested via DatabaseSettings
config.resolved_database_url  # computed property
```

---

## Global Definition of Done

- [ ] `uv run python -c "from utils.settings import config; print(config)"` executes without error
- [ ] Type annotations pass `mypy` or IDE type checking
- [ ] All consuming modules (database.py, logger.py) updated and functional
- [ ] UTF-8 encoding explicitly set in all file I/O operations
- [ ] Google-style docstrings for all public classes/functions
- [ ] AI-Native naming: fully qualified variable names, no generic `data`/`item`
- [ ] Secrets use `SecretStr` and don't appear in logs/repr

---

## User Stories

### US-001: Add pydantic-settings Dependency
**Description:** Add required dependency for type-safe configuration management.

**Acceptance Criteria:**
- [ ] `pydantic-settings>=2.0.0` added to `pyproject.toml` main dependencies
- [ ] `python-dotenv` removed (functionality covered by pydantic-settings)
- [ ] `uv lock` executed to update lock file

---

### US-002: Create .env.example Template
**Description:** Create environment variable template for all secret configurations.

**Acceptance Criteria:**
- [ ] File created at project root: `.env.example`
- [ ] Contains all database credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`)
- [ ] Contains all MinIO credentials (`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`)
- [ ] Contains API keys section (placeholder for `DASHSCOPE_API_KEY`, `OPENROUTER_API_KEY`, etc.)
- [ ] Contains application settings (`APP_NAME`, `LOG_LEVEL`)
- [ ] All values are placeholder examples, not real secrets
- [ ] Comments explain each variable's purpose

---

### US-003: Create config.toml Defaults
**Description:** Create TOML configuration file for non-sensitive defaults.

**Acceptance Criteria:**
- [ ] File created at project root: `config.toml`
- [ ] Contains `[app]` section with `name`, `log_level`
- [ ] Contains `[database]` section with `host`, `port`, `name`, `driver`, `backend`
- [ ] Contains `[chat_model]` section with `name`, `provider`, `temperature`
- [ ] Contains `[minio]` section with `endpoint`, `secure`, `bucket_raw_documents`
- [ ] Contains `[qdrant]` section with `host`, `port`, `collection_name`
- [ ] Contains `[embedding]` section with `model`, `dim`, `offline_mode`, `model_dir`
- [ ] Contains `[chunking]` section with `size`, `overlap`
- [ ] Contains `[timeouts]` section with all timeout values
- [ ] All values are sensible development defaults

---

### US-004: Refactor settings.py with pydantic-settings
**Description:** Rewrite configuration module using pydantic-settings with custom TOML source.

**Acceptance Criteria:**
- [ ] Module docstring explaining the three-layer configuration system
- [ ] `_TomlSectionSource` class implementing `PydanticBaseSettingsSource`
- [ ] All settings classes follow naming: `{Domain}Settings` (e.g., `DatabaseSettings`)
- [ ] Each nested settings class implements `settings_customise_sources()` with correct priority
- [ ] `AppSettings` aggregates all sub-configurations
- [ ] `SecretStr` used for all password/secret fields
- [ ] `resolved_database_url` property implements hybrid URL resolution
- [ ] `resolved_minio_access_key` and `resolved_minio_secret_key` properties for credential fallback
- [ ] `ensure_log_directory()` method creates log directory on startup
- [ ] `_ensure_no_proxy_for_local_services()` function sets NO_PROXY for localhost
- [ ] Global `config` instance created at module level
- [ ] AI-Native code patterns: fully qualified names, SSA, type annotations

---

### US-005: Update utils/database.py
**Description:** Update database module to use new nested configuration structure.

**Acceptance Criteria:**
- [ ] Import statement updated to use new config structure
- [ ] `DATABASE_URL` reference changed to `config.resolved_database_url`
- [ ] Type-safe access to database configuration

---

### US-006: Update utils/logger.py
**Description:** Update logger module to use new nested configuration structure.

**Acceptance Criteria:**
- [ ] Import statement updated to use new config structure
- [ ] `config.APP_NAME` changed to `config.app_name`
- [ ] `config.LOG_LEVEL` changed to `config.log.level` (or appropriate path)
- [ ] `config.LOG_FILE` changed to appropriate path access

---

### US-007: Update utils/__init__.py
**Description:** Update utils package exports if needed.

**Acceptance Criteria:**
- [ ] Verify `config` export still works correctly
- [ ] Update docstring examples if configuration access patterns changed

---

## Functional Requirements

### FR-1: Configuration Priority
The system MUST resolve configuration values in the following priority order:
1. Environment variables (including `.env` and `.env.local`)
2. Values from `config.toml` section
3. Code defaults (Pydantic Field defaults)

### FR-2: Type Safety
All configuration values MUST be type-annotated with appropriate Pydantic types:
- Strings: `str`
- Integers: `int`
- Booleans: `bool`
- Secrets: `SecretStr`
- Paths: `Path`

### FR-3: UTF-8 Encoding
All file I/O operations MUST explicitly specify `encoding="utf-8"` to ensure Windows compatibility.

### FR-4: Secret Protection
All credentials, API keys, and passwords MUST use Pydantic `SecretStr` to prevent accidental exposure in logs or tracebacks.

### FR-5: Database URL Resolution
The system MUST support two methods for database connection:
- Complete URL via `DATABASE_URL` environment variable
- Component construction from `DB_HOST`, `DB_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DB_NAME`

### FR-6: MinIO Credential Fallback
The system MUST support Docker-style MinIO credentials (`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`) as fallback to standard credentials.

### FR-7: Local Proxy Bypass
The system MUST automatically set `NO_PROXY` environment variable to include `localhost`, `127.0.0.1`, and `::1` on module import.

### FR-8: Log Directory Creation
The system MUST ensure the log directory exists on configuration initialization.

---

## Non-Goals

- **Runtime Configuration Changes**: Configuration is loaded once at import time, not dynamically reloaded
- **Configuration Validation UI**: No CLI or web UI for editing configuration
- **Encrypted Secrets**: No built-in encryption for `.env` files (use external secret management)
- **Multiple Environment Profiles**: No separate `config.dev.toml`, `config.prod.toml` (use `.env` files)
- **Configuration Schema Migration**: No versioning or migration for configuration changes
