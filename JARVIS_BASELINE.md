# J.A.R.V.I.S — Production Baseline & Discovery Report

> **Stage:** STAGE 0 — DISCOVERY & BASELINE  
> **Status:** COMPLETED & VERIFIED  
> **Verification Date:** 2026-11-06  
> **Repository:** `c:\Users\yajat\OneDrive\Desktop\JARVIS M\JARVIS MAIN`  
> **Base Git Commit:** `31034ce` on branch `main` (uncommitted working tree preserved)  

---

## 1. System Inventory & Baseline State

### 1.1 Tool Registry Verification
- **Verified Tool Count:** **73 tools** registered in [`core/register_tools.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/register_tools.py).
- *Note:* Older test files referenced 62 tools (`test_runtime_routing_fixes.py`). The current active system has 73 functional tools, all loaded via lazy-module proxies.
- Zero tools were disabled or removed during discovery.

### 1.2 Web Search Provider Live Status
Executed provider initialization diagnostics directly in the environment:
```
[WEB] Initializing web search engine...
[WEB] Google Search : UNAVAILABLE (GOOGLE_SEARCH_API_KEY / GOOGLE_CSE_ID missing)
[WEB] Serper        : AUTH_REQUIRED (SERPER_API_KEY empty string in environment)
[WEB] Brave Search  : UNAVAILABLE (BRAVE_SEARCH_API_KEY missing / key name discrepancy)
[WEB] Fallback      : DuckDuckGo (AVAILABLE & VERIFIED)
[WEB] Web Search    : READY (DuckDuckGo fallback operational)
```
- **Active Operational Path:** DuckDuckGo fallback operates without paid API requirements.
- **Root Cause of Serper AUTH_REQUIRED:** `SERPER_API_KEY` is present as an empty string in `.env` or system environment, triggering auth headers with empty values.
- **Root Cause of Brave Search UNAVAILABLE:** `.env.example` documents `BRAVE_API_KEY`, but [`actions/web_search_providers.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/web_search_providers.py) looks for `BRAVE_SEARCH_API_KEY`.

### 1.3 Baseline Test Suite Results
A full execution across all 71 test suites in the `tests/` directory was completed:
- **Total Test Files Evaluated:** 71
- **Clean Passing Files:** 51
- **Total Tests Passed:** 999
- **Total Tests Failed:** 40
- **Timeouts (>25s subprocess limit):** 5 (`test_proactive_companion.py`, `test_universal_app_launcher.py`, `test_universal_control.py`, `test_universal_desktop_control.py`, `test_universal_social_automation.py`)
- **Key Pre-existing Failure Root Causes:**
  1. `test_tool_registry_preserves_62_tools`: Outdated assertion expecting 62 tools instead of the current 73.
  2. `test_real_startup.py`: `NameError: name 'QWebEnginePage' is not defined` in `ui.py:551` when `PyQt6-WebEngine` is not installed.
  3. `test_addressing.py`: Intent routing regex returns `OTHER` instead of `WHATSAPP_READ` for specific conversational phrasing.
  4. App launcher tests: Windows UI window verification timeout during headless testing.

---

## 2. Confirmed Code Anomalies for Stage 1 Stabilization

The discovery audit identified the following specific confirmed anomalies in the codebase:

1. **UnboundLocalError Risk in [`actions/web_search.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/web_search.py#L517):**
   - At line 517, `return answer` is executed. If `data['success']` was initially false or an exception branch was taken without defining `answer`, `UnboundLocalError` is raised.
2. **Missing Fallback Class Guard in [`ui.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/ui.py#L551):**
   - Line 49 catches `ImportError` for `PyQt6.QtWebEngineWidgets`, but line 551 unconditionally subclasses `QWebEnginePage`. On systems where WebEngine is absent, importing `ui.py` fails with `NameError`.
3. **Environment Variable Naming Mismatch:**
   - `.env.example` documents `BRAVE_API_KEY`, whereas `actions/web_search_providers.py` checks `BRAVE_SEARCH_API_KEY`.
4. **Voice Runner Exception Suppression in [`main.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/main.py#L755-L761):**
   - Voice runner watchdog catches exceptions and silently swallows errors, preventing automatic reconnection in edge disconnect states.
5. **Memory Concurrency Race Condition in [`memory/memory_manager.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/memory/memory_manager.py):**
   - `_cached_memory_data` reads outside the critical lock section in some paths, risking stale state during simultaneous typed chat and voice updates.
6. **Thread-Safe WorkflowEngine Singleton in [`agent/workflow_engine.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/agent/workflow_engine.py):**
   - Engine initializes without a reentrant lock around persistent file I/O to `config/workflows.json`.

---

## 3. Preservation Checkpoint

- **Git Working Tree:** Preserved without modification.
- **Configuration Files:** Intact (`config/api_keys.json`, `config/runtime.json`).
- **Memory Store:** Intact (`memory/long_term.json`).
- **Zero Breakage Guarantee:** All changes in Stage 1 and beyond will be verified against this 999-passed baseline.
