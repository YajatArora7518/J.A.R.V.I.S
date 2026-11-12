# scripts/test_sleep_wake_recovery.py
# Phase 3D: Sleep/Wake & Hardware Hot-Swap Recovery Test

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

from core.sleep_wake_monitor import get_sleep_wake_monitor, SleepWakeMonitor
from agent.awareness.permissions import privacy_mode_manager
from core.runtime_supervisor import get_runtime_supervisor

def run_sleep_wake_recovery_test():
    print("=" * 65, flush=True)
    print("      PHASE 3D: SLEEP/WAKE RECOVERY TEST", flush=True)
    print("=" * 65, flush=True)

    monitor1 = get_sleep_wake_monitor()
    monitor2 = SleepWakeMonitor()
    assert monitor1 is monitor2, "SleepWakeMonitor is not a singleton!"
    print("  [+] Singleton verified: Instances share identical identity.", flush=True)

    # 1. Duplicate Worker Thread Protection
    print("\n[-] STEP 1: Verify Duplicate Thread Protection", flush=True)
    monitor1.start_monitoring()
    t1 = monitor1._monitor_thread
    monitor1.start_monitoring()
    t2 = monitor1._monitor_thread
    assert t1 is t2, "Duplicate monitor thread spawned on redundant start() call!"
    print("  [+] Lifecycle protection verified: Redundant start() prevented duplicate worker.", flush=True)
    monitor1.stop_monitoring()

    # 2. Callback Registration & Trigger
    print("\n[-] STEP 2: Verify Wake Callback Execution", flush=True)
    callback_executed = [False]
    def on_wake(drift_sec):
        callback_executed[0] = True

    monitor1.register_wake_callback(on_wake)

    # 3. Privacy Mode Preservation Across Wake Event
    print("\n[-] STEP 3: Verify Privacy Mode Strict Preservation Across Wake", flush=True)
    privacy_mode_manager.enable_privacy_mode()
    assert privacy_mode_manager.is_privacy_mode_active() is True, "Failed to enable privacy mode!"

    rep = monitor1.trigger_wake_recovery(elapsed_sleep_sec=45.0)
    assert callback_executed[0] is True, "Registered wake callback was not executed!"

    # Verify camera was not touched
    cam_report = next((s for s in rep.get("subsystems_probed", []) if s.get("name") == "CAMERA"), None)
    assert cam_report is not None, "Missing CAMERA in probe report!"
    assert cam_report.get("status") == "PRESERVED_PRIVACY", f"Camera probe violated privacy mode: {cam_report}"
    assert privacy_mode_manager.is_privacy_mode_active() is True, "Privacy mode was disabled by wake recovery!"
    print("  [+] Privacy Mode strictly preserved: Camera hardware was not opened during wake.", flush=True)

    # 4. Wake Recovery with Privacy Mode Disabled (Normal Standby)
    print("\n[-] STEP 4: Verify Wake Recovery Normal Standby Pass", flush=True)
    privacy_mode_manager.disable_privacy_mode()
    assert privacy_mode_manager.is_privacy_mode_active() is False

    rep2 = monitor1.trigger_wake_recovery(elapsed_sleep_sec=15.0)
    cam_report2 = next((s for s in rep2.get("subsystems_probed", []) if s.get("name") == "CAMERA"), None)
    assert cam_report2 is not None, "Missing CAMERA in second probe report!"
    assert cam_report2.get("status") in ("RECOVERED", "OFFLINE"), f"Unexpected status: {cam_report2}"
    print(f"  [+] Normal wake recovery pass verified: Camera status -> {cam_report2.get('status')}", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3D SLEEP/WAKE RECOVERY TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_sleep_wake_recovery_test()
    sys.exit(0 if success else 1)
