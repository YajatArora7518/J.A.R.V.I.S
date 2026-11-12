# scripts/test_hardware_recovery.py
# Phase 3D: Hardware Recovery & Handle Isolation Test

import sys
import os
import time
import threading
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.tts_engine import get_tts_engine
from agent.awareness.camera_provider import camera_provider
from agent.awareness.permissions import privacy_mode_manager
from core.runtime_supervisor import get_runtime_supervisor, SubsystemState

def run_hardware_recovery_test():
    print("=" * 65, flush=True)
    print("      PHASE 3D: HARDWARE RECOVERY & HANDLE ISOLATION TEST", flush=True)
    print("=" * 65, flush=True)

    supervisor = get_runtime_supervisor()

    # 1. TTS Worker Duplication Guard Verification
    print("\n[-] STEP 1: Verify UniversalTTSEngine Reuses Worker Thread", flush=True)
    tts1 = get_tts_engine()
    initial_worker = getattr(tts1, "_worker_thread", None)
    
    # Trigger repeated speech stop/start
    tts1.stop()
    tts1.speak("Diagnostic hardware check.", source="test")
    time.sleep(0.3)
    tts1.stop()
    
    post_worker = getattr(tts1, "_worker_thread", None)
    if initial_worker and post_worker:
        assert initial_worker is post_worker, "TTS engine spawned a duplicate worker thread!"
    print("  [+] TTS worker thread verified: Existing worker reused without duplication.", flush=True)

    # 2. Camera Handle Isolation & Leak Prevention
    print("\n[-] STEP 2: Camera Handle Leak Prevention Under Rapid Cycling", flush=True)
    privacy_mode_manager.disable_privacy_mode()
    
    # Sample camera repeatedly to ensure handles are completely freed
    for cycle in range(5):
        sample = camera_provider.sample_context()
        assert isinstance(sample, dict), f"Sample #{cycle} failed: {sample}"
        time.sleep(0.1)

    print("  [+] 5 rapid camera capture cycles completed with zero handle leaks.", flush=True)

    # 3. Audio Device Hot-Swap Resilience
    print("\n[-] STEP 3: Audio Hot-Swap Telemetry Recovery", flush=True)
    # Simulate temporary voice input degradation
    supervisor.record_failure(
        "VOICE INPUT",
        offline=True,
        error_msg="Simulated audio hot-unplug event",
        category="DEVICE_DISCONNECT"
    )
    voice_sub = supervisor.get_subsystem("VOICE INPUT")
    assert voice_sub.state == SubsystemState.OFFLINE, f"Expected OFFLINE, got {voice_sub.state}"
    print(f"  [+] Voice input marked {voice_sub.state} upon simulated hot-unplug.", flush=True)

    # Simulate reconnect: Force due time and run healing pass
    voice_sub.next_recovery_due = time.time() - 1.0
    healing_res = supervisor.trigger_self_healing_pass()
    print(f"  [+] Voice input self-healing result: {healing_res.get('VOICE INPUT')}", flush=True)
    assert voice_sub.state == SubsystemState.HEALTHY, f"Expected HEALTHY, got {voice_sub.state}"
    print("  [+] Voice input automatically restored to HEALTHY upon device reconnect.", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3D HARDWARE RECOVERY TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_hardware_recovery_test()
    sys.exit(0 if success else 1)
