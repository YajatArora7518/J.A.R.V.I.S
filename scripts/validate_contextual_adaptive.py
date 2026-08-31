# scripts/validate_contextual_adaptive.py
"""
Context-Aware Adaptive Intelligence 2.0 Real-World Validation Script.

Simulates realistic user workflows and verifies end-to-end adaptive intelligence:
1. Multi-turn workflow learning (VS Code -> Terminal -> Chrome)
2. Confidence reinforcement curve
3. Context detection (CODING, BROWSING, COLLEGE, etc.)
4. Workflow pattern recognition
5. Proactive suggestion generation
6. Suggestion feedback & rejection handling (cooldown adjustment)
7. Explicit user instruction overriding learned behavior (Tier 1 vs Tiers 2-5)
8. Secret redaction prior to disk storage
9. Selective preference forgetting
10. Workflow pattern reset
11. Adaptive learning toggle (Disable / Resume)
12. Clear PASS/FAIL matrix output
"""

import json
import shutil
import tempfile
import sys
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
    PreferenceHierarchyResolver,
    redact_secrets,
)


def run_realworld_validation():
    print("=" * 60)
    print("  JARVIS ADAPTIVE INTELLIGENCE 2.0 REAL-WORLD VALIDATION  ")
    print("=" * 60)

    test_dir = Path(tempfile.mkdtemp())
    insights_file = test_dir / "adaptive_insights.json"
    engine = AdaptiveIntelligenceEngine(insights_path=insights_file)

    results = []

    try:
        # ------------------------------------------------
        # 1. CONTEXT DETECTION VALIDATION
        # ------------------------------------------------
        print("\n--- STEP 1: Multidimensional Context Detection ---")
        ctx_coding = ContextDetector.detect_context("Write python unit tests in VS Code", active_app="Code.exe")
        ctx_browsing = ContextDetector.detect_context("Search documentation online", recent_tools=["web_search"])
        ctx_college = ContextDetector.detect_context("Read lecture assignment pdf")

        assert ctx_coding["domain"] == "CODING", f"Expected CODING, got {ctx_coding['domain']}"
        assert ctx_browsing["domain"] == "BROWSING", f"Expected BROWSING, got {ctx_browsing['domain']}"
        assert ctx_college["domain"] == "COLLEGE", f"Expected COLLEGE, got {ctx_college['domain']}"
        print("[OK] STEP 1 PASSED: Domain categories (CODING, BROWSING, COLLEGE) correctly inferred.")
        results.append(("1. Multidimensional Context Detection", "PASS"))

        # ------------------------------------------------
        # 2. WORKFLOW SEQUENCE LEARNING & REINFORCEMENT
        # ------------------------------------------------
        print("\n--- STEP 2: Workflow Sequence Learning (N-gram) ---")
        tool_calls_1 = [{"name": "open_app", "args": {"app_name": "VS Code"}}]
        tool_calls_2 = [{"name": "open_app", "args": {"app_name": "Terminal"}}]
        tool_calls_3 = [{"name": "open_app", "args": {"app_name": "Chrome"}}]

        # Turn 1
        engine.observe_interaction("Open VS Code for coding", "Opening VS Code...", tool_calls=tool_calls_1)
        # Turn 2
        engine.observe_interaction("Open Terminal", "Opening Terminal...", tool_calls=tool_calls_2)
        # Turn 3
        engine.observe_interaction("Open Chrome for docs", "Opening Chrome...", tool_calls=tool_calls_3)

        # Repeat workflow turns 2 more times to reinforce confidence
        for _ in range(2):
            engine.observe_interaction("Open VS Code for coding", "Opening VS Code...", tool_calls=tool_calls_1)
            engine.observe_interaction("Open Terminal", "Opening Terminal...", tool_calls=tool_calls_2)
            engine.observe_interaction("Open Chrome for docs", "Opening Chrome...", tool_calls=tool_calls_3)

        patterns = engine.patterns_data.get("patterns", {})
        seq_key = "VS Code -> Terminal -> Chrome"
        assert seq_key in patterns, f"Sequence key '{seq_key}' not found in learned patterns!"
        pat_conf = patterns[seq_key]["confidence"]
        assert pat_conf >= 0.60, f"Pattern confidence {pat_conf} expected to be >= 0.60"
        print(f"[OK] STEP 2 PASSED: Sequence '{seq_key}' learned with confidence {pat_conf:.2f}")
        results.append(("2. Workflow Sequence Learning", "PASS"))

        # ------------------------------------------------
        # 3. PROACTIVE WORKFLOW SUGGESTION & FEEDBACK
        # ------------------------------------------------
        print("\n--- STEP 3: Proactive Workflow Suggestion & Feedback ---")
        ctx = ContextDetector.detect_context("Open VS Code for coding")
        sug = engine.sequence_engine.get_proactive_suggestion("VS Code", ctx)

        assert sug is not None, "Failed to generate proactive suggestion for VS Code!"
        msg, pat = sug
        assert "Terminal" in msg, f"Expected 'Terminal' in suggestion, got: {msg}"
        print(f"[OK] Suggestion generated: '{msg}'")

        # Simulate user rejecting suggestion
        engine.sequence_engine.record_suggestion_feedback(seq_key, accepted=False)
        updated_cooldown = patterns[seq_key]["cooldown_seconds"]
        assert updated_cooldown > 300, f"Expected cooldown to increase (>300s), got {updated_cooldown}s"
        print(f"[OK] STEP 3 PASSED: Suggestion rejection handled and cooldown doubled to {updated_cooldown}s")
        results.append(("3. Proactive Workflow Suggestion & Feedback", "PASS"))

        # ------------------------------------------------
        # 4. EXPLICIT OVERRIDE VS LEARNED PREFERENCE
        # ------------------------------------------------
        print("\n--- STEP 4: Explicit User Command Priority (Tier 1 vs Tier 2-5) ---")
        engine.add_or_update_insight("preference", "python_editor", "VS Code", source="explicit")

        # Explicit user command requesting PyCharm for current task
        val, tier = PreferenceHierarchyResolver.resolve_preference(
            "preference",
            "python_editor",
            current_instruction="Open PyCharm for this project",
            stored_insights=engine.insights_data.get("insights", {})
        )

        assert val == "PyCharm", f"Expected PyCharm, got {val}"
        assert tier == "TIER_1_CURRENT_INSTRUCTION", f"Expected TIER_1_CURRENT_INSTRUCTION, got {tier}"
        print("[OK] STEP 4 PASSED: Explicit instruction 'PyCharm' overrode stored preference 'VS Code' (TIER_1).")
        results.append(("4. Explicit Command Override Priority", "PASS"))

        # ------------------------------------------------
        # 5. PRIVACY & SECRET REDACTION
        # ------------------------------------------------
        print("\n--- STEP 5: Privacy Secret Redaction ---")
        raw_secret = "sk-1a60099ffa27a77767028ef421a0fd4169384363e0f3a34e05f6ff42f52f234c"
        engine.add_or_update_insight("preference", "api_key", raw_secret, source="explicit")

        file_text = engine.insights_path.read_text(encoding="utf-8")
        assert raw_secret not in file_text, "CRITICAL: Raw API key was written to disk!"
        assert "[REDACTED_SECRET]" in file_text, "Secret was not replaced with [REDACTED_SECRET]!"
        print("[OK] STEP 5 PASSED: Secrets scrubbed prior to disk persistence.")
        results.append(("5. Privacy & Secret Redaction", "PASS"))

        # ------------------------------------------------
        # 6. SELECTIVE FORGETTING & WORKFLOW RESET
        # ------------------------------------------------
        print("\n--- STEP 6: Selective Forgetting & Reset ---")
        engine.add_or_update_insight("preference", "game_launcher", "Steam", source="explicit")
        engine.forget_insight("game_launcher")
        assert "game_launcher" not in [i.get("key") for i in engine.insights_data.get("insights", {}).values()]

        engine.forget_workflow_patterns()
        assert len(engine.patterns_data.get("patterns", {})) == 0
        print("[OK] STEP 6 PASSED: Selective preference removal and workflow pattern reset verified.")
        results.append(("6. Selective Forgetting & Reset", "PASS"))

        # ------------------------------------------------
        # 7. ADAPTIVE LEARNING DISABLE & RESUME
        # ------------------------------------------------
        print("\n--- STEP 7: Learning Toggle (Disable / Resume) ---")
        engine.observe_interaction("Jarvis, stop adaptive learning", "Disabled.")
        assert not engine.learning_enabled, "Learning should be disabled!"

        res = engine.add_or_update_insight("preference", "browser", "Opera")
        assert res is None, "Insight should not be saved while learning is disabled!"

        engine.observe_interaction("Jarvis, resume adaptive learning", "Resumed.")
        assert engine.learning_enabled, "Learning should be resumed!"
        print("[OK] STEP 7 PASSED: Adaptive learning disable and resume toggles verified.")
        results.append(("7. Learning Toggle (Disable / Resume)", "PASS"))

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    # ------------------------------------------------
    # SUMMARY MATRIX
    # ------------------------------------------------
    print("\n" + "=" * 60)
    print("  CONTEXT-AWARE ADAPTIVE INTELLIGENCE 2.0 VALIDATION MATRIX  ")
    print("=" * 60)
    all_pass = True
    for name, status in results:
        pad = "." * (50 - len(name))
        print(f"{name} {pad} [{status}]")
        if status != "PASS":
            all_pass = False
    print("=" * 60)

    if all_pass:
        print("  ALL REAL-WORLD VALIDATION TESTS PASSED CLEANLY!  ")
        print("=" * 60)
    else:
        print("  SOME TESTS FAILED!  ")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    run_realworld_validation()
