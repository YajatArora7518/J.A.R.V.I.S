# 🌐 JARVIS REST API Reference

The JARVIS REST API exposes HTTP JSON endpoints on version `/api/v1`.

---

## 🔒 Authentication
All endpoints except `/health` require the `X-JARVIS-API-KEY` header.

```http
X-JARVIS-API-KEY: default-jarvis-key
```

---

## 📋 Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|:---:|
| `GET` | `/api/v1/health` | Health check endpoint | No |
| `GET` | `/api/v1/status` | System health & diagnostic status | Yes |
| `GET` | `/api/v1/tools` | List registered tools and schemas | Yes |
| `POST` | `/api/v1/execute` | Execute natural language command | Yes |
| `POST` | `/api/v1/tool` | Call registered tool directly | Yes |
| `POST` | `/api/v1/task` | Submit autonomous background task | Yes |
| `GET` | `/api/v1/memory` | Retrieve long-term memory facts | Yes |
| `POST` | `/api/v1/memory` | Store long-term memory fact | Yes |
| `DELETE` | `/api/v1/memory/{key}` | Delete long-term memory fact | Yes |

---

## 🧪 Sample Request (`POST /api/v1/execute`)

```http
POST /api/v1/execute HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
X-JARVIS-API-KEY: default-jarvis-key

{
  "command": "Open Chrome"
}
```

### Response (200 OK)
```json
{
  "success": true,
  "tool": "open_app",
  "message": "Opened Chrome successfully, sir.",
  "data": {},
  "verification": {
    "verified": true,
    "type": "process",
    "pid": 14220,
    "name": "chrome.exe"
  },
  "error": null,
  "execution_time_ms": 420.15
}
```
