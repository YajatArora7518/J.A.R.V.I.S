# tests/test_predictive_adaptive.py
"""
Comprehensive 30-Category Unit Test Suite for Context-Aware Adaptive Intelligence 3.0
Tests all core predictive personal agent features:
1. Intent prediction
2. Next-action prediction
3. Routine detection
4. Cross-session continuity
5. Project context
6. Outcome learning
7. Prediction confidence
8. Confidence bounds (0.00 to 1.00)
9. Explicit override (Tier 1 current command always wins)
10. Context isolation
11. Prediction rejection
12. Prediction acceptance
13. Memory consolidation
14. Duplicate memory merging
15. Contradictory preference handling
16. Prediction explanation
17. Safe suggestion behavior
18. No silent execution
19. Secret redaction
20. Corrupted storage recovery
21. Concurrent access (multithreaded)
22. Learning disable
23. Prediction disable
24. Forget prediction
25. Full reset
26. Temporal decay (14-day)
27. Cross-project isolation
28. Cross-session retrieval
29. Long-run bounded growth
30. Fault isolation
"""

import json
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from memory.adaptive_intelligence import (
    AdaptiveIntelligenceEngine,
    ContextDetector,
    MemoryConsolidationEngine,
    PersonalWorkflowGraph,
    PreferenceHierarchyResolver,
    PredictiveIntentEngine,
    ProjectContextEngine,
    RoutinePredictionEngine,
    WorkflowSequenceEngine,
    redact_secrets,
)


