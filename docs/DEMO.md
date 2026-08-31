# Demo Mode Documentation

**Status**: `IMPLEMENTED`  
**Command**: `python main.py --demo`  

---

## Overview
Demo Mode provides a safe, non-destructive walkthrough of all 21 JARVIS capabilities without performing dangerous system modifications, deleting files, or modifying critical operating system settings.

---

## Execution Walkthrough

When you run `python main.py --demo`, JARVIS performs 7 verified checks:

1. **Core System Initialization**: Loads configuration and environment settings.
2. **Tool Registry Verification**: Confirms all 21 tools (`open_app`, `web_search`, `college_mode`, `camera_control`, `chrome_profile`, `whatsapp`, `discord`, etc.) are registered and validated.
3. **Unified Context Engine**: Checks current user identity (`Yajat`), active window telemetry, battery level, and camera status.
4. **Memory Engine**: Demonstrates memory entry saving, topic querying, and deletion.
5. **Security Manager**: Evaluates tool risk levels (e.g. `web_search` = `LOW`, `delete_all` = `CRITICAL`).
6. **College Mode Engine**: Executes schedule & assignment lookup.
7. **Verification Engine**: Validates disk file existence (`main.py`).

---

## Output Example
```text
============================================================
      J.A.R.V.I.S — SAFE DEMO MODE WALKTHROUGH
============================================================

[✓] STEP 1: Core System Initialization...
[✓] STEP 2: Tool Registry — 21 tools registered...
[✓] STEP 3: Unified Context Engine...
[✓] STEP 4: Memory Engine...
[✓] STEP 5: Security Manager...
[✓] STEP 6: College Mode...
[✓] STEP 7: Verification Engine...

============================================================
      ALL DEMO CHECKS PASSED — JARVIS SYSTEM FULLY OPERATIONAL
============================================================
```
