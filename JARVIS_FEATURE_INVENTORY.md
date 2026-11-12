# J.A.R.V.I.S — Complete Feature & Tool Inventory

> **Baseline Inventory:** 73 Registered Tools Verified  
> **Date:** 2026-11-06  
> **Workspace:** `c:\Users\yajat\OneDrive\Desktop\JARVIS M\JARVIS MAIN`  

---

## 1. Registered Tools Inventory (73 Tools)

All 73 tools are registered in [`core/register_tools.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/register_tools.py) and managed by [`core/tool_registry.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/tool_registry.py).

### 1.1 Web, Search & Information Tools (8 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 1 | `web_search` | LOW | Multi-provider internet search with automatic cascading fallback | `query` (str), `num_results` (int) |
| 2 | `web_research` | LOW | Two-pass grounded research engine with source synthesis | `query` (str), `max_sources` (int) |
| 3 | `browser_search` | LOW | Direct browser search fallback via CDP Chrome | `query` (str), `engine` (str) |
| 4 | `fetch_webpage` | LOW | Clean readable text extraction from web URLs with SSRF protection | `url` (str), `max_chars` (int) |
| 5 | `weather_report` | LOW | Live weather and forecast information | `city` (str), `days` (int) |
| 6 | `flight_finder` | LOW | Flight lookup and price estimation | `origin` (str), `destination` (str), `date` (str) |
| 7 | `store_search` | LOW | Microsoft Store application and game search | `query` (str) |
| 8 | `google_search_website`| LOW | Targeted site-specific search query generator | `site` (str), `query` (str) |

### 1.2 Browser Automation Tools (5 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 9 | `browser_control` | MEDIUM | Playwright-driven Chrome browser control (CDP port 9222) | `action` (go_to, click, type, scroll), `url`, `selector` |
| 10 | `open_browser_url` | MEDIUM | Opens specific URL in dedicated 'Yajat' Chrome profile | `url` (str), `new_tab` (bool) |
| 11 | `browser_tab_manager` | MEDIUM | Inspect, switch, and close active Chrome tabs | `action` (list, switch, close), `tab_id` |
| 12 | `browser_page_extractor`| LOW | Extracts DOM accessibility tree and structured tables | `selector` (str), `format` (text/json) |
| 13 | `browser_cookie_session`| HIGH | Validates authenticated browser sessions without credential exposure | `service` (discord, gmail, etc.) |

### 1.3 Media & YouTube Tools (5 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 14 | `youtube_video` | LOW | YouTube video playback, trending extraction, and summaries | `action` (play, summarize, trending), `query` |
| 15 | `youtube_browser` | LOW | Interactive browser-based YouTube navigation and control | `action` (search, play, pause, seek), `query` |
| 16 | `play_music` | LOW | Desktop media playback via default player or Spotify | `song_name` (str), `platform` (str) |
| 17 | `media_control` | LOW | OS media key control (play, pause, next, volume) | `action` (play_pause, next, prev, stop) |
| 18 | `volume_control` | LOW | System master audio volume adjustment and muting | `level` (int 0-100), `mute` (bool) |

### 1.4 Communication & Social Platforms (10 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 19 | `whatsapp` | MEDIUM | Desktop-first WhatsApp automation (open, chat, call) | `action` (open, send, read, call), `contact`, `message` |
| 20 | `whatsapp_automation`| MEDIUM | CDP/Web WhatsApp controller fallback | `action` (send, read, call), `recipient`, `text` |
| 21 | `send_message` | MEDIUM | Generic messaging dispatcher across registered platforms | `platform`, `receiver`, `message_text` |
| 22 | `discord_control` | MEDIUM | Discord desktop/web navigation, channels, and messaging | `action` (open, send, read), `channel`, `message` |
| 23 | `telegram_control` | MEDIUM | Telegram automation via desktop protocol or CDP | `action` (open, send, read), `contact`, `message` |
| 24 | `instagram_control` | MEDIUM | Instagram direct messages and notification checker | `action` (open, check_dms), `target` |
| 25 | `gmail_control` | MEDIUM | Email summary and inbox awareness | `action` (check_inbox, search), `query` |
| 26 | `contact_directory` | LOW | Contact resolution and phone/handle lookup | `query` (str), `platform` (str) |
| 27 | `social_chat` | MEDIUM | Conversational social command parser and executor | `raw_command` (str) |
| 28 | `call_contact` | HIGH | Outgoing voice/video call dispatcher (requires user confirmation)| `contact` (str), `platform` (str), `type` (audio/video) |