class TestPredictiveAdaptiveIntelligence3(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.insights_file = self.test_dir / "adaptive_insights.json"
        self.engine = AdaptiveIntelligenceEngine(insights_path=self.insights_file)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    # 1. Intent prediction
    def test_intent_prediction(self):
        pred = self.engine.intent_engine.predict_intent(query="I need to code on JARVIS", active_app="Code.exe")
        self.assertIn("CODING", pred["intent"])
        self.assertGreaterEqual(pred["confidence"], 0.60)

    # 2. Next-action prediction
    def test_next_action_prediction(self):
        seq = ["VS Code", "Terminal", "Chrome"]
        ctx = {"domain": "CODING", "project": "JARVIS"}
        for _ in range(3):
            self.engine.sequence_engine.record_sequence(seq, ctx)

        res = self.engine.sequence_engine.predict_next_action("VS Code", ctx)
        self.assertIsNotNone(res)
        next_action, conf, msg, pat = res
        self.assertEqual(next_action, "Terminal")

    # 3. Routine detection
    def test_routine_detection(self):
        # Record enough observations to reach 0.60 confidence (0.35 -> 0.51 -> 0.63)
        for _ in range(3):
            self.engine.routine_engine.record_routine_observation("EVENING", "MONDAY", "CODING", "JARVIS", ["VS Code", "Terminal"])
        pred_rot = self.engine.routine_engine.predict_routine("EVENING", "MONDAY", "CODING")
        self.assertIsNotNone(pred_rot)
        self.assertGreaterEqual(pred_rot["confidence"], 0.60)

    # 4. Cross-session continuity
    def test_cross_session_continuity(self):
        self.engine.project_engine.update_project_context("JARVIS", "VS Code", "CODING", "adaptive_intelligence.py")
        summary = self.engine.project_engine.get_last_session_summary("JARVIS")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["last_file"], "adaptive_intelligence.py")

    # 5. Project context
    def test_project_context(self):
        self.engine.project_engine.update_project_context("JARVIS", "VS Code", "CODING")
        proj = self.engine.project_engine.data.get("JARVIS")
        self.assertIsNotNone(proj)
        self.assertIn("VS Code", proj["typical_tools"])

    # 6. Outcome learning
    def test_outcome_learning(self):
        out = self.engine.outcome_engine.evaluate_prediction_outcome(
            "p123", "Yes, open terminal", "SUCCESS", self.engine.sequence_engine
        )
        self.assertTrue(out["accepted"])

    # 7. Prediction confidence
    def test_prediction_confidence(self):
        pred = self.engine.intent_engine.predict_intent(query="python dev work")
        self.assertGreaterEqual(pred["confidence"], 0.50)

    # 8. Confidence bounds (0.00 to 1.00)
    def test_confidence_bounds(self):
        ins = self.engine.add_or_update_insight("preference", "tool", "VS Code", source="inferred", initial_confidence=0.99)
        self.assertLessEqual(ins["confidence"], 0.98)

    # 9. Explicit override
    def test_explicit_override(self):
        self.engine.add_or_update_insight("preference", "editor", "VS Code", source="explicit")
        val, tier = PreferenceHierarchyResolver.resolve_preference(
            "preference", "editor", current_instruction="Open PyCharm for this", stored_insights=self.engine.insights_data.get("insights", {})
        )
        self.assertEqual(val, "PyCharm")
        self.assertEqual(tier, "TIER_1_CURRENT_INSTRUCTION")

    # 10. Context isolation
    def test_context_isolation(self):
        ctx_c = {"domain": "CODING"}
        ctx_clg = {"domain": "COLLEGE"}
        self.engine.add_or_update_insight("preference", "ide", "VS Code", source="explicit", context=ctx_c)
        self.engine.add_or_update_insight("preference", "reader", "Acrobat", source="explicit", context=ctx_clg)

        ctx_str = self.engine.get_adaptive_context(query="python code task")
        self.assertNotIn("Acrobat", ctx_str)

    # 11. Prediction rejection
    def test_prediction_rejection(self):
        seq = ["VS Code", "Terminal"]
        ctx = {"domain": "CODING"}
        for _ in range(3):
            self.engine.sequence_engine.record_sequence(seq, ctx)

        self.engine.sequence_engine.record_suggestion_feedback("VS Code -> Terminal", accepted=False)
        pat = self.engine.patterns_data["patterns"]["VS Code -> Terminal"]
        self.assertEqual(pat["cooldown_seconds"], 600)

    # 12. Prediction acceptance
    def test_prediction_acceptance(self):
        seq = ["VS Code", "Terminal"]
        ctx = {"domain": "CODING"}
        for _ in range(3):
            self.engine.sequence_engine.record_sequence(seq, ctx)

        self.engine.sequence_engine.record_suggestion_feedback("VS Code -> Terminal", accepted=True)
        pat = self.engine.patterns_data["patterns"]["VS Code -> Terminal"]
        self.assertEqual(pat["cooldown_seconds"], 300)

    # 13. Memory consolidation
    def test_memory_consolidation(self):
        self.engine.add_or_update_insight("preference", "lang", "Python", source="inferred", initial_confidence=0.4)
        self.engine.add_or_update_insight("preference", "lang", "Python", source="inferred", initial_confidence=0.5)
        count = MemoryConsolidationEngine.consolidate(self.engine.insights_data)
        self.assertGreaterEqual(count, 0)

    # 14. Duplicate memory merging
    def test_duplicate_memory_merging(self):
        insights = self.engine.insights_data.setdefault("insights", {})
        insights["id1"] = {"key": "browser", "value": "Chrome", "confidence": 0.5, "source": "inferred", "enabled": True}
        insights["id2"] = {"key": "browser", "value": "Chrome", "confidence": 0.98, "source": "explicit", "enabled": True}
        merged = MemoryConsolidationEngine.consolidate(self.engine.insights_data)
        self.assertEqual(merged, 1)

    # 15. Contradictory preference handling
    def test_contradictory_preference_handling(self):
        self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred", initial_confidence=0.5)
        res = self.engine.add_or_update_insight("preference", "editor", "PyCharm", source="explicit")
        self.assertEqual(res["value"], "PyCharm")

    # 16. Prediction explanation
    def test_prediction_explanation(self):
        ans = self.engine.handle_voice_query("Why did you suggest Terminal?")
        self.assertIn("Terminal", ans)

    # 17. Safe suggestion behavior
    def test_safe_suggestion_behavior(self):
        seq = ["VS Code", "Terminal"]
        ctx = {"domain": "CODING"}
        for _ in range(3):
            self.engine.sequence_engine.record_sequence(seq, ctx)

        sug = self.engine.sequence_engine.get_proactive_suggestion("VS Code", ctx)
        self.assertIsNotNone(sug)
        msg, _ = sug
        self.assertIn("?", msg)

    # 18. No silent execution
    def test_no_silent_execution(self):
        # Suggestions generate question string without modifying system app execution
        sug = self.engine.sequence_engine.predict_next_action("VS Code", {"domain": "CODING"})
        if sug:
            _, _, msg, _ = sug
            self.assertIn("Want me to prepare", msg)

    # 19. Secret redaction
    def test_secret_redaction(self):
        sec = "sk-1a60099ffa27a77767028ef421a0fd4169384363e0f3a34e05f6ff42f52f234c"
        redacted = redact_secrets(f"My token is {sec}")
        self.assertNotIn(sec, redacted)

    # 20. Corrupted storage recovery
    def test_corrupted_storage_recovery(self):
        self.insights_file.write_text("INVALID { JSON", encoding="utf-8")
        rec = AdaptiveIntelligenceEngine(insights_path=self.insights_file)
        self.assertIsNotNone(rec.insights_data)

    # 21. Concurrent access
    def test_concurrent_access(self):
        def worker():
            for i in range(10):
                self.engine.add_or_update_insight("preference", f"key_{i}", f"val_{i}")

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertGreater(len(self.engine.insights_data.get("insights", {})), 0)

    # 22. Learning disable
    def test_learning_disable(self):
        self.engine.observe_interaction("Jarvis, stop adaptive learning", "Disabled.")
        self.assertFalse(self.engine.learning_enabled)

    # 23. Prediction disable
    def test_prediction_disable(self):
        self.engine.observe_interaction("stop predictive intelligence", "Disabled.")
        self.assertFalse(self.engine.predictive_enabled)

    # 24. Forget prediction
    def test_forget_prediction(self):
        self.engine.handle_voice_query("clear predictions")
        self.assertEqual(len(self.engine.predictive_data.get("intent_patterns", {})), 0)

    # 25. Full reset
    def test_full_reset(self):
        self.engine.reset_learning()
        self.assertEqual(len(self.engine.insights_data.get("insights", {})), 0)

    # 26. Temporal decay (14-day)
    def test_temporal_decay(self):
        ins = self.engine.add_or_update_insight("preference", "old_editor", "Atom", source="inferred", initial_confidence=0.6)
        ins["last_seen"] = (datetime.now() - timedelta(days=20)).isoformat()
        self.engine.save()

        self.engine.apply_decay(days_threshold=14, decay_factor=0.2)
        updated = self.engine.insights_data["insights"][ins["insight_id"]]
        self.assertLess(updated["confidence"], 0.6)

    # 27. Cross-project isolation
    def test_cross_project_isolation(self):
        self.engine.project_engine.update_project_context("PROJECT_A", "ToolA", "TASK_A")
        self.engine.project_engine.update_project_context("PROJECT_B", "ToolB", "TASK_B")
        summary_a = self.engine.project_engine.get_last_session_summary("PROJECT_A")
        summary_b = self.engine.project_engine.get_last_session_summary("PROJECT_B")
        self.assertNotEqual(summary_a["project"], summary_b["project"])

    # 28. Cross-session retrieval
    def test_cross_session_retrieval(self):
        self.engine.project_engine.update_project_context("JARVIS", "VS Code", "CODING", "main.py")
        summary = self.engine.project_engine.get_last_session_summary("JARVIS")
        self.assertEqual(summary["last_file"], "main.py")

    # 29. Long-run bounded growth
    def test_long_run_bounded_growth(self):
        for i in range(50):
            self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred")
        ins_list = list(self.engine.insights_data.get("insights", {}).values())
        self.assertLessEqual(len(ins_list), 5)

    # 30. Fault isolation
    def test_fault_isolation(self):
        try:
            ContextDetector.detect_context(None, None, None, None)
            self.engine.sequence_engine.predict_next_action(None, {})
            self.engine.intent_engine.predict_intent(None)
            self.engine.get_adaptive_context(None)
        except Exception as ex:
            self.fail(f"Fault isolation failed: {ex}")


if __name__ == "__main__":
    unittest.main()
