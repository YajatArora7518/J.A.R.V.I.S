# 🤖 JARVIS AI — Comprehensive Project Documentation

Welcome to the official technical documentation for **JARVIS AI**, a real-time, cross-platform, autonomous personal AI assistant engineered for Windows, macOS, and Linux.

---

## 📑 Table of Contents
1. [Overview & Vision](#1-overview--vision)
2. [System Architecture](#2-system-architecture)
3. [Core Subsystems & File Layout](#3-core-subsystems--file-layout)
4. [Tool Execution & Security Pipeline](#4-tool-execution--security-pipeline)
5. [State Verification Engine](#5-state-verification-engine)
6. [Configuration & API Setup](#6-configuration--api-setup)
7. [Voice & Command Reference](#7-voice--command-reference)
8. [Testing & Health Diagnostics](#8-testing--health-diagnostics)
9. [Troubleshooting Guide](#9-troubleshooting-guide)

---

## 1. Overview & Vision

JARVIS is designed to bridge the gap between human voice intent and desktop operating system automation. Operating with **zero cloud subscription overhead**, it leverages:
- **Gemini Live API**: Real-time continuous speech-to-speech bidirectional audio and multimodal vision streaming.
- **OpenRouter API**: Cost-free routing for background action processing and intent detection.
- **Deterministic Tool Execution**: Safety-checked tool registry with real-time post-action state verification.

---

## 2. System Architecture

```
                               ┌───────────────────────────┐
                               │     User Voice / Text     │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │  Gemini Live / OpenRouter │
                               └─────────────┬─────────────┘
                                             │  Intent / Tool Call
                                             ▼
                               ┌───────────────────────────┐
                               │       Tool Registry       │
                               │   (Schema Validation)     │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │     Security Manager      │
                               │  (Risk: LOW/MED/HIGH/CRIT)│
                               └─────────────┬─────────────┘
                                             │  Authorized Execution
                                             ▼
                               ┌───────────────────────────┐
                               │     Action Executors      │
                               │ (Win32/Pycaw/Playwright)  │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │    Verification Engine    │
                               │ (Process/Window/Disk/Audio)│
                               └─────────────┬─────────────┘
                                             │  Verified Result
                                             ▼
                               ┌───────────────────────────┐
                               │   JARVIS Audio/Log Response│
                               │    & Memory Persistence   │
                               └───────────────────────────┘
```

---

## 3. Core Subsystems & File Layout

| Directory / File | Description |
|---|---|
| [main.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/main.py) | Application entry point, Gemini Live WebSocket loop, tool dispatcher, audio IO stream. |
| [ui.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/ui.py) | Graphical HUD interface with adjustable transparency, status indicators, and live log view. |
| [or_client.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/or_client.py) | OpenRouter LLM client for cost-effective JSON generation and vision calls. |
| [setup.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/setup.py) | Automated environment setup, dependency installer, Playwright browser installer, health checker. |
| [start_jarvis.bat](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/start_jarvis.bat) | Windows batch file shortcut to launch JARVIS. |
| **`core/`** | Core infrastructure engine |
| ├── [tool_registry.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/tool_registry.py) | Unified Tool Registry managing parameter validation, timeouts, structured `ToolResult`. |
| ├── [security.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/security.py) | Security Manager for risk level classification and user confirmation flow. |
| ├── [verification.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/verification.py) | Windows Post-Action State Verification Engine. |
| ├── [health_check.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/health_check.py) | System diagnostics & component health checker. |
| └── [register_tools.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/register_tools.py) | Auto-initializer registering all capabilities into `default_tool_registry`. |
| **`actions/`** | Specialized action handlers |
| ├── [open_app.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/open_app.py) | Binary path resolution & process launcher with post-launch verification. |
| ├── [computer_settings.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/computer_settings.py) | System volume (Pycaw), process termination (`taskkill`), display settings. |
| ├── [computer_control.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/computer_control.py) | Mouse, keyboard, hotkeys, screenshots with byte-size verification. |
| ├── [browser_control.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/browser_control.py) | Playwright web browser automation (search, click, type, scroll, extract). |
| ├── [file_controller.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/file_controller.py) | Filesystem management (CRUD, move, rename, search, disk usage). |
| ├── [file_processor.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/file_processor.py) | Document, image, audio, video, and PDF file processing. |
| ├── [screen_processor.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/screen_processor.py) | Real-time visual screen capture and webcam vision analysis. |
| ├── [dev_agent.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/dev_agent.py) | Autonomous multi-file project developer & code executor. |
| ├── [code_helper.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/code_helper.py) | Single-file code generation, editing, and execution. |
| ├── [game_updater.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/game_updater.py) | Steam & Epic Games downloader and game update scheduler. |
| └── [youtube_video.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/actions/youtube_video.py) | YouTube video search, playback control, and transcript summarization. |
| **`agent/`** | Multi-step task planner |
| ├── [planner.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/agent/planner.py) | Task decomposition planner. |
| ├── [executor.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/agent/executor.py) | Sequential step executor. |
| └── [task_queue.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/agent/task_queue.py) | Background task queue manager with priority handling. |
| **`memory/`** | Memory subsystem |
| └── [memory_manager.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/memory/memory_manager.py) | Persistent long-term JSON memory & automatic fact extractor. |
| **`tests/`** | Functional verification suite |
| └── [run_tests.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/tests/run_tests.py) | End-to-end component test suite with status matrix reporter. |

---

## 4. Tool Execution & Security Pipeline

Every tool call generated by the AI model follows a strict pipeline:

1. **Parameter Schema Validation**: Checks required arguments against tool definitions in [tool_registry.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/tool_registry.py).
2. **Risk Classification**: [security.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/security.py) assigns a risk level:
   - `LOW`: Search, file read, system info, memory store.
   - `MEDIUM`: Application opening, setting changes, web browsing.
   - `HIGH`: File deletion, app termination, code execution.
   - `CRITICAL`: Bulk deletion, disk format.
3. **Security Check**: High-risk actions trigger a user authorization check.
4. **Tool Execution**: Executes underlying Python/Win32 action handler.
5. **Post-Action State Verification**: Verifies the outcome using system APIs.
6. **Structured Result Packaging**: Returns a standardized `ToolResult` object.

---

## 5. State Verification Engine

The state verification engine ([verification.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/verification.py)) ensures JARVIS never falsely reports success:

- `verify_app_launched(app_name, timeout=4.0)`: Checks `psutil` process list and `pygetwindow` titles.
- `verify_process_closed(app_name, timeout=3.0)`: Confirms process termination.
- `verify_file_exists(path, min_bytes=0)`: Confirms file existence and minimum size.
- `verify_file_deleted(path)`: Confirms removal from disk.
- `verify_screenshot_created(path)`: Confirms screenshot image byte integrity.
- `verify_volume_changed(target_level)`: Reads master scalar volume from Windows audio endpoint via `pycaw`.
- `verify_browser_loaded(page, keyword)`: Checks Playwright Chromium page state.

---

## 6. Configuration & API Setup

Configuration is stored in `config/api_keys.json`:

```json
{
  "gemini_api_key": "YOUR_FREE_GEMINI_API_KEY",
  "openrouter_api_key": "OPTIONAL_OPENROUTER_KEY",
  "os_system": "windows"
}
```

- **Gemini API Key**: Required for real-time speech and vision (obtain free key at [Google AI Studio](https://aistudio.google.com/)).
- **OpenRouter API Key**: Optional for free-tier LLM delegation (obtain free key at [OpenRouter](https://openrouter.ai/)).

---

## 7. Voice & Command Reference

### 🚀 Application Control
- *"Jarvis, open Chrome."*
- *"Jarvis, launch VS Code."*
- *"Jarvis, close Spotify."*
- *"Jarvis, close Notepad."*

### 🔊 Audio & System Settings
- *"Jarvis, set volume to 50 percent."*
- *"Jarvis, increase volume."*
- *"Jarvis, mute audio."*
- *"Jarvis, tell me my CPU and RAM usage."*

### 👁️ Vision & Screen Processing
- *"Jarvis, what's on my screen?"*
- *"Jarvis, take a screenshot."*
- *"Jarvis, look at my camera."*

### 📁 Filesystem Operations
- *"Jarvis, create a folder named Project on my Desktop."*
- *"Jarvis, search for my resume in Documents."*
- *"Jarvis, list the files on my Desktop."*

### 🌐 Web Browser & Search
- *"Jarvis, search the web for quantum computing advances."*
- *"Jarvis, open YouTube and play lofi beats."*
- *"Jarvis, search flights from New York to London for tomorrow."*

### 💻 Developer & Workspace
- *"Jarvis, prepare my coding workspace."*
- *"Jarvis, write a Python script to monitor network ping and save it to my Desktop."*

---

## 8. Testing & Health Diagnostics

### Run Environment Diagnostics
```bash
python setup.py
```
Validates Python runtime, pip dependencies, API configuration, microphone & speaker devices, Playwright Chromium, and Windows control permissions.

### Run Functional Integration Tests
```bash
python tests/run_tests.py
```
Executes functional tests for ToolRegistry, Filesystem CRUD, Application Lifecycle, Screen Capture, Memory Engine, Security Manager, and Browser Automation, displaying a `JARVIS FINAL VERIFICATION` summary report.

---

## 9. Troubleshooting Guide

| Issue | Cause | Fix |
|---|---|---|
| `api_keys.json missing` | Configuration file not created | Run `python setup.py` or create `config/api_keys.json` manually with your Gemini API key. |
| `Microphone missing` | Audio input device disabled or disconnected | Check system sound settings and ensure a microphone is connected. |
| `Chromium binary not found` | Playwright browsers not installed | Run `python -m playwright install chromium`. |
| `pyautogui FailSafeTrigger` | Mouse moved to top-left screen corner | PyAutoGUI safety feature triggered. Keep mouse still during automated operations. |

---

*Engineered for maximum reliability, speed, and intelligence.* 🚀