### 1.5 System, Desktop & Window Control (14 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 29 | `open_app` | MEDIUM | Desktop-first application launcher with window verification | `app_name` (str), `args` (str) |
| 30 | `close_app` | HIGH | Safely terminates running Windows application | `app_name` (str), `force` (bool) |
| 31 | `computer_control` | HIGH | OS mouse, keyboard, and coordinate interaction primitives | `action` (click, type, hotkey, scroll, press) |
| 32 | `computer_settings` | HIGH | Windows system configuration (sleep, display, power) | `setting` (str), `value` (str) |
| 33 | `desktop_control` | MEDIUM | Desktop icon management, wallpaper changer, window tiling | `action` (wallpaper, organize, clean) |
| 34 | `windows_system_controller`| HIGH| Direct Win32 process and power controller | `action` (shutdown, restart, lock, sleep) |
| 35 | `windows_service_control`| HIGH | Windows service manager (start, stop, inspect) | `service_name` (str), `action` (start, stop, status) |
| 36 | `cmd_control` | HIGH | Command line execution with safety filters | `task` (str), `visible` (bool) |
| 37 | `file_controller` | HIGH | File system manager (create, write, read, delete, list) | `action` (create, write, read, delete, list), `path` |
| 38 | `script_executor` | HIGH | Executes temporary automation scripts | `script_type` (python/powershell), `code` (str) |
| 39 | `typing_tool` | MEDIUM | Smart keyboard typing with human latency simulation | `text` (str), `press_enter` (bool) |
| 40 | `screen_lock` | MEDIUM | Locks Windows workstation | None |
| 41 | `app_launcher` | MEDIUM | Canonical application resolution and launch | `app` (str) |
| 42 | `app_registry_tool` | LOW | Lists all detected installed applications and shortcuts | `filter` (str) |

### 1.6 Vision, Camera & Screen Perception (5 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 43 | `screen_process` | LOW | Screen capture and Gemini multimodal vision reasoning | `text` (query), `angle` ("screen" / "camera") |
| 44 | `visual_agent` | MEDIUM | Observe -> Plan -> Act -> Verify desktop visual agent | `action_type`, `target`, `text`, `coords` |
| 45 | `screenshot` | LOW | Captures active display or primary monitor to disk | `path` (optional), `display_index` (int) |
| 46 | `camera_capture` | LOW | Captures webcam frame for user or environmental awareness | `camera_index` (int), `save_path` (str) |
| 47 | `screen_element_finder`| LOW | Locates screen coordinates for named visual elements | `description` (str), `confidence` (float) |

### 1.7 Memory, Context & Adaptive Intelligence (8 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 48 | `memory_manager` | LOW | Long-term memory query, remember, and forget | `action` (save, get, delete), `category`, `key`, `value` |
| 49 | `adaptive_intelligence`| LOW| Analyzes user interaction patterns and habits | `action` (learn, get_habits, decay) |
| 50 | `user_profile` | LOW | User preference and identity state manager | `action` (get, update), `field`, `value` |
| 51 | `notes_manager` | LOW | Personal quick notes and scratchpad storage | `action` (add, list, delete), `title`, `content` |
| 52 | `reminder` | LOW | Schedules time-based user notifications | `date` (YYYY-MM-DD), `time` (HH:MM), `message` |
| 53 | `conversation_history`| LOW | Multi-turn conversational context queries | `turns` (int), `filter_role` (str) |
| 54 | `clipboard_manager` | LOW | Read/write Windows system clipboard | `action` (get, set), `content` (str) |
| 55 | `session_manager` | LOW | Manages active JARVIS working sessions | `action` (save_session, restore_session) |

### 1.8 Planning, Workflow & Development (10 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 56 | `planner` | LOW | Multi-step task decomposition into executable tool chains | `goal` (str), `max_steps` (int) |
| 57 | `workflow_engine` | MEDIUM | Saved, replayable named workflows engine | `action` (create, run, list, delete), `name` |
| 58 | `error_handler_tool` | LOW | Root-cause error analysis and automated replan | `error_text` (str), `failed_step` (dict) |
| 59 | `code_helper` | MEDIUM | Generates, edits, and reviews programming code | `action` (write, edit, explain), `description`, `lang` |
| 60 | `dev_agent` | MEDIUM | Autonomous coding assistant with file awareness | `task` (str), `repo_path` (str) |
| 61 | `game_updater` | MEDIUM | Steam and Epic Games library updater and launch coordinator | `action` (update, install, list), `game_name` |
| 62 | `package_manager` | HIGH | Python pip / system package inspection and installation | `action` (install, list), `package_name` |
| 63 | `git_controller` | MEDIUM | Local Git repository status, diff, and commit manager | `action` (status, diff, commit), `repo_path` |
| 64 | `macro_recorder` | MEDIUM | Records and replays repeated desktop user actions | `action` (record, play, save), `macro_name` |
| 65 | `college_mode` | LOW | Study schedule and academic timetable assistant | `action` (get_schedule, next_class, assignments) |

