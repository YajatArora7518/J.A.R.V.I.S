# ⚡ JARVIS Production Quickstart

Get started with the **JARVIS Assistant**, **Python SDK**, **REST API**, and **CLI Commands**.

---

## 1. Installation

```bash
# Clone repository
git clone https://github.com/YajatArora7518/JARVIS.git
cd JARVIS

# Install package in editable mode with CLI binaries
python -m pip install -e . --no-build-isolation

# Run environment setup & health check
python setup.py
```

---

## 2. CLI Command Usage

```bash
# 1. Check version
jarvis --version

# 2. View CLI help
jarvis --help

# 3. Check System Health
jarvis status

# 4. List Registered Tools & Risk Levels
jarvis tools

# 5. Execute Command
jarvis execute "Open Notepad"

# 6. Submit Autonomous Task
jarvis task "Organize college files"
```

---

## 3. Python SDK Usage

```python
from jarvis_api import JarvisAPI

# Initialize SDK
jarvis = JarvisAPI()

# Status & Health
print(jarvis.get_status())

# Execute Command
jarvis.execute("Open Notepad")

# Direct Tool Call
jarvis.call_tool("computer_settings", {"action": "volume_set", "value": 50})

# Long-Term Memory
jarvis.remember("theme", "dark", category="preferences")
print(jarvis.get_memory("preferences", "theme"))

# Screen Vision
jarvis.analyze_screen("What is visible on screen?")
```

---

## 4. REST API Server Usage

Start REST API server:
```bash
jarvis-api
```

Test endpoints:
```bash
# Health Check (Public)
curl http://127.0.0.1:8000/api/v1/health

# System Diagnostics (Protected)
curl -X GET http://127.0.0.1:8000/api/v1/status \
  -H "X-JARVIS-API-KEY: default-jarvis-key"

# OpenAPI Documentation
# Visit: http://127.0.0.1:8000/docs
```

---

## 5. Master Verification Suite

Run full system verification test runner:
```bash
jarvis-test
```
