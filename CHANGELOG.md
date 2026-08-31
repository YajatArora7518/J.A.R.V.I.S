# 📜 JARVIS CHANGELOG

All notable changes to **JARVIS AI** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-08-07

### Added
- **`jarvis_api` Python Package**: Published pip-installable package metadata via `pyproject.toml` supporting `pip install .` and `pip install -e .`.
- **Python Client SDK (`JarvisAPI`)**: Full programmatic SDK with `execute()`, `call_tool()`, `run_task()`, `get_status()`, `remember()`, `get_memory()`, `delete_memory()`, `analyze_screen()`, and `list_tools()`.
- **Production REST API Server (`jarvis_api.server`)**: FastAPI + Uvicorn REST API server on `/api/v1` with authentication (`X-JARVIS-API-KEY`), OpenAPI documentation (`/docs`), and standard library fallback.
- **Central Tool Registry (`core/tool_registry.py`)**: Parameter validation, timeouts, risk levels, and structured `ToolResult` packaging.
- **Security Manager (`core/security.py`)**: Risk classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and authorization checks.
- **State Verification Engine (`core/verification.py`)**: Post-execution state verification for processes, windows, disk state, audio volume levels, screenshots, and browser pages.
- **Startup Diagnostics (`core/health_check.py`)**: `JARVIS SYSTEM CHECK` verifying Python environment, dependencies, AI key, mic/speakers, browser, and permissions.
- **Comprehensive Developer Documentation (`docs/`)**: Documentation tree with quickstart, SDK reference, REST API reference, security policy, configuration, architecture, and developer examples.
- **Automated Test Matrix (`tests/`)**: Component test suite covering package metadata, SDK methods, REST API endpoints, tool registry, and state verification.

### Changed
- Rebranded legacy Mark references to **JARVIS** across Python files, UI, prompts, batch scripts, configuration, and documentation.
- Upgraded `open_app` and `computer_settings` to support direct Win32 binary resolution and process tree termination (`taskkill`).
