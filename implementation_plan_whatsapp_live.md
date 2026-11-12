# Implementation Plan: WhatsApp Desktop Live Validation & Production Hardening

## Overview & Objectives
Harden and live-validate the existing WhatsApp functionality in JARVIS Windows desktop assistant without breaking any existing functionality.
Enforce the core rule: **WhatsApp Desktop is the default for all normal WhatsApp commands; WhatsApp Web is ONLY opened when explicitly requested ("WhatsApp Web").**

## Audit Findings & Targeted Fixes

### 1. `core/command_pipeline.py`
- **Scoping Bug (Line 976):** An inline `import re` inside `process_user_command` marks `re` as local throughout the entire function, causing `UnboundLocalError` when `_wa_msg_match = re.search(...)` executes at line 624.
  - *Fix:* Remove redundant `import re` at line 976 (`import re` is already at line 6).
- **Hinglish Message Extraction & Conversational Fillers:**
  - Support leading conversational prefixes (`ab`, `fir`, `phir`, `bhai`, `jarvis`).
  - Support multi-word contacts (`[a-zA-Z0-9_\s]+?`).
  - Extract exact requested message body without truncating user content.
- **Contextual Pronoun Resolution ("usko", "usse", "wahi"):**
  - Run pronoun resolution before message pattern matching or support pronoun patterns (`(usko|usse) bol (.+)`) resolving to `_CONVERSATION_CONTEXT["last_contact"]`.
  - Preserve existing Notepad typing context (`Notepad kholo` -> `Isme hello type karo`).
- **Sequential Multi-Step Pipeline ("WhatsApp kholo aur Mumma ko hello bhej"):**
  - Order: (1) Open WhatsApp Desktop -> (2) Verify Desktop ready (abort if fails) -> (3) Resolve contact (abort if fails) -> (4) Send message -> (5) Verify send (do not claim success if verification fails) -> (6) Report completion.
- **Voice & Video Call Direct Interception:**
  - Route Hinglish voice/video call commands (`Mumma ko call laga`, `Mumma ko video call laga`, `Mummy ko call kar`, `Maa ko WhatsApp call laga`) to desktop call executor with contact resolution.
- **Telemetry Enhancement:**
  - Ensure `target_app` and `target_contact` are explicitly logged in telemetry.

### 2. `actions/windows_whatsapp_desktop_executor.py`
- **Truthful Message Send Verification:**
  - If window verification fails (`verified = False`), do NOT return `success = True`. Return `success = False` and an honest status.
- **Dry-Run / Test Boundary for Calls (Rule 11):**
  - Add check for `os.environ.get("JARVIS_DRY_RUN") == "1" or os.environ.get("PYTEST_CURRENT_TEST")`.
  - In test/dry-run mode: verify HWND, bounds (>100x100), and target coordinate calculation, but do NOT click the call button. Return safe verified simulation.
  - In manual live run: actually click the button.
- **Contact Ambiguity & Alias Resolution:**
  - Strip leading conversational filler words before alias lookup.
  - Unknown contacts must never silently resolve to another person.
  - Maintain case-insensitive, whitespace-tolerant alias resolution from `config/important_contacts.json`.

### 3. `core/verification.py`
- **Distinguish WHATSAPP_DESKTOP vs WHATSAPP_WEB vs UNKNOWN:**
  - Never allow a browser tab containing "WhatsApp Web" in its title to satisfy Desktop launch verification.
  - Check actual desktop process names (`WhatsApp.exe`, `WhatsApp.Root.exe`, `WhatsAppDesktop.exe`) and native Windows window class.
  - Return `target_type`: `WHATSAPP_DESKTOP`, `WHATSAPP_WEB`, or `UNKNOWN`.

### 4. `actions/open_app.py`
- Verify that normal `whatsapp` opens Desktop and never silently falls back to Web.
- Verify explicit `whatsapp web` routes strictly to Yajat Chrome profile.

## Verification & Testing Plan
1. Baseline test suite (`tests/run_tests.py` + `tests/test_whatsapp_production_upgrade.py`).
2. Targeted WhatsApp unit and integration tests covering:
   - Routing: Normal -> Desktop; Explicit Web -> Yajat Chrome.
   - Contact resolution: Aliases (Mumma, Mummy, Maa, Mom, Papa, Dad), ambiguity, unknown passthrough.
   - Parsing: All required Hinglish patterns.
   - Follow-up context: `Mumma ko hello bhej` -> `Ab usko bol main 10 minute mein aaunga`.
   - Notepad typing context preservation.
   - Multi-step sequential execution.
   - Voice/Video call button calculation & dry-run guard.
3. Live Windows discovery & process verification.
4. Regression run: 0 regressions allowed.
5. Final Validation Report generation with honest status classification.
