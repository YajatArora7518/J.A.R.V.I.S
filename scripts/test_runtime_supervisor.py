# scripts/test_runtime_supervisor.py
# Phase 3B: Runtime Supervisor & Self-Healing Lifecycle Test

import sys
import os
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.runtime_supervisor import (
    get_runtime_supervisor,
    RuntimeSupervisor,
    SubsystemState,
    MIN_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    BACKOFF_MULTIPLIER,
    redact_secrets
)

def run_supervisor_tests():
    print("=" * 65, flush=True)
    print("      PHASE 3B: RUNTIME SUPERVISOR & SELF-HEALING TEST", flush=True)
    print("=" * 65, flush=True)

    # 1. Singleton Lifecycle Guard
    print("\n[-] STEP 1: Singleton Lifecycle Guard Verification", flush=True)
    sup1 = get_runtime_supervisor()
    sup2 = get_runtime_supervisor()
    sup3 = RuntimeSupervisor()
    assert sup1 is sup2, "get_runtime_supervisor() did not return singleton instance!"
    assert sup1 is sup3, "RuntimeSupervisor() constructor did not return singleton instance!"
    print("  [+] Singleton verified: All instances share identical memory address.", flush=True)

    # Prevent duplicate background threads
    sup1.start_background_monitor(interval_sec=30.0)
    worker1 = sup1._monitor_thread
    sup1.start_background_monitor(interval_sec=30.0)
    worker2 = sup1._monitor_thread
    assert worker1 is worker2, "Duplicate monitor worker created on second start call!"
    print("  [+] Lifecycle protection: Duplicate background worker creation prevented.", flush=True)
    sup1.stop_background_monitor()

    # 2. Secret Redaction in Telemetry
    print("\n[-] STEP 2: Secret Redaction in Stored Subsystem Telemetry", flush=True)
    fake_secret = "Failed auth: api_key=AIzaSySecretApiKey1234567890 token=sk-abcdefghijklmnopqrstuvwxyz"
    sup1.record_failure("OLLAMA", offline=True, error_msg=fake_secret, category="AUTH_FAILURE")
    sub = sup1.get_subsystem("OLLAMA")
    assert sub is not None, "Subsystem OLLAMA not found!"
    assert "AIzaSySecretApiKey1234567890" not in (sub.last_error or ""), "Secret leaked into last_error!"
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in (sub.last_error or ""), "Secret leaked into last_error!"
    assert "[REDACTED" in (sub.last_error or ""), "Redaction tag missing from stored error!"
    print(f"  [+] Error stored safely with redaction: '{sub.last_error}'", flush=True)

    # 3. Bounded Exponential Backoff Verification
    print("\n[-] STEP 3: Bounded Exponential Backoff Verification", flush=True)
    assert sub.state == SubsystemState.OFFLINE, f"Expected OFFLINE, got {sub.state}"
    assert sub.current_backoff == 10.0, f"Expected backoff 10.0s after first failure, got {sub.current_backoff}"

    # Multiple successive failures to verify bounding at MAX_BACKOFF_SECONDS (60s)
    for _ in range(6):
        sup1.record_failure("OLLAMA", offline=True, error_msg="Server still down", category="TIMEOUT")

    assert sub.current_backoff <= MAX_BACKOFF_SECONDS, f"Backoff exceeded MAX ({MAX_BACKOFF_SECONDS}s): {sub.current_backoff}"
    print(f"  [+] Bounded backoff verified: Clamped at {sub.current_backoff}s (Max: {MAX_BACKOFF_SECONDS}s)", flush=True)

    # 4. Self-Healing Recovery Pass Verification
    print("\n[-] STEP 4: Self-Healing Recovery Pass Verification", flush=True)
    # Register a controlled probe that simulates successful recovery
    probe_called = [False]
    def mock_healthy_probe() -> bool:
        probe_called[0] = True
        return True

    sup1.register_recovery_hook("OLLAMA", mock_healthy_probe)
    # Force next_recovery_due to the past to simulate elapsed backoff
    sub.next_recovery_due = time.time() - 1.0

    healing_results = sup1.trigger_self_healing_pass()
    assert probe_called[0] is True, "Recovery hook was not triggered during self-healing pass!"
    assert healing_results.get("OLLAMA") == "RECOVERED", f"Unexpected result: {healing_results}"
    assert sub.state == SubsystemState.HEALTHY, f"Subsystem state not restored to HEALTHY! Current: {sub.state}"
    assert sub.current_backoff == MIN_BACKOFF_SECONDS, f"Backoff not reset to MIN: {sub.current_backoff}"
    assert sub.error_category is None, "error_category not cleared after recovery!"
    print(f"  [+] Self-healing verified: State -> {sub.state}, Backoff reset -> {sub.current_backoff}s", flush=True)

    # 5. Full Observability Telemetry Dump
    print("\n[-] STEP 5: Observability Telemetry Completeness", flush=True)
    report = sup1.get_full_report()
    assert "timestamp" in report, "Missing timestamp in report"
    assert "subsystems" in report, "Missing subsystems in report"
    all_subs = report["subsystems"]
    assert len(all_subs) >= 8, f"Expected at least 8 subsystems, found {len(all_subs)}"

    print(f"{'SUBSYSTEM':<18} | {'STATE':<10} | {'ATTEMPTS':<9} | {'PROVIDER'}")
    print("-" * 65)
    for name, data in all_subs.items():
        print(f"{name:<18} | {data['state']:<10} | {data['recovery_attempts']:<9} | {data['current_provider']}")

    # Restore real probe hook for OLLAMA
    sup1._register_default_hooks()

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3B RUNTIME SUPERVISOR TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_supervisor_tests()
    sys.exit(0 if success else 1)
