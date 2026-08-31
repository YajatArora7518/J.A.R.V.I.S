# 🛡️ JARVIS Security & Authorization Policy

JARVIS includes a central `SecurityManager` ([security.py](file:///c:/Users/yajat/OneDrive/Desktop/JARVIS%20M/JARVIS%20MAIN/core/security.py)) that classifies operations by risk level and enforces user safety.

---

## 📊 Risk Level Classification

```
      CRITICAL  ───────►  Drive Formatting / Mass Deletion (Requires User Confirmation)
         │
       HIGH      ───────►  File Deletion / Process Killing / Project Agent Generation
         │
      MEDIUM    ───────►  App Launching / System Settings / Web Browsing
         │
        LOW      ───────►  Search / Screen Capture / Fact Memory Retrieval
```

---

## 🔒 Security Principles

1. **Localhost Binding by Default**:
   The REST API server binds strictly to `127.0.0.1`. Remote network access is disabled unless explicitly configured.

2. **Protected System Directories**:
   Operations attempting file deletion or modification within system directories (`C:\Windows`, `System32`) are blocked automatically.

3. **No Unrestricted Elevation**:
   JARVIS operates within legitimate user permissions and does not bypass UAC or security policies.
