---
applyTo: "backend/**/*.py"
---

Use `docs/ai-standards/` as the canonical standards hub and `docs/architecture/system-design.md` as the detailed backend architecture authority.

Respect the layer boundaries:

- `backend/apps/` handles request entry, validation, and DTO conversion
- `backend/core/` owns business rules and orchestration
- `backend/capabilities/` implements pluggable platform capabilities
- `backend/infrastructure/` owns concrete integrations and external systems

Do not violate dependency direction. Cross-layer dependencies must go through `backend/core/shared/interfaces/`.

Use descriptive variable names, avoid generic placeholders like `data` or `res`, and prefer SSA-style intermediate variables in Python.

Public Python modules, classes, and functions require Google Style Docstrings. File I/O must explicitly use UTF-8 encoding.
