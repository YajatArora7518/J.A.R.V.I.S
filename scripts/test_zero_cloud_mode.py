# scripts/test_zero_cloud_mode.py
# Authoritative Zero-Cloud-AI Verification & Offline Resilience Test Suite for JARVIS

import os
import sys
import time
import json
import logging
from typing import Dict, Any

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Ensure JARVIS_CLOUD_AI=false (the strict default)
os.environ["JARVIS_CLOUD_AI"] = "false"

import core.ai_policy as ai_policy
from core.ai_multitier_engine import get_ai_engine
from core.local_ai_provider import get_local_ai_provider
from core.command_pipeline import process_user_command

def run_zero_cloud_tests() -> Dict[str, Any]:
    print("=" * 70)
    print("JARVIS 100% LOCAL AI / ZERO-CLOUD INTEGRATION TEST SUITE")
    print("=" * 70)

    ai_policy.reset_ai_telemetry()
    initial_telem = ai_policy.get_ai_telemetry()
    print(f"Initial Telemetry: {initial_telem}")
    assert initial_telem["cloud_ai_allowed"] is False, "Cloud AI must be False by default"
    assert initial_telem["zero_cloud_verified"] is True, "zero_cloud_verified must be True"

    tests = []

    # Test 1: Direct Cloud Gate Enforcement
    print("\n[Test 1: Direct Cloud Gate Assertion]")
    gate_blocked = False
    try:
        ai_policy.assert_cloud_ai_allowed("Test Unauthorized Cloud AI Call")
    except ai_policy.CloudAIBlocked as cb:
        gate_blocked = True
        print(f"  Successfully caught CloudAIBlocked: {cb}")
    assert gate_blocked, "CloudAIBlocked was NOT raised when asserting cloud call"
    tests.append({"test": "1_CloudGateAssertion", "pass": gate_blocked})

    # Test 2: MultiTier Engine Zero Cloud Enforcement
    print("\n[Test 2: MultiTier Engine Zero Cloud Delegation]")
    engine = get_ai_engine()
    res_2a = engine.generate_response("What is your core directive, Jarvis?")
    print(f"  Tier 1 Local Result: Tier='{res_2a.get('tier')}', Success={res_2a.get('success')}")
    assert res_2a.get("tier") == "TIER_1_OLLAMA", f"Expected TIER_1_OLLAMA, got {res_2a.get('tier')}"

    # Force cloud attempt - must be blocked cleanly without crashing
    res_2b = engine.generate_response("Test force cloud escalation", prefer_cloud=True)
    print(f"  Forced Cloud Attempt Result: Tier='{res_2b.get('tier')}', Error='{res_2b.get('error')}'")
    assert res_2b.get("tier") == "LOCAL_ZERO_CLOUD_GATE", f"Expected LOCAL_ZERO_CLOUD_GATE, got {res_2b.get('tier')}"
    assert res_2b.get("error") == "CLOUD_AI_BLOCKED", f"Expected CLOUD_AI_BLOCKED, got {res_2b.get('error')}"
    tests.append({"test": "2_MultiTierZeroCloud", "pass": True})

    # Test 3: Local Command Pipeline Deterministic & Ollama Execution
    print("\n[Test 3: Local Command Pipeline Execution]")
    res_3a = process_user_command("what time is it", source="test")
    print(f"  Time Fast-Path Result: Success={res_3a.get('success')}, Verified={res_3a.get('verified')}")
    assert res_3a.get("success") is True, "Time query failed"

    res_3b = process_user_command("who created you", source="test")
    print(f"  Conversational Query Result: Success={res_3b.get('success')}, Msg='{res_3b.get('message', '')[:60]}...'")
    assert res_3b.get("success") is True, "Conversational query failed"
    tests.append({"test": "3_CommandPipelineLocal", "pass": True})

    # Test 4: Final Telemetry Audit & Strict Zero Cloud Assertion
    print("\n[Test 4: Authoritative Telemetry Audit]")
    final_telem = ai_policy.get_ai_telemetry()
    print(f"Final Telemetry: {json.dumps(final_telem, indent=2)}")

    assert final_telem["gemini_calls"] == 0, f"VIOLATION: gemini_calls={final_telem['gemini_calls']} (MUST BE 0)"
    assert final_telem["cloud_attempts"] > 0, "cloud_attempts should reflect blocked attempts"
    assert final_telem["cloud_blocked"] == final_telem["cloud_attempts"], "All cloud attempts MUST be blocked"
    assert final_telem["local_ai_calls"] > 0, f"VIOLATION: local_ai_calls={final_telem['local_ai_calls']} (MUST BE > 0)"
    assert final_telem["zero_cloud_verified"] is True, "zero_cloud_verified must be True"

    print("\n" + "=" * 70)
    print("ALL ZERO-CLOUD CONSTRAINTS EMPIRICALLY VERIFIED:")
    print(f"  GEMINI_CALLS:     {final_telem['gemini_calls']} (PASSED: STRICTLY 0)")
    print(f"  CLOUD_BLOCKED:    {final_telem['cloud_blocked']}/{final_telem['cloud_attempts']} (PASSED: 100% BLOCKED)")
    print(f"  LOCAL_AI_CALLS:   {final_telem['local_ai_calls']} (PASSED: > 0)")
    print(f"  RUNTIME MODE:     100% LOCAL AI / ZERO-CLOUD-AI")
    print("=" * 70)

    summary = {
        "tests": tests,
        "telemetry": final_telem,
        "all_passed": all(t["pass"] for t in tests)
    }

    scratch_dir = os.path.join(os.path.dirname(__file__), "..", "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    with open(os.path.join(scratch_dir, "zero_cloud_test_results.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary

if __name__ == "__main__":
    run_zero_cloud_tests()
