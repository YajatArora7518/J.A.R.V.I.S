# scripts/test_ollama_recovery.py
# Phase 3C: Ollama Outage & Automatic Resumption Test

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

from core.ai_multitier_engine import get_ai_engine
from core.runtime_supervisor import get_runtime_supervisor, SubsystemState

def run_ollama_recovery_test():
    print("=" * 65, flush=True)
    print("      PHASE 3C: OLLAMA OUTAGE & RECOVERY TEST", flush=True)
    print("=" * 65, flush=True)

    engine = get_ai_engine()
    supervisor = get_runtime_supervisor()

    # 1. Normal State: Ollama Available -> Tier 1
    print("\n[-] STEP 1: Verify Initial Tier 1 Status", flush=True)
    ollama_sub = supervisor.get_subsystem("OLLAMA")
    assert ollama_sub is not None, "Ollama subsystem not registered in supervisor!"
    print(f"  [+] Initial State: {ollama_sub.state} | Provider: {ollama_sub.current_provider}", flush=True)

    # 2. Simulated Ollama Outage: Fallback to Tier 2
    print("\n[-] STEP 2: Simulating Local Ollama Outage -> Tier 2 Fallback", flush=True)
    with patch("core.ollama_provider.is_ollama_available", return_value=False):
        t0 = time.time()
        res = engine.generate_response("Say hello in one short sentence.", prefer_cloud=False)
        dur = int((time.time() - t0) * 1000)

        assert res.get("success") is True, f"Inference failed during Ollama outage: {res}"
        assert res.get("tier") == "TIER_2_GEMINI", f"Expected TIER_2_GEMINI fallback, got {res.get('tier')}"
        print(f"  [+] Graceful fallback verified: {res.get('tier')} ({res.get('model')}) in {dur}ms", flush=True)
        print(f"  [+] Response: '{res.get('text')[:60]}...'", flush=True)

    # Check supervisor telemetry reflects degradation
    assert ollama_sub.state in (SubsystemState.DEGRADED, SubsystemState.OFFLINE), f"Ollama state not degraded: {ollama_sub.state}"
    print(f"  [+] Telemetry verified: Ollama state -> {ollama_sub.state} (Error: {ollama_sub.error_category})", flush=True)

    # 3. Simulated Ollama Recovery: Self-Healing & Automatic Tier 1 Resumption
    print("\n[-] STEP 3: Simulating Ollama Recovery & Automatic Tier 1 Resumption", flush=True)
    # Re-enable Ollama availability
    ollama_sub.next_recovery_due = time.time() - 1.0  # Elapse backoff
    healing_res = supervisor.trigger_self_healing_pass()
    print(f"  [+] Self-healing pass result: {healing_res.get('OLLAMA')}", flush=True)
    assert ollama_sub.state == SubsystemState.HEALTHY, f"Ollama state not restored to HEALTHY: {ollama_sub.state}"

    # Verify generate_response automatically uses Tier 1 again without restarting JARVIS
    mock_ollama_resp = {
        "success": True,
        "text": "Hello Boss! I am back online and operational locally.",
        "model_used": "fotiecodes/jarvis:latest"
    }
    with patch("core.ollama_provider.is_ollama_available", return_value=True), \
         patch("core.ollama_provider.generate_ollama_response", return_value=mock_ollama_resp):
        res2 = engine.generate_response("Are you back online?", prefer_cloud=False)
        assert res2.get("success") is True, f"Call failed: {res2}"
        assert res2.get("tier") == "TIER_1_OLLAMA", f"Expected TIER_1_OLLAMA resumption, got {res2.get('tier')}"
        print(f"  [+] Automatic Tier 1 resumption verified without restart: {res2.get('tier')} -> '{res2.get('text')}'", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3C OLLAMA RECOVERY TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_ollama_recovery_test()
    sys.exit(0 if success else 1)
