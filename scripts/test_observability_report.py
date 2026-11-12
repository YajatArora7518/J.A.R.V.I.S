# scripts/test_observability_report.py
# Phase 2 Observability & Deep Runtime Signal Diagnostic Test

import sys
import os
import json
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

import threading
import queue

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.health_check import get_subsystem_observability_report, _redact_secrets

def run_observability_test():
    print("=" * 65, flush=True)
    print("      PHASE 2 & 3: DEEP SUBSYSTEM OBSERVABILITY TEST", flush=True)
    print("=" * 65, flush=True)

    # 1. Test secret redaction explicitly with representative fake secrets
    print("\n[-] STEP 1: Secret Redaction Verification", flush=True)
    fake_secrets = [
        ("api_key=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q", "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q"),
        ("sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"),
        ("AQ.ab12cd34ef56gh78ij90kl12mn34op56qr78st", "AQ.ab12cd34ef56gh78ij90kl12mn34op56qr78st"),
        ("Authorization: Bearer my_secret_bearer_token_1234567890", "my_secret_bearer_token_1234567890"),
        ("user_password=SuperSecretPassword456!", "SuperSecretPassword456!"),
        ("auth_token: my_jwt_token_payload_xyz987", "my_jwt_token_payload_xyz987"),
        ("client_secret = oauth_secret_hex_payload_45678", "oauth_secret_hex_payload_45678")
    ]

    for secret_input, secret_raw_val in fake_secrets:
        redacted = _redact_secrets(secret_input)
        assert secret_raw_val not in redacted, f"Raw secret leaked in '{redacted}'!"
        assert "[REDACTED" in redacted, f"Redaction tag missing in '{redacted}'!"
        print(f"  [+] Redacted: '{secret_input[:30]}...' -> '{redacted}'", flush=True)

    print("[+] All fake secrets successfully redacted.", flush=True)

    # 2. Run real runtime signal diagnostic for all 8 subsystems with watchdog
    print("\n[-] STEP 2: Querying Real Subsystem Runtime Signals (Bounded Watchdog: 20s)", flush=True)
    t0 = time.time()

    result_queue = queue.Queue()

    def _worker():
        try:
            rep = get_subsystem_observability_report(REPO_DIR)
            result_queue.put(("OK", rep))
        except Exception as ex:
            result_queue.put(("ERROR", ex))

    worker_thread = threading.Thread(target=_worker, daemon=True, name="ObservabilityReport_WatchdogWorker")
    worker_thread.start()

    try:
        status, report = result_queue.get(timeout=20.0)
        if status == "ERROR":
            raise RuntimeError(f"Observability worker failed: {report}")
    except queue.Empty:
        raise TimeoutError("CRITICAL: get_subsystem_observability_report exceeded 20s watchdog limit!")

    duration_ms = int((time.time() - t0) * 1000)
    print(f"[+] Observability report generated safely in {duration_ms}ms", flush=True)

    subsystems = report.get("subsystems", {})
    required_subsystems = [
        "OLLAMA",
        "VOICE INPUT",
        "VOICE OUTPUT",
        "CAMERA",
        "SCREEN ANALYSIS",
        "MEMORY",
        "AUTOMATION",
        "REMINDERS"
    ]

    valid_states = {"HEALTHY", "DEGRADED", "RECOVERING", "OFFLINE"}

    print("\n" + "-" * 65, flush=True)
    print(f"{'SUBSYSTEM':<18} | {'STATUS':<10} | {'LATENCY':<8} | {'DETAILS'}", flush=True)
    print("-" * 65, flush=True)

    for sub in required_subsystems:
        assert sub in subsystems, f"Missing required subsystem: {sub}"
        info = subsystems[sub]
        status = info.get("status")
        lat = f"{info.get('latency_ms', -1)}ms"
        details = info.get("details", "")

        assert status in valid_states, f"Invalid health state '{status}' for {sub}"

        # Ensure no accidental secrets or keys leaked in details
        redacted_details = _redact_secrets(details)
        assert details == redacted_details, f"Unredacted sensitive string in {sub} details!"

        # Ensure supervisor fields are attached
        assert "recovery_attempts" in info, f"Missing recovery_attempts in {sub}"
        assert "current_provider" in info, f"Missing current_provider in {sub}"

        print(f"{sub:<18} | {status:<10} | {lat:<8} | {details}", flush=True)

        if status not in ("HEALTHY", "DEGRADED"):
            print(f"  [i] Subsystem {sub} reported non-healthy state: {status}", flush=True)

    # Subsystem specific assertions on real signals
    print("\n[-] STEP 3: Verifying Specific Runtime Signal Distinctions", flush=True)

    # Camera: device availability distinguishable from active awareness state
    cam_info = subsystems["CAMERA"]
    assert "hardware_available" in cam_info, "Camera missing hardware_available signal"
    assert "awareness_active" in cam_info, "Camera missing awareness_active signal"
    assert "privacy_mode" in cam_info, "Camera missing privacy_mode signal"
    print(f"  [+] Camera Signals -> HW: {cam_info['hardware_available']}, Active: {cam_info['awareness_active']}, Privacy: {cam_info['privacy_mode']}", flush=True)

    # Screen Analysis: resolution and latency
    screen_info = subsystems["SCREEN ANALYSIS"]
    assert "resolution" in screen_info, "Screen Analysis missing resolution signal"
    print(f"  [+] Screen Pipeline -> Resolution: {screen_info['resolution']}, Latency: {screen_info['latency_ms']}ms", flush=True)

    # Memory: active categories
    mem_info = subsystems["MEMORY"]
    assert "categories" in mem_info and len(mem_info["categories"]) > 0, "Memory missing categories"
    print(f"  [+] Memory Engine -> Categories: {mem_info['categories']}", flush=True)

    # Automation: tool count
    auto_info = subsystems["AUTOMATION"]
    assert auto_info.get("tool_count", 0) >= 60, f"Expected >= 60 tools, got {auto_info.get('tool_count')}"
    print(f"  [+] Automation Tools -> Count: {auto_info['tool_count']}", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 2 & 3 OBSERVABILITY TEST: PASSED (All 8 subsystems monitored)", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_observability_test()
    sys.exit(0 if success else 1)
