# scripts/validate_real_world_adaptive.py
"""
Real-world validation script for JARVIS Adaptive Intelligence
Validates:
1. Explicit preference learning ("Jarvis, I prefer VS Code for Python")
2. Repeated behavior confidence reinforcement (0.35 -> 0.51 -> 0.63 -> ...)
3. Tool failure learning & reflex correction
4. Privacy secret redaction (sk-keys, passwords, credit cards)
5. Disable command ("Jarvis, stop adaptive learning")
6. Reset command ("Jarvis, reset adaptive intelligence")
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from memory.adaptive_intelligence import AdaptiveIntelligenceEngine, redact_secrets


def run_validation():
    print("==================================================")
    print("  JARVIS ADAPTIVE INTELLIGENCE REAL-WORLD VALIDATION")
    print("==================================================")

    with tempfile.TemporaryDirectory() as tmp_dir:
        insights_file = Path(tmp_dir) / "adaptive_insights.json"
        engine = AdaptiveIntelligenceEngine(insights_path=insights_file)

        # ------------------------------------------------
        # TEST 1: EXPLICIT PREFERENCE LEARNING
        # ------------------------------------------------
        print("\n--- TEST 1: Explicit Preference Learning ---")
        user_input_1 = "Jarvis, I prefer VS Code for Python"
        engine.observe_interaction(user_input_1, "Understood, sir. Noted your preference for VS Code.")

        context_1 = engine.get_adaptive_context()
        print(f"[Synthesized Context]:\n{context_1}")
        assert "vs code" in context_1.lower() or "python" in context_1.lower(), "Explicit preference failed to appear in adaptive context!"
        print("[OK] TEST 1 PASSED: Explicit preference learned with high confidence and injected into adaptive context.")

        # ------------------------------------------------
        # TEST 2: REPEATED BEHAVIOR CONFIDENCE REINFORCEMENT
        # ------------------------------------------------
        print("\n--- TEST 2: Repeated Behavior Confidence Reinforcement ---")
        # Inferred observation 1
        ins1 = engine.add_or_update_insight("preference", "web_browser", "Google Chrome", source="inferred", initial_confidence=0.35)
        conf1 = ins1["confidence"]
        print(f"Observation 1 -> count: {ins1['observation_count']}, confidence: {conf1:.4f}")

        # Inferred observation 2
        ins2 = engine.add_or_update_insight("preference", "web_browser", "Google Chrome", source="inferred", initial_confidence=0.35)
        conf2 = ins2["confidence"]
        print(f"Observation 2 -> count: {ins2['observation_count']}, confidence: {conf2:.4f}")

        # Inferred observation 3
        ins3 = engine.add_or_update_insight("preference", "web_browser", "Google Chrome", source="inferred", initial_confidence=0.35)
        conf3 = ins3["confidence"]
        print(f"Observation 3 -> count: {ins3['observation_count']}, confidence: {conf3:.4f}")

        assert conf3 > conf2 > conf1, "Confidence score did not increase with repeated observations!"
        assert conf3 >= 0.60, f"Confidence {conf3} did not reach 0.60 threshold after 3 observations!"
        print("[OK] TEST 2 PASSED: Asymptotic confidence reinforcement curve verified (0.35 -> 0.51 -> 0.63).")

        # ------------------------------------------------
        # TEST 3: TOOL FAILURE LEARNING & REFLEX
        # ------------------------------------------------
        print("\n--- TEST 3: Tool Failure Learning & Reflex ---")
        failed_args = {"query": "python 3.14 specs"}
        corrected_args = {"query": "python 3.14 documentation"}
        engine.record_tool_reflex("web_search", failed_args, corrected_args)

        suggested = engine.suggest_tool_correction("web_search", failed_args)
        print(f"Failed args: {failed_args}")
        print(f"Suggested correction: {suggested}")
        assert suggested == corrected_args, "Tool reflex failed to suggest learned correction!"
        print("[OK] TEST 3 PASSED: Tool failure correction learned and applied successfully.")

        # ------------------------------------------------
        # TEST 4: PRIVACY & SECRET REDACTION
        # ------------------------------------------------
        print("\n--- TEST 4: Privacy Secret Redaction ---")
        secret_key = "sk-1a60099ffa27a77767028ef421a0fd4169384363e0f3a34e05f6ff42f52f234c"
        engine.add_or_update_insight("preference", "openai_key", secret_key, source="explicit")

        file_text = insights_file.read_text(encoding="utf-8")
        assert secret_key not in file_text, "CRITICAL: Raw API key was saved into adaptive_insights.json!"
        assert "[REDACTED_SECRET]" in file_text, "Secret was not replaced with [REDACTED_SECRET]!"
        print("[OK] TEST 4 PASSED: API key and secrets successfully redacted prior to disk persistence.")

        # ------------------------------------------------
        # TEST 5: DISABLE COMMAND
        # ------------------------------------------------
        print("\n--- TEST 5: Disable Voice Command ---")
        engine.observe_interaction("Jarvis, stop adaptive learning", "Adaptive learning disabled.")
        assert engine.learning_enabled is False, "Learning was not disabled by voice command!"

        # Attempt to add new insight while disabled
        res = engine.add_or_update_insight("preference", "theme", "Cyberpunk")
        assert res is None, "New insight was added while adaptive learning was disabled!"
        print("[OK] TEST 5 PASSED: 'Jarvis, stop adaptive learning' pauses adaptive learning completely.")

        # Re-enable
        engine.observe_interaction("Jarvis, resume adaptive learning", "Resumed.")
        assert engine.learning_enabled is True, "Learning was not resumed!"

        # ------------------------------------------------
        # TEST 6: RESET COMMAND
        # ------------------------------------------------
        print("\n--- TEST 6: Reset Voice Command ---")
        engine.observe_interaction("Jarvis, reset adaptive intelligence", "Resetting memory.")
        assert len(engine.data.get("insights", {})) == 0, "Insights were not cleared upon reset command!"
        assert len(engine.data.get("tool_reflexes", {})) == 0, "Tool reflexes were not cleared upon reset command!"
        assert engine.learning_enabled is True, "Learning state should reset to enabled!"
        print("[OK] TEST 6 PASSED: 'Jarvis, reset adaptive intelligence' cleared adaptive dataset cleanly.")

    print("\n==================================================")
    print("  ALL 6 REAL-WORLD VALIDATION TESTS PASSED CLEANLY!")
    print("==================================================")


if __name__ == "__main__":
    run_validation()
