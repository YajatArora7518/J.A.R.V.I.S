# 🏛️ JARVIS System Architecture

JARVIS is built around a single, unified execution pipeline that serves the Desktop GUI, Python SDK, and REST API.

```
       Desktop UI            Python SDK           REST API
      (PySide6 HUD)         (JarvisAPI)          (FastAPI)
           │                     │                   │
           └─────────────────────┼───────────────────┘
                                 │
                                 ▼
                     Unified Execution Pipeline
                                 │
                       ┌─────────┴─────────┐
                       │   Tool Registry   │
                       │(Schema & Timeout) │
                       └─────────┬─────────┘
                                 │
                                 ▼
                       ┌───────────────────┐
                       │ Security Manager  │
                       │(LOW/MED/HIGH/CRIT)│
                       └─────────┬─────────┘
                                 │
                                 ▼
                       ┌───────────────────┐
                       │  Action Execution │
                       │ (Win32/Playwright)│
                       └─────────┬─────────┘
                                 │
                                 ▼
                       ┌───────────────────┐
                       │Verification Engine│
                       │ (Process/File/Vol)│
                       └───────────────────┘
```
