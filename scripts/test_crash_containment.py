# scripts/test_crash_containment.py
# Phase 3 Crash Containment Verification Suite
# Verifies that failures in Camera, TTS, Cloud, Screen, or Supervisor do NOT crash JARVIS or block commands.

import sys
import os
import time
from pathlib import Path
from unittest.mock import patch

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.command_pipeline import process_user_command
from core.runtime_supervisor import get_runtime_supervisor, SubsystemState
from agent.awareness.camera_provider import camera_provider
from actions.screen_processor import analyze_screen_vision
from core.tts_engine import get_tts_engine

def run_crash_containment_tests():
    print("=" * 65, flush=True)
    print("      PHASE 3: CRASH & EXCEPTION CONTAINMENT TEST", flush=True)
    print("=" * 65, flush=True)

    supervisor = get_runtime_supervisor()

    # 1. Camera Hardware Exception -> Contained
    print("\n[-] TEST 1: Camera Hardware Crash -> Contained Locally", flush=True)
    with patch("cv2.VideoCapture", side_effect=RuntimeError("DirectShow driver kernel fault (simulated)")):
        cam_res = camera_provider.sample_context()
        assert isinstance(cam_res, dict), "Camera sample did not return dict upon driver error!"
        assert "presence_detected" in cam_res, "Camera failed to return standard schema!"
        print(f"  [+] Camera driver fault contained successfully: available={cam_res.get('available')}, error='{cam_res.get('error', '')[:40]}'", flush=True)

    # 2. TTS Hardware / SAPI Failure -> Contained, Does Not Kill Command Processing
    print("\n[-] TEST 2: TTS Engine Failure -> Command Processing Unaffected", flush=True)
    tts = get_tts_engine()
    with patch.object(tts, "speak", side_effect=RuntimeError("Audio endpoint disconnected (simulated)")):
        # Command pipeline should execute command and return result without crashing
        res = process_user_command("calculate 12 * 12", source="chat")
        assert res.get("success") is True, f"Command failed due to TTS exception: {res}"
        assert "144" in res.get("message", ""), "Command computation lost!"
        print(f"  [+] TTS failure contained: Command completed successfully with result: '{res.get('message')}'", flush=True)

    # 3. Cloud Provider Outage -> Local Tools Unaffected
    print("\n[-] TEST 3: Cloud Provider Failure -> Local Tools Unaffected", flush=True)
    with patch("google.genai.Client", side_effect=ConnectionError("Cloud endpoint down (simulated)")):
        res_calc = process_user_command("calculate 500 / 5", source="chat")
        assert res_calc.get("success") is True, f"Local tool failed during cloud outage: {res_calc}"
        assert "100" in res_calc.get("message", "")
        print(f"  [+] Cloud failure contained: Local tool computed correctly: '{res_calc.get('message')}'", flush=True)

    # 4. Screen Grab Exception -> Degrades Gracefully
    print("\n[-] TEST 4: Screen Grab Failure -> Degrades Gracefully", flush=True)
    with patch("actions.screen_processor._capture_screenshot", return_value=b""), \
         patch("actions.screen_processor._capture_camera", return_value=b""):
        s_res = analyze_screen_vision("Observe screen")
        assert isinstance(s_res, dict), "Screen analysis failed to return dict upon grab error!"
        # Bounded failure schema returned
        assert "message" in s_res or "error" in s_res
        print(f"  [+] Screen grab failure contained: message='{s_res.get('message')}'", flush=True)

    # 5. Supervisor Probe Exception -> Contained Locally Without Recursive Crash
    print("\n[-] TEST 5: Supervisor Recovery Hook Crash -> Contained Locally", flush=True)
    def buggy_hook():
        raise ZeroDivisionError("Simulated bug in recovery probe")

    supervisor.register_recovery_hook("MEMORY", buggy_hook)
    mem_sub = supervisor.get_subsystem("MEMORY")
    mem_sub.state = SubsystemState.DEGRADED
    mem_sub.next_recovery_due = time.time() - 1.0

    # Self-healing pass must NOT raise ZeroDivisionError
    try:
        results = supervisor.trigger_self_healing_pass()
        assert "Simulated bug" in str(results.get("MEMORY", "")), f"Expected error string in results: {results}"
        assert mem_sub.state == SubsystemState.DEGRADED, "Subsystem state unexpected!"
        print(f"  [+] Supervisor contained probe exception safely: '{results.get('MEMORY')}'", flush=True)
    finally:
        # Restore real hooks
        supervisor._register_default_hooks()
        mem_sub.mark_success()

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3 CRASH CONTAINMENT TEST: PASSED (All 5 domains verified)", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_crash_containment_tests()
    sys.exit(0 if success else 1)
