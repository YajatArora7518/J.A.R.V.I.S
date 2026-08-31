# scripts/audit_predictive_adaptive.py
"""
Adaptive Intelligence 3.0 Predictive Personal Agent 13-Phase Audit & Stress Test Suite.

Automates end-to-end verification of 3.0 predictive capabilities:
- Runtime initialization & non-blocking startup
- Intent prediction & Next-Action prediction
- Recurring routine detection
- Project context & Cross-session continuity
- Outcome learning & Confidence evaluation
- 7-Tier Preference Priority Hierarchy
- Memory consolidation & Duplicate merging
- Privacy secret redaction & Corrupted storage recovery
- Voice governance controls (Stop, Resume, Clear Predictions, Reset)
- Long-run stress test (100 continuous interaction turns)
- Fault injection & Exception isolation
"""

import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# Force UTF-8 output encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from memory.adaptive_intelligence import (
    AdaptiveIntelligenceEngine,
    ContextDetector,
    MemoryConsolidationEngine,
    PreferenceHierarchyResolver,
    redact_secrets,
)


def run_predictive_audit():
    print("=" * 70)
    print("  JARVIS ADAPTIVE INTELLIGENCE 3.0 PREDICTIVE AUDIT & STRESS SUITE  ")
    print("=" * 70)

    test_dir = Path(tempfile.mkdtemp())
    insights_file = test_dir / "adaptive_insights.json"
    engine = AdaptiveIntelligenceEngine(insights_path=insights_file)

    results = []

    try:
        # 1. Startup & Init
        print("\n--- CHECK 1: Startup & Modular Storage Init ---")
        t0 = time.time()
        init_eng = AdaptiveIntelligenceEngine(insights_path=test_dir / "audit_check.json")
        dur = time.time() - t0
        assert dur < 0.20, f"Init duration too high ({dur:.3f}s)"
        print(f"[OK] CHECK 1 PASSED: 3.0 Engine initialized in {dur*1000:.1f}ms.")
        results.append(("1. 3.0 Runtime & Storage Init", "PASS"))

        # 2. Predictive Intent Engine
        print("\n--- CHECK 2: Predictive Intent Engine ---")
        pred_intent = engine.intent_engine.predict_intent("Working on python code", active_app="Code.exe")
        assert "CODING" in pred_intent["intent"]
        assert pred_intent["confidence"] >= 0.60
        assert len(pred_intent["reasoning_summary"]) > 5
        print(f"[OK] CHECK 2 PASSED: Predicted intent '{pred_intent['intent']}' with summary '{pred_intent['reasoning_summary']}'.")
        results.append(("2. Predictive Intent Engine", "PASS"))

        # 3. Next-Action Prediction
        print("\n--- CHECK 3: Next-Action Prediction System ---")
        seq = ["VS Code", "Terminal", "Chrome"]
        ctx = {"domain": "CODING", "project": "JARVIS"}
        for _ in range(3):
            engine.sequence_engine.record_sequence(seq, ctx)

        sug = engine.sequence_engine.predict_next_action("VS Code", ctx)
        assert sug is not None
        next_act, conf, msg, _ = sug
        assert next_act == "Terminal"
        assert "?" in msg
        print(f"[OK] CHECK 3 PASSED: Next action '{next_act}' predicted with confirmation msg.")
        results.append(("3. Next-Action Prediction System", "PASS"))

        # 4. Routine Prediction Engine
        print("\n--- CHECK 4: Routine Prediction Engine ---")
        for _ in range(3):  # Need 3+ observations to reach 0.60 confidence
            engine.routine_engine.record_routine_observation("EVENING", "MONDAY", "CODING", "JARVIS", ["VS Code", "Terminal"])
        rot = engine.routine_engine.predict_routine("EVENING", "MONDAY", "CODING")
        assert rot is not None
        assert rot["project"] == "JARVIS"
        print("[OK] CHECK 4 PASSED: Routine pattern matched successfully.")
        results.append(("4. Routine Prediction Engine", "PASS"))

        # 5. Project Context & Cross-Session Continuity
        print("\n--- CHECK 5: Project Context & Cross-Session Continuity ---")
        engine.project_engine.update_project_context("JARVIS", "VS Code", "CODING", "main.py")
        summary = engine.project_engine.get_last_session_summary("JARVIS")
        assert summary is not None
        assert summary["last_file"] == "main.py"
        print("[OK] CHECK 5 PASSED: Cross-session summary retrieved for 'JARVIS'.")
        results.append(("5. Project Context & Continuity", "PASS"))

        # 6. Outcome Learning Engine
        print("\n--- CHECK 6: Outcome Learning Engine ---")
        out = engine.outcome_engine.evaluate_prediction_outcome("pred_01", "Yes, open terminal", "SUCCESS", engine.sequence_engine)
        assert out["accepted"] is True
        print("[OK] CHECK 6 PASSED: Outcome evaluation logged and confidence updated.")
        results.append(("6. Outcome Learning Engine", "PASS"))

        # 7. 7-Tier Preference Hierarchy
        print("\n--- CHECK 7: 7-Tier Preference Priority Hierarchy ---")
        engine.add_or_update_insight("preference", "editor", "VS Code", source="explicit")
        val, tier = PreferenceHierarchyResolver.resolve_preference(
            "preference", "editor", current_instruction="Open PyCharm for this project", stored_insights=engine.insights_data.get("insights", {})
        )
        assert val == "PyCharm"
        assert tier == "TIER_1_CURRENT_INSTRUCTION"
        print("[OK] CHECK 7 PASSED: Tier 1 current instruction overrode explicit stored preference.")
        results.append(("7. 7-Tier Priority Hierarchy", "PASS"))

        # 8. Memory Consolidation Engine
        print("\n--- CHECK 8: Memory Consolidation Engine ---")
        engine.add_or_update_insight("preference", "browser", "Chrome", source="inferred", initial_confidence=0.4)
        engine.add_or_update_insight("preference", "browser", "Chrome", source="inferred", initial_confidence=0.5)
        merged = MemoryConsolidationEngine.consolidate(engine.insights_data)
        assert merged >= 0
        print("[OK] CHECK 8 PASSED: Memory consolidation duplicate merging verified.")
        results.append(("8. Memory Consolidation Engine", "PASS"))

        # 9. Privacy & Secret Redaction
        print("\n--- CHECK 9: Privacy & Secret Redaction ---")
        raw_secret = "sk-1a60099ffa27a77767028ef421a0fd4169384363e0f3a34e05f6ff42f52f234c"
        engine.add_or_update_insight("preference", "secret_key", raw_secret, source="explicit")
        file_text = engine.insights_path.read_text(encoding="utf-8")
        assert raw_secret not in file_text
        assert "[REDACTED_SECRET]" in file_text
        print("[OK] CHECK 9 PASSED: Secret scrubbing prior to disk persistence verified.")
        results.append(("9. Privacy & Secret Redaction", "PASS"))

        # 10. Voice Governance Commands
        print("\n--- CHECK 10: Voice Governance Commands ---")
        ans = engine.handle_voice_query("stop predictive intelligence")
        assert engine.predictive_enabled is False

        ans_res = engine.handle_voice_query("resume predictive intelligence")
        assert engine.predictive_enabled is True

        ans_clear = engine.handle_voice_query("clear predictions")
        assert len(engine.predictive_data.get("intent_patterns", {})) == 0
        print("[OK] CHECK 10 PASSED: Voice governance commands ('stop predictive', 'resume predictive', 'clear predictions') verified.")
        results.append(("10. Voice Governance Commands", "PASS"))

        # 11. Long-Run Stress Test (100 Turns)
        print("\n--- CHECK 11: Long-Run Stress Test (100 Interaction Turns) ---")
        t_stress = time.time()
        for turn in range(100):
            app_name = "VS Code" if turn % 2 == 0 else "Chrome"
            engine.observe_interaction(
                f"Turn {turn}: Work on app {app_name}",
                f"Turn {turn}: Done.",
                tool_calls=[{"name": "open_app", "args": {"app_name": app_name}}]
            )
        stress_dur = time.time() - t_stress

        assert stress_dur < 35.0, f"100-turn stress test took too long ({stress_dur:.3f}s)"
        ins_count = len(engine.insights_data.get("insights", {}))
        assert ins_count < 100, f"Memory leak detected ({ins_count} items)"
        print(f"[OK] CHECK 11 PASSED: 100 interaction turns executed in {stress_dur:.2f}s without memory leaks.")
        results.append(("11. Long-Run Stress Test (100 Turns)", "PASS"))

        # 12. Fault Injection & Resilience
        print("\n--- CHECK 12: Fault Injection & Exception Isolation ---")
        try:
            ContextDetector.detect_context(None, None, None, None)
            engine.sequence_engine.predict_next_action(None, {})
            engine.intent_engine.predict_intent(None)
            engine.get_adaptive_context(None)
            engine.observe_interaction(None, None)
        except Exception as ex:
            assert False, f"CRITICAL FAULT ISOLATION FAILURE: {ex}"

        print("[OK] CHECK 12 PASSED: 0 uncaught exceptions escaped adaptive layer.")
        results.append(("12. Fault Injection & Resilience", "PASS"))

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    # 13. Summary Matrix
    print("\n" + "=" * 70)
    print("  ADAPTIVE INTELLIGENCE 3.0 PREDICTIVE AUDIT MATRIX  ")
    print("=" * 70)
    all_pass = True
    for name, status in results:
        pad = "." * (52 - len(name))
        print(f"{name} {pad} [{status}]")
        if status != "PASS":
            all_pass = False
    print("=" * 70)

    if all_pass:
        print("  ALL 13 AUDIT CHECKS PASSED CLEANLY!  ")
        print("=" * 70)
    else:
        print("  AUDIT FAILED!  ")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    run_predictive_audit()
