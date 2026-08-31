# JARVIS System Baseline

**Generated Date**: August 8, 2026  
**Repository Version**: 1.0.0 (Pre-Upgrade Baseline)  

---

## 1. Startup & Core Pipeline
- **Entry Point**: `main.py`
- **CLI Commands**: `jarvis`, `jarvis-api`, `jarvis-status`, `jarvis-test`
- **Startup Sequence**:
  1. Sets stdout/stderr UTF-8 encoding.
  2. Loads API key from `config/api_keys.json`.
  3. Loads system prompt from `core/prompt.txt`.
  4. Initializes 19 tools into `ToolRegistry`.
  5. Launches `JarvisUI` (PyQt6 with WebEngine 3D Canvas).
  6. Starts live Gemini audio session (`models/gemini-2.5-flash-native-audio-latest`).

---

## 2. Capability Matrix

| Component | Status | Implementation Details |
| :--- | :---: | :--- |
| **Voice Interaction** | ✅ Active | `sounddevice` 16kHz input / 24kHz output, Gemini Live API, Watchdog reset timer |
| **AI Integration** | ✅ Active | Gemini Live Audio, OpenRouter fallback, Gemini 2.5 Flash for code/summaries |
| **Tool System** | ✅ Active | 19 tools registered in `core/tool_registry.py` with parameter validation |
| **Security Manager** | ✅ Active | `RiskLevel` classification (LOW, MEDIUM, HIGH, CRITICAL), protection of `C:\Windows` paths |
| **Verification Engine** | ✅ Active | `core/verification.py` checking running processes, window titles, disk files, volume levels |
| **Memory Engine** | ✅ Active | `memory/memory_manager.py` with `long_term.json`, auto memory extraction via OpenRouter |
| **Adaptive Intelligence**| ✅ Active | `memory/adaptive_intelligence.py` for pattern prediction and routine tracking |
| **Planner & Executor** | ✅ Active | `agent/planner.py` & `agent/executor.py` for multi-step task planning & error recovery |
| **Task Queue** | ✅ Active | `agent/task_queue.py` background thread execution queue |
| **UI / HUD** | ✅ Active | `ui.py` PyQt6 overlay window with `assets/jarvis_3d_core.html` Three.js core visualizer |
| **Browser Control** | ✅ Active | `actions/browser_control.py` via Playwright Chromium automation |
| **Desktop Automation** | ✅ Active | `actions/computer_control.py`, `actions/open_app.py`, `actions/desktop.py` |
| **Screen Processing** | ✅ Active | `actions/screen_processor.py` for screenshot capture and Gemini visual description |
| **SDK & REST API** | ✅ Active | `jarvis_api/` FastAPI server (13 routes) and Python `JarvisAPI` client SDK |

---

## 3. Registered Tools Baseline (19 Tools)
1. `open_app`: Application & web service launcher.
2. `web_search`: Live internet search (DuckDuckGo / DDGS provider fallback).
3. `fetch_webpage`: URL reader and text extractor.
4. `weather_report`: Weather lookup by city.
5. `send_message`: WhatsApp / Telegram messaging.
6. `reminder`: Windows Task Scheduler reminder setter.
7. `computer_settings`: System volume, brightness, power control.
8. `screen_process`: Screenshot capture and visual analysis.
9. `youtube_video`: YouTube playback and summary.
10. `desktop_control`: Wallpaper, file organization, desk cleaning.
11. `browser_control`: Playwright navigation and web action automation.
12. `file_controller`: Directory listing, file reading/writing/deletion.
13. `code_helper`: Automated code writing and execution.
14. `dev_agent`: Software engineering task agent.
15. `computer_control`: Mouse/keyboard automation and screenshot taker.
16. `game_updater`: Steam/Epic game update and installation manager.
17. `flight_finder`: Flight schedule lookup.
18. `discord`: Discord messaging automation.
19. `windows_startup`: Startup entry registration.

---

## 4. Operational Test Baseline
- **Suite**: `python tests/run_tests.py`
- **Result**: **PASS** (100/100 checks across Core, Tools, Security, SDK, REST API, App Control, Filesystem, Browser, Voice, Memory, Task Queue).

---

## 5. Approved UI SHA-256 Hashes Baseline
- `assets/jarvis_3d_core.html`: `2054ED87618B9BF6FB68A1CC2F03DD9E3F1E06A4781146158DF964E18A37009F`
- `assets/jarvis_3d_core_holographic.html`: `D27913E85FDC99DA75B49149A1472A913A06F554CEDD64756CA889FE2CB9700F`
- `assets/jarvis_holographic_ui.html`: `6DA5CEE7943F120FD1ACFA136E38A8C1ABB7B4439D20DFDFDAD330F9AD0574DC` (Approved legitimate runtime baseline)
