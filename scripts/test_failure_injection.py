# scripts/test_failure_injection.py
# Phase 2 Comprehensive Failure Injection & Graceful Recovery Verification

import sys
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.ai_multitier_engine import get_ai_engine
from core.command_pipeline import process_user_command
from actions.open_app import open_app_structured
from agent.awareness.camera_provider import camera_provider
from core.health_check import get_subsystem_observability_report

def run_failure_injection_tests():
    print("=" * 65)
    print("      PHASE 2: REAL FAILURE INJECTION & RECOVERY SUITE")
    print("=" * 65)

    all_passed = True
    ai_engine = get_ai_engine()

    # -------------------------------------------------------------
    # 1. Failure Injection: OLLAMA UNAVAILABLE
    # -------------------------------------------------------------
    print("\n[-] TEST 1: Ollama Unavailable -> Tier 2 Gemini Recovery")
    with patch("core.ollama_provider.is_ollama_available", return_value=False):
        # 1. Trigger failure & confirm detection
        t0 = time.time()
        res = ai_engine.generate_response("Test prompt during Ollama outage", prefer_cloud=False)
        latency = int((time.time() - t0) * 1000)
        
        # 2. Confirm fallback to Tier 2 Gemini
        assert res.get("success"), "AI failed to recover from Ollama outage"
        assert res.get("tier") == "TIER_2_GEMINI", f"Expected fallback to TIER_2_GEMINI, got {res.get('tier')}"
        print(f"  [+] Detected Ollama outage. Gracefully switched to Tier 2 ({res.get('model')}) in {latency}ms.")

        # 3. Confirm unaffected subsystems continue working (e.g. calculator tool)
        pipe_res = process_user_command("calculate 15 + 30", source="chat")
        assert "45" in pipe_res.get("message", ""), "Unaffected tool failed during Ollama outage!"
        print(f"  [+] Unaffected subsystem verified: Command pipeline & tools remain operational.")

    # -------------------------------------------------------------
    # 2. Failure Injection: GEMINI UNAVAILABLE (503 Service Unavailable)
    # -------------------------------------------------------------
    print("\n[-] TEST 2: Gemini Cloud Unavailable -> Tier 3 OpenRouter / Fallback")
    with patch("google.genai.Client", side_effect=Exception("503 Service Unavailable")):
        res_cloud_fail = ai_engine.generate_response("Important status check", prefer_cloud=True)
        # Should attempt Tier 3 or return graceful offline response without crash
        assert "text" in res_cloud_fail, "Missing text in fallback response during Gemini outage"
        print(f"  [+] Gemini 503 detected. Handled safely: Tier={res_cloud_fail.get('tier')}, text='{res_cloud_fail.get('text')[:40]}...'")

    # -------------------------------------------------------------
    # 3. Failure Injection: NETWORK UNAVAILABLE (WAN Disconnection)
    # -------------------------------------------------------------
    print("\n[-] TEST 3: Full Network Disconnection -> Local Fallback")
    import socket
    orig_create_conn = socket.create_connection
    def mock_wan_offline(address, *args, **kwargs):
        host = address[0]
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_create_conn(address, *args, **kwargs)
        raise OSError("Network is unreachable (WAN offline)")

    with patch("socket.create_connection", side_effect=mock_wan_offline):
        # Querying local commands must still succeed 100%
        local_res = process_user_command("calculate 99 * 5", source="chat")
        assert local_res.get("success"), f"Local command failed during WAN network outage: {local_res}"
        print(f"  [+] Network outage simulated. Local operations unaffected: '{local_res.get('message')}'")

    # -------------------------------------------------------------
    # 4. Failure Injection: CAMERA BUSY / HARDWARE LOCKED
    # -------------------------------------------------------------
    print("\n[-] TEST 4: Camera Busy / Hardware Locked -> Graceful Status")
    with patch("cv2.VideoCapture") as mock_cap_cls:
        # Mock camera unable to open (e.g. another app is using it)
        mock_cap_instance = MagicMock()
        mock_cap_instance.isOpened.return_value = False
        mock_cap_cls.return_value = mock_cap_instance

        cam_res = camera_provider.sample_context()
        # Must detect that camera could not read hardware and return safe dict without crashing
        assert "presence_detected" in cam_res, "Camera failed to return standard schema on busy error"
        print(f"  [+] Camera locked condition handled cleanly: Available={cam_res.get('available')}, Status={cam_res.get('status')}")

    # -------------------------------------------------------------
    # 5. Failure Injection: INVALID / EMPTY AI RESPONSE
    # -------------------------------------------------------------
    print("\n[-] TEST 5: Invalid AI Response (None / Empty String) -> Polite Fallback")
    with patch("core.ollama_provider.generate_ollama_response", return_value={"success": True, "text": ""}):
        with patch("google.genai.Client") as mock_gclient:
            mock_inst = MagicMock()
            mock_inst.models.generate_content.return_value = MagicMock(text="")
            mock_gclient.return_value = mock_inst
            invalid_ai_res = ai_engine.generate_response("Hello")
            # Pipeline or engine must provide a guaranteed fallback string
            reply_text = invalid_ai_res.get("text", "").strip()
            assert len(reply_text) > 0, "Returned empty response on invalid AI output"
            print(f"  [+] Empty AI output caught and handled with fallback: '{reply_text}'")

    # -------------------------------------------------------------
    # 6. Failure Injection: AI TIMEOUT
    # -------------------------------------------------------------
    print("\n[-] TEST 6: AI Inference Timeout -> Timeout Fallback")
    with patch("core.ollama_provider.generate_ollama_response", side_effect=TimeoutError("Ollama inference timed out after 30s")):
        t_res = ai_engine.generate_response("Complex query")
        assert t_res.get("text"), "Missing response on timeout"
        print(f"  [+] Timeout caught cleanly: Fallback text provided via Tier 2.")

    # -------------------------------------------------------------
    # 7. Failure Injection: NON-EXISTENT APPLICATION LAUNCH
    # -------------------------------------------------------------
    print("\n[-] TEST 7: Application Launch Failure (Non-existent App)")
    fake_app = "FakeNonExistentApplication12345"
    app_res = open_app_structured(fake_app)
    # Must report honest failure without crashing or hanging
    assert app_res.get("success") is False, "Non-existent app claimed success!"
    assert "couldn't find" in app_res.get("message", "").lower() or "not found" in app_res.get("message", "").lower(), \
        f"Unexpected failure message: {app_res.get('message')}"
    print(f"  [+] Launch failure handled honestly: '{app_res.get('message')}'")

    # -------------------------------------------------------------
    # 8. Failure Injection: VOICE SUBSYSTEM DEGRADATION
    # -------------------------------------------------------------
    print("\n[-] TEST 8: Voice Subsystem Audio Device Missing")
    with patch("sounddevice.query_devices", return_value=[]):
        rep = get_subsystem_observability_report(REPO_DIR)
        voice_st = rep["subsystems"]["VOICE INPUT"]["status"]
        assert voice_st in ("OFFLINE", "DEGRADED"), f"Expected OFFLINE/DEGRADED for missing audio, got {voice_st}"
        print(f"  [+] Missing audio hardware detected and reported honestly: {voice_st}")

    print("\n" + "=" * 65)
    print("PHASE 2 FAILURE INJECTION SUITE: ALL 8 TESTS PASSED")
    print("=" * 65)
    return True

if __name__ == "__main__":
    success = run_failure_injection_tests()
    sys.exit(0 if success else 1)
