# Security Policy & Responsible Disclosure

## Supported Versions

Security fixes and patches are released for the current production release.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

---

## 🛡️ Security Architecture & Guardrails

JARVIS AI is built around a defense-in-depth security model:
1. **Four-Tier Risk Engine**:
   - `LOW`: Safe read-only and telemetry operations (e.g., system metrics, time, search).
   - `MEDIUM`: State-modifying actions requiring standard logging (e.g., launching apps, volume adjustment).
   - `HIGH`: Impactful actions requiring confirmation (e.g., script execution, voice/video calls, service restart).
   - `CRITICAL`: Destructive actions requiring explicit confirmation (e.g., shutdown, deletion).
2. **Deterministic State Verification**: Ensures requested actions accurately match actual OS state post-execution.
3. **Local Credentials & Data Isolation**: API keys, user profiles, conversation transcripts, and memory states remain strictly local to the user's system and are never transmitted to unauthorized endpoints.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in JARVIS AI, please report it responsibly:

- **Do NOT open a public GitHub issue.**
- Submit a detailed report through **GitHub Private Vulnerability Reporting** on the repository page.
- Please include steps to reproduce, affected components, and potential impact.

We take security issues seriously and will respond promptly to investigate and patch confirmed vulnerabilities.
