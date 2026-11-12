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

## Operational Security Requirements

- **Fail-closed confirmation**: HIGH and CRITICAL tools are denied unless an explicit confirmation callback is configured. A missing callback is not treated as approval.
- **REST API authentication**: Set `JARVIS_API_KEY` before using protected API routes. There is no built-in default key. Send it in the `X-JARVIS-API-KEY` header.
- **Filesystem boundaries**: File operations are limited by default to Desktop, Downloads, Documents, Pictures, Music, Videos, and the JARVIS project directory. Set `JARVIS_ALLOWED_PATHS` to a platform-separated list of additional trusted directories when needed.
- **Canonical path checks**: Paths are resolved before access, which blocks traversal and symlink escapes outside the configured roots.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability in JARVIS AI, please report it responsibly:

- **Do NOT open a public GitHub issue.**
- Submit a detailed report through **GitHub Private Vulnerability Reporting** on the repository page.
- Please include steps to reproduce, affected components, and potential impact.

We take security issues seriously and will respond promptly to investigate and patch confirmed vulnerabilities.