### 1.9 System Diagnostics & Telemetry (8 Tools)
| # | Tool Name | Risk Level | Description | Key Parameters |
|---|---|---|---|---|
| 66 | `system_telemetry` | LOW | Real-time CPU, RAM, GPU, battery, and disk telemetry | None |
| 67 | `self_diagnostics` | LOW | Comprehensive health audit across all internal subsystems | `subsystem` (optional) |
| 68 | `network_diagnostics`| LOW | Ping, DNS resolution, and internet latency tester | `host` (str), `timeout` (float) |
| 69 | `audio_diagnostics` | LOW | Audio input/output device and level verification | None |
| 70 | `process_inspector` | LOW | List running Windows processes and resource usage | `filter_name` (str), `top_n` (int) |
| 71 | `service_inspector` | LOW | Windows services status and startup type auditor | `service_name` (str) |
| 72 | `shutdown_jarvis` | HIGH | Cleanly stops all JARVIS background threads and UI | None |
| 73 | `restart_jarvis` | HIGH | Clean restart of the JARVIS process | None |

---

## 2. Intent Router Classification Inventory (38 Intents)

Managed in [`core/intent_router.py`](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/intent_router.py):

1. `TASK_MANAGER` — Open Windows Task Manager or list running tasks.
2. `DRAFT_TEXT` — Drafting emails, messages, or notes without sending.
3. `SOCIAL_CHAT` — Natural messaging commands with pronouns ("usko bol...").
4. `YOUTUBE_VIDEO` — Video play, summarization, and trending commands.
5. `CONTACT_DIRECTORY` — Contact lookups and directory queries.
6. `TIME` / `MIC` / `CAMERA` / `SCREEN` — Quick hardware and time queries.
7. `COMPUTATION` — Inline math and scientific calculations.
8. `SYSTEM_TELEMETRY` — Performance vitals (CPU, GPU, RAM, battery).
9. `FILE_ACTION` — File creation, reading, moving, and deletion.
10. `SERVICE_ACTION` — Windows service management.
11. `SCRIPT_ACTION` — Script generation and execution.
12. `STARTUP_ACTION` — Windows startup program queries.
13. `SCREENSHOT` — Capturing the screen to disk.
14. `VISUAL_AGENT` — Autonomous visual interaction.
15. `WORKFLOW` — Replaying named workflows.
16. `MACRO` — Desktop macro recording and playback.
17. `NOTES` — Creating and reading notes.
18. `USER_PROFILE` — Reading or updating user profile details.
19. `REMINDER` — Setting time-based reminders.
20. `CLOSE_APP` — Terminating applications.
21. `STORE_SEARCH` — Searching Microsoft Store.
22. `GOOGLE_WEBSITE` — Targeted search on a website.
23. `WEB_SEARCH` — General real-time web search.
24. `COMMUNICATION` — General communication dispatch.
25. `SERVICE_DISCOVERY` — Discovering available integrations.
26. `AWARENESS` — Environmental context and idle alerts.
27. `DISCORD` — Discord messaging and navigation.
28. `WHATSAPP_ACTION` — WhatsApp operations.
29. `WHATSAPP_READ` — Reading WhatsApp messages.
30. `WHATSAPP_WEB` — Explicit WhatsApp Web access.
31. `TELEGRAM` — Telegram messaging.
32. `INSTAGRAM` — Instagram direct messages.
33. `COLLEGE` — Academic schedule and study tasks.
34. `SENSITIVE` — High-risk actions requiring elevation.
35. `COMPLEX_PLANNER` — Multi-step goal decomposition.
36. `SCREEN_VISION` — Screen analysis questions.
37. `DIAGNOSTICS` — Subsystem status queries.
38. `OTHER` — Fallback to general conversational LLM.

---

## 3. Web Search Provider Baseline

| Provider | Current Baseline Status | Reason | Target Upgrade (Stage 2-3) |
|---|---|---|---|
| **Google Search API** | UNAVAILABLE | `GOOGLE_SEARCH_API_KEY` & `GOOGLE_CSE_ID` not set | Support verified key fallback |
| **Serper API** | AUTH_REQUIRED | `SERPER_API_KEY` empty string in environment | Graceful skip when empty; validate when provided |
| **Brave Search API** | UNAVAILABLE | Env name mismatch (`BRAVE_API_KEY` vs `BRAVE_SEARCH_API_KEY`) | Normalize configuration key names |
| **DuckDuckGo** | **AVAILABLE (Active)** | HTML & Instant Answer scrapers; no API key needed | Preserve as indestructible zero-cost default |
| **Browser Google (CDP)**| AVAILABLE (Fallback) | Automated Playwright headless search | Use as verified visual fallback |
