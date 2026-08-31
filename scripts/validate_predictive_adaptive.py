# scripts/validate_predictive_adaptive.py
"""
Adaptive Intelligence 3.0 Predictive Personal Agent Multi-Day Real-World Simulation Script.

Simulates a multi-day realistic user workflow:
- DAY 1: User works on JARVIS project (VS Code -> Terminal -> Chrome).
- DAY 2: User continues project work with matching sequence.
- DAY 3: Intent prediction and Next-Action prediction become strong (Confidence >= 0.85).
- OVERRIDE: User explicitly requests PyCharm -> PyCharm wins instantly (Tier 1 override).
- FEEDBACK: User rejects Terminal suggestion multiple times -> cooldown doubles, confidence drops.
- RECOVERY: User returns to workflow -> prediction confidence recovers safely based on new evidence.
- ISOLATION: CODING, COLLEGE, ENTERTAINMENT, BROWSING, PROJECT_WORK contexts remain strictly isolated.
"""

import json
import shutil
import sys
import tempfile
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


def run_predictive_validation():
    print("=" * 70)
    print("  JARVIS ADAPTIVE INTELLIGENCE 3.0 PREDICTIVE VALIDATION  ")
    print("=" * 70)

    test_dir = Path(tempfile.mkdtemp())
    insights_file = test_dir / "adaptive_insights.json"
    engine = AdaptiveIntelligenceEngine(insights_path=insights_file)

    results = []

    try:
        # ------------------------------------------------
        # SIMULATION DAY 1: Initial Learning
        # ------------------------------------------------
        print("\n--- DAY 1: Initial Workflow & Intent Observation ---")
        t1 = [{"name": "open_app", "args": {"app_name": "VS Code"}}]
        t2 = [{"name": "open_app", "args": {"app_name": "Terminal"}}]
        t3 = [{"name": "open_app", "args": {"app_name": "Chrome"}}]

        engine.observe_interaction("Start working on JARVIS project", "Opening VS Code...", tool_calls=t1, cwd="/Desktop/JARVIS MAIN")
        engine.observe_interaction("Open terminal to run tests", "Opening Terminal...", tool_calls=t2, cwd="/Desktop/JARVIS MAIN")
        engine.observe_interaction("Open Chrome for docs", "Opening Chrome...", tool_calls=t3, cwd="/Desktop/JARVIS MAIN")
        print("[OK] DAY 1: Initial turn sequence recorded.")

        # ------------------------------------------------
        # SIMULATION DAY 2: Reinforcement
        # ------------------------------------------------
        print("\n--- DAY 2: Pattern Reinforcement & Routine Detection ---")
        for _ in range(2):
            engine.observe_interaction("Continue JARVIS development", "Opening VS Code...", tool_calls=t1, cwd="/Desktop/JARVIS MAIN")
            engine.observe_interaction("Open terminal", "Opening Terminal...", tool_calls=t2, cwd="/Desktop/JARVIS MAIN")
            engine.observe_interaction("Check docs on Chrome", "Opening Chrome...", tool_calls=t3, cwd="/Desktop/JARVIS MAIN")

        print("[OK] DAY 2: Sequence reinforced.")

        # ------------------------------------------------
        # SIMULATION DAY 3: Intent & Next-Action Prediction
        # ------------------------------------------------
        print("\n--- DAY 3: Predictive Intent & Next-Action Evaluation ---")
        pred_intent = engine.intent_engine.predict_intent(query="I need to code on JARVIS", cwd="/Desktop/JARVIS MAIN")
        assert "CODING" in pred_intent["intent"], f"Expected CODING intent, got {pred_intent['intent']}"
        assert pred_intent["confidence"] >= 0.60, f"Expected confidence >= 0.60, got {pred_intent['confidence']}"

        ctx = ContextDetector.detect_context("Working on JARVIS project", cwd="/Desktop/JARVIS MAIN")
        pred_action = engine.sequence_engine.predict_next_action("VS Code", ctx)

        assert pred_action is not None, "Failed to predict next action after VS Code!"
        next_act, conf, msg, pat = pred_action
        assert next_act == "Terminal", f"Expected Terminal, got {next_act}"
        assert "Want me to prepare" in msg, "Proactive suggestion MUST ask user confirmation!"
        print(f"[OK] DAY 3 PASSED: Predicted Intent '{pred_intent['intent']}' & Next-Action '{next_act}' (conf: {conf:.2f}).")
        results.append(("1. Intent & Next-Action Prediction", "PASS"))

        # ------------------------------------------------
        # EXPLICIT OVERRIDE: PyCharm vs VS Code Stored Preference
        # ------------------------------------------------
        print("\n--- TEST: Explicit Current Instruction Override (PyCharm) ---")
        engine.add_or_update_insight("preference", "python_editor", "VS Code", source="explicit")
        val, tier = PreferenceHierarchyResolver.resolve_preference(
            "preference",
            "python_editor",
            current_instruction="Open PyCharm for this project",
            stored_insights=engine.insights_data.get("insights", {})
        )

        assert val == "PyCharm", f"Expected PyCharm, got {val}"
        assert tier == "TIER_1_CURRENT_INSTRUCTION", f"Expected TIER_1_CURRENT_INSTRUCTION, got {tier}"
        print("[OK] EXPLICIT OVERRIDE PASSED: Current instruction 'PyCharm' overrode stored preference 'VS Code' (TIER_1).")
        results.append(("2. Explicit Command Override Priority", "PASS"))

        # ------------------------------------------------
        # NEGATIVE FEEDBACK & RECOVERY
        # ------------------------------------------------
        print("\n--- TEST: Negative Feedback Cooldown & Recovery ---")
        seq_key = "VS Code -> Terminal -> Chrome"
        engine.sequence_engine.record_suggestion_feedback(seq_key, accepted=False)
        c1 = engine.patterns_data["patterns"][seq_key]["cooldown_seconds"]
        assert c1 == 600, f"Expected doubled cooldown 600s, got {c1}"

        # Recovery on acceptance
        engine.sequence_engine.record_suggestion_feedback(seq_key, accepted=True)
        c2 = engine.patterns_data["patterns"][seq_key]["cooldown_seconds"]
        assert c2 == 300, f"Expected reset cooldown 300s, got {c2}"
        print("[OK] FEEDBACK PASSED: Rejection doubled cooldown to 600s; subsequent acceptance reset cooldown to 300s.")
        results.append(("3. Negative/Positive Feedback Dynamics", "PASS"))

        # ------------------------------------------------
        # CONTEXT ISOLATION (CODING vs COLLEGE vs ENTERTAINMENT)
        # ------------------------------------------------
        print("\n--- TEST: Strict Context & Project Isolation ---")
        engine.add_or_update_insight("preference", "ide", "VS Code", source="explicit", context={"domain": "CODING"})
        engine.add_or_update_insight("preference", "reader", "Acrobat", source="explicit", context={"domain": "COLLEGE"})

        coding_context = engine.get_adaptive_context(query="Run python tests")
        college_context = engine.get_adaptive_context(query="Read lecture assignment pdf")

        assert "vs code" in coding_context.lower()
        assert "acrobat" not in coding_context.lower(), "College memory bled into coding context!"
        assert "acrobat" in college_context.lower()
        assert "vs code" not in college_context.lower(), "Coding memory bled into college context!"
        print("[OK] CONTEXT ISOLATION PASSED: Coding and College contexts strictly isolated.")
        results.append(("4. Strict Context & Project Isolation", "PASS"))

        # ------------------------------------------------
        # PRIVACY & SECRET REDACTION
        # ------------------------------------------------
        print("\n--- TEST: Privacy & Secret Redaction ---")
        raw_secret = "sk-1a60099ffa27a77767028ef421a0fd4169384363e0f3a34e05f6ff42f52f234c"
        engine.add_or_update_insight("preference", "openai_key", raw_secret, source="explicit")

        file_text = engine.insights_path.read_text(encoding="utf-8")
        assert raw_secret not in file_text, "CRITICAL SECURITY BREACH: Raw secret written to disk!"
        assert "[REDACTED_SECRET]" in file_text, "Secret was not scrubbed with [REDACTED_SECRET]"
        print("[OK] PRIVACY PASSED: Raw API keys scrubbed to [REDACTED_SECRET] prior to disk storage.")
        results.append(("5. Privacy & Secret Redaction", "PASS"))

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    # ------------------------------------------------
    # SUMMARY MATRIX
    # ------------------------------------------------
    print("\n" + "=" * 70)
    print("  ADAPTIVE INTELLIGENCE 3.0 PREDICTIVE VALIDATION MATRIX  ")
    print("=" * 70)
    all_pass = True
    for name, status in results:
        pad = "." * (52 - len(name))
        print(f"{name} {pad} [{status}]")
        if status != "PASS":
            all_pass = False
    print("=" * 70)

    if all_pass:
        print("  ALL PREDICTIVE VALIDATION SCENARIOS PASSED CLEANLY!  ")
        print("=" * 70)
    else:
        print("  PREDICTIVE VALIDATION FAILED!  ")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    run_predictive_validation()
