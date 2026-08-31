# core/health_check.py
# Startup Health Check & Diagnostics for JARVIS

import os
import sys
import json
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_startup_health_check(base_dir: Path) -> Tuple[bool, List[str]]:
    """
    Performs comprehensive diagnostic checks on system components.
    Prints visual formatted 'JARVIS SYSTEM CHECK' status report.
    Returns (all_passed, summary_lines).
    """
    print("\n" + "=" * 45)
    print("        JARVIS SYSTEM CHECK")
    print("=" * 45)

    results: Dict[str, Tuple[bool, str]] = {}
    summary_lines: List[str] = []

    # 1. Python Environment Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        results["Python"] = (True, f"v{py_ver}")
    else:
        results["Python"] = (False, f"v{py_ver} (Requires Python 3.10+)")

    # 2. Dependencies Import Check
    missing_deps = []
    required_mods = [
        ("sounddevice", "sounddevice"),
        ("google-genai", "google.genai"),
        ("pillow", "PIL"),
        ("requests", "requests"),
        ("playwright", "playwright"),
        ("pyautogui", "pyautogui"),
        ("psutil", "psutil"),
    ]

    for pkg, mod in required_mods:
        try:
            __import__(mod)
        except ImportError:
            missing_deps.append(pkg)

    if not missing_deps:
        results["Dependencies"] = (True, "All required packages installed")
    else:
        results["Dependencies"] = (False, f"Missing packages: {', '.join(missing_deps)}")

    # 3. AI Provider Architecture Check
    try:
        from core.ollama_provider import is_ollama_available, get_ollama_provider
        if is_ollama_available():
            provider = get_ollama_provider()
            results["AI Provider"] = (True, "Ollama LOCAL")
            results["Persona Model"] = (True, f"{provider.persona_model}")
            results["Tool Model"] = (True, f"{provider.tool_model}")
            results["Fallback"] = (True, "Gemini (only when Ollama is unavailable)")
        else:
            api_config_path = base_dir / "config" / "api_keys.json"
            if api_config_path.exists():
                with open(api_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    key = data.get("gemini_api_key", "").strip()
                    if key and not key.startswith("YOUR_"):
                        results["AI Provider"] = (True, "Gemini API Key configured (Ollama Offline)")
                    else:
                        results["AI Provider"] = (False, "Gemini API key empty or default")
            else:
                results["AI Provider"] = (False, "api_keys.json missing")
    except Exception as e:
        results["AI Provider"] = (False, f"AI diagnostic error: {e}")

    # 4. Audio Input/Output Check
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
        has_output = any(d.get("max_output_channels", 0) > 0 for d in devices)

        if has_input and has_output:
            results["Voice Hardware"] = (True, "Microphone & Speaker detected")
        elif has_input:
            results["Voice Hardware"] = (False, "Microphone detected, Speaker missing")
        elif has_output:
            results["Voice Hardware"] = (False, "Speaker detected, Microphone missing")
        else:
            results["Voice Hardware"] = (False, "No audio input/output devices found")
    except Exception as e:
        results["Voice Hardware"] = (False, f"Audio diagnostic failed: {e}")

    # 5. Playwright Browser Check
    try:
        import playwright
        results["Browser"] = (True, "Playwright available")
    except Exception as e:
        results["Browser"] = (False, f"Playwright not ready: {e}")

    # 6. Windows System Control Check
    if platform.system() == "Windows":
        try:
            import psutil
            import pyautogui
            from core.capability_discovery import capability_registry
            cap_summary = capability_registry.get_summary()
            results["Windows Control"] = (True, f"Ready ({cap_summary})")
        except Exception as e:
            results["Windows Control"] = (False, f"Win32 API error: {e}")
    else:
        results["Windows Control"] = (True, f"Cross-platform OS: {platform.system()}")

    # 7. Memory & Storage Check
    mem_path = base_dir / "memory" / "long_term.json"
    if mem_path.exists() or mem_path.parent.exists():
        results["Memory Engine"] = (True, "Persistent memory JSON active")
    else:
        results["Memory Engine"] = (False, "Memory directory inaccessible")

    # Print Formatted Report
    all_passed = True
    for comp, (passed, msg) in results.items():
        status_symbol = "✓" if passed else "⚠"
        line = f" {status_symbol} {comp:<18} : {msg}"
        print(line)
        summary_lines.append(line)
        if not passed:
            all_passed = False

    print("=" * 45)
    print("      COMMUNICATION INTEGRATIONS (OPTIONAL)")
    print("=" * 45)
    try:
        from actions.social_providers import get_social_provider_health
        soc_health = get_social_provider_health()
        for prov_name, pdata in soc_health.items():
            st = pdata.get("status", "UNCONFIGURED")
            if st in ["MISSING", "UNCONFIGURED"]:
                st_label = "NOT CONFIGURED (OPTIONAL)"
                st_symbol = "ℹ"
            elif st in ["READY", "CONFIGURED"]:
                st_label = "READY"
                st_symbol = "✓"
            else:
                st_label = st
                st_symbol = "⚠"
            line = f" {st_symbol} {prov_name:<18} : {st_label}"
            print(line)
            summary_lines.append(line)
    except Exception as e:
        print(f" ⚠ Social Diagnostic : {e}")

    print("=" * 45)
    if all_passed:
        print(" JARVIS ONLINE — ALL SYSTEMS OPERATIONAL")
    else:
        print(" ⚠ JARVIS ONLINE WITH WARNINGS — (Some features may run degraded)")
    print("=" * 45 + "\n")

    return all_passed, summary_lines
