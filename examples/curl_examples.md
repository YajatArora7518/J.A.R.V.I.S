# cURL Examples for JARVIS REST API

### 1. Public Health Check
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 2. Get System Diagnostics & Status
```bash
curl -X GET http://127.0.0.1:8000/api/v1/status \
  -H "X-JARVIS-API-KEY: default-jarvis-key"
```

### 3. List Registered Tools
```bash
curl -X GET http://127.0.0.1:8000/api/v1/tools \
  -H "X-JARVIS-API-KEY: default-jarvis-key"
```

### 4. Execute Natural Language Command
```bash
curl -X POST http://127.0.0.1:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -H "X-JARVIS-API-KEY: default-jarvis-key" \
  -d "{\"command\": \"Open Chrome\"}"
```

### 5. Call Tool Directly
```bash
curl -X POST http://127.0.0.1:8000/api/v1/tool \
  -H "Content-Type: application/json" \
  -H "X-JARVIS-API-KEY: default-jarvis-key" \
  -d "{\"tool\": \"computer_settings\", \"arguments\": {\"action\": \"volume_set\", \"value\": 50}}"
```

### 6. Store Memory Fact
```bash
curl -X POST http://127.0.0.1:8000/api/v1/memory \
  -H "Content-Type: application/json" \
  -H "X-JARVIS-API-KEY: default-jarvis-key" \
  -d "{\"key\": \"favorite_editor\", \"value\": \"VS Code\", \"category\": \"preferences\"}"
```
