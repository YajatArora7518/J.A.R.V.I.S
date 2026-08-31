# tests/test_contextual_adaptive.py
"""
Comprehensive Unit Test Suite for Context-Aware Adaptive Intelligence 2.0
Covers all 25 specified test categories:
1. CODING context detection
2. BROWSING context detection
3. COLLEGE context detection
4. FILE_MANAGEMENT context detection
5. Time bucket detection
6. Project detection
7. Preference priority hierarchy
8. Current instruction override
9. Explicit preference override
10. Contextual preference
11. Workflow N-gram learning
12. Confidence reinforcement
13. Temporal decay
14. Workflow graph
15. Contextual tool routing
16. Proactive suggestion
17. Suggestion cooldown
18. Selective forgetting
19. Complete adaptive reset
20. Secret redaction
21. Corrupted JSON recovery
22. Concurrent access/thread safety
23. Learning disable/enable
24. Compact Gemini context
25. Weak inference does not cause premature behavior changes
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
    PersonalWorkflowGraph,
    PreferenceHierarchyResolver,
    WorkflowSequenceEngine,
    redact_secrets,
)


class TestContextualAdaptiveIntelligence(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.insights_file = self.test_dir / "adaptive_insights.json"
        self.engine = AdaptiveIntelligenceEngine(insights_path=self.insights_file)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    # 1. CODING context detection
    def test_coding_context_detection(self):
        ctx = ContextDetector.detect_context("Write python unit tests in VS Code", active_app="Code.exe")
        self.assertEqual(ctx["domain"], "CODING")

    # 2. BROWSING context detection
    def test_browsing_context_detection(self):
        ctx = ContextDetector.detect_context("Search documentation online", recent_tools=["web_search"])
        self.assertEqual(ctx["domain"], "BROWSING")

    # 3. COLLEGE context detection
    def test_college_context_detection(self):
        ctx = ContextDetector.detect_context("Check lecture pdf for homework assignment")
        self.assertEqual(ctx["domain"], "COLLEGE")

    # 4. FILE_MANAGEMENT context detection
    def test_file_management_context_detection(self):
        ctx = ContextDetector.detect_context("Organize downloads directory and copy files", recent_tools=["file_controller"])
        self.assertEqual(ctx["domain"], "FILE_MANAGEMENT")

    # 5. Time bucket detection
    def test_time_bucket_detection(self):
        tb = ContextDetector.get_time_bucket(datetime(2026, 8, 8, 20, 0))  # 8 PM
        self.assertEqual(tb, "EVENING")

        tb_morning = ContextDetector.get_time_bucket(datetime(2026, 8, 8, 9, 30))  # 9:30 AM
        self.assertEqual(tb_morning, "MORNING")

    # 6. Project detection
    def test_project_detection(self):
        ctx = ContextDetector.detect_context("Run tests for JARVIS core", cwd="/Desktop/JARVIS MAIN")
        self.assertEqual(ctx["project"], "JARVIS")

    # 7. Preference priority hierarchy
    def test_preference_priority_hierarchy(self):
        insights = {
            "p1": {"key": "python_editor", "value": "VS Code", "source": "explicit", "confidence": 0.98, "enabled": True}
        }
        val, tier = PreferenceHierarchyResolver.resolve_preference("preference", "python_editor", stored_insights=insights)
        self.assertEqual(val, "VS Code")
        self.assertEqual(tier, "TIER_2_EXPLICIT_STORED")

    # 8. Current instruction override
    def test_current_instruction_override(self):
        insights = {
            "p1": {"key": "python_editor", "value": "VS Code", "source": "explicit", "confidence": 0.98, "enabled": True}
        }
        # Current instruction explicitly asks for PyCharm
        val, tier = PreferenceHierarchyResolver.resolve_preference(
            "preference", "python_editor", current_instruction="Open PyCharm for this task", stored_insights=insights
        )
        self.assertEqual(val, "PyCharm")
        self.assertEqual(tier, "TIER_1_CURRENT_INSTRUCTION")

    # 9. Explicit preference override
    def test_explicit_preference_override(self):
        self.engine.add_or_update_insight("preference", "browser", "Firefox", source="inferred", initial_confidence=0.45)
        # Explicit instruction overrides inferred
        ins = self.engine.add_or_update_insight("preference", "browser", "Chrome", source="explicit")
        self.assertEqual(ins["value"], "Chrome")
        self.assertEqual(ins["source"], "explicit")
        self.assertEqual(ins["confidence"], 0.98)

    # 10. Contextual preference
    def test_contextual_preference(self):
        ctx = {"domain": "COLLEGE", "project": "THESIS"}
        ins = self.engine.add_or_update_insight("preference", "reader", "Acrobat", source="explicit", context=ctx)
        self.assertEqual(ins["context"]["domain"], "COLLEGE")

    # 11. Workflow N-gram learning
    def test_workflow_ngram_learning(self):
        seq = ["VS Code", "Terminal", "Chrome"]
        ctx = {"domain": "CODING", "project": "JARVIS"}
        pat = self.engine.sequence_engine.record_sequence(seq, ctx)
        self.assertIsNotNone(pat)
        self.assertEqual(pat["sequence_key"], "VS Code -> Terminal -> Chrome")

    # 12. Confidence reinforcement
    def test_confidence_reinforcement(self):
        ins1 = self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred", initial_confidence=0.35)
        conf1 = ins1["confidence"]
        ins2 = self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred", initial_confidence=0.35)
        conf2 = ins2["confidence"]
        self.assertGreater(conf2, conf1)

    # 13. Temporal decay
    def test_temporal_decay(self):
        ins = self.engine.add_or_update_insight("preference", "music_player", "VLC", source="inferred", initial_confidence=0.6)
        old_date = (datetime.now() - timedelta(days=20)).isoformat()
        ins["last_seen"] = old_date
        self.engine.save()

        self.engine.apply_decay(days_threshold=14, decay_factor=0.2)
        updated = self.engine.insights_data["insights"][ins["insight_id"]]
        self.assertLess(updated["confidence"], 0.6)

    # 14. Workflow graph
    def test_workflow_graph(self):
        edge = self.engine.workflow_graph.add_or_update_edge("CODING", "python_dev", "VS Code", "JARVIS")
        self.assertEqual(edge["weight"], 0.35)
        edge2 = self.engine.workflow_graph.add_or_update_edge("CODING", "python_dev", "VS Code", "JARVIS")
        self.assertGreater(edge2["weight"], 0.35)

    # 15. Contextual tool routing
    def test_contextual_tool_routing(self):
        self.engine.record_tool_reflex("web_search", {"query": "python specs"}, {"query": "python documentation"})
        suggested = self.engine.suggest_tool_correction("web_search", {"query": "python specs"})
        self.assertEqual(suggested, {"query": "python documentation"})

    # 16. Proactive suggestion
    def test_proactive_suggestion(self):
        seq = ["VS Code", "Terminal", "Chrome"]
        ctx = {"domain": "CODING", "project": "JARVIS"}
        # Reinforce sequence until confidence >= 0.60
        for _ in range(3):
            pat = self.engine.sequence_engine.record_sequence(seq, ctx)

        sug = self.engine.sequence_engine.get_proactive_suggestion("VS Code", ctx)
        self.assertIsNotNone(sug)
        msg, p = sug
        self.assertIn("Terminal", msg)

    # 17. Suggestion cooldown
    def test_suggestion_cooldown(self):
        seq = ["VS Code", "Terminal"]
        ctx = {"domain": "CODING"}
        for _ in range(3):
            self.engine.sequence_engine.record_sequence(seq, ctx)

        # 1st suggestion triggers last_suggested
        sug1 = self.engine.sequence_engine.get_proactive_suggestion("VS Code", ctx)
        self.assertIsNotNone(sug1)

        # Immediate 2nd attempt is blocked by cooldown
        sug2 = self.engine.sequence_engine.get_proactive_suggestion("VS Code", ctx)
        self.assertIsNone(sug2)

    # 18. Selective forgetting
    def test_selective_forgetting(self):
        self.engine.add_or_update_insight("preference", "music_genre", "Lo-Fi", source="explicit")
        self.assertTrue(self.engine.forget_insight("music_genre"))
        self.assertFalse(self.engine.forget_insight("non_existent_key"))

    # 19. Complete adaptive reset
    def test_complete_adaptive_reset(self):
        self.engine.add_or_update_insight("preference", "shell", "PowerShell", source="explicit")
        self.engine.reset_learning()
        self.assertEqual(len(self.engine.insights_data.get("insights", {})), 0)

    # 20. Secret redaction
    def test_secret_redaction(self):
        secret = "sk-1234567890abcdef1234567890"
        redacted = redact_secrets(f"My token is {secret}")
        self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)

    # 21. Corrupted JSON recovery
    def test_corrupted_json_recovery(self):
        self.insights_file.write_text("CORRUPTED {{{ JSON", encoding="utf-8")
        new_engine = AdaptiveIntelligenceEngine(insights_path=self.insights_file)
        self.assertIsNotNone(new_engine.insights_data)
        self.assertIn("insights", new_engine.insights_data)

    # 22. Concurrent access / thread safety
    def test_concurrent_access_thread_safety(self):
        def worker():
            for i in range(10):
                self.engine.add_or_update_insight("preference", f"key_{i}", f"val_{i}")

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertGreater(len(self.engine.insights_data.get("insights", {})), 0)

    # 23. Learning disable / enable
    def test_learning_disable_enable(self):
        self.engine.observe_interaction("Jarvis, stop adaptive learning", "Disabled.")
        self.assertFalse(self.engine.learning_enabled)
        res = self.engine.add_or_update_insight("preference", "lang", "Python")
        self.assertIsNone(res)

        self.engine.observe_interaction("Jarvis, resume adaptive learning", "Resumed.")
        self.assertTrue(self.engine.learning_enabled)

    # 24. Compact Gemini context
    def test_compact_gemini_context(self):
        self.engine.add_or_update_insight("preference", "ide", "VS Code", source="explicit")
        ctx_str = self.engine.get_adaptive_context(query="Python dev task")
        self.assertIn("ADAPTIVE CONTEXT", ctx_str)
        self.assertIn("vs code", ctx_str.lower())

    # 25. Weak inference does not cause premature behavior changes
    def test_weak_inference_no_premature_changes(self):
        # Single low-confidence observation
        ins = self.engine.add_or_update_insight("preference", "browser", "Edge", source="inferred", initial_confidence=0.35)
        # Context generator filters out low confidence (< 0.60)
        ctx_str = self.engine.get_adaptive_context(min_confidence=0.60)
        self.assertNotIn("Edge", ctx_str)


if __name__ == "__main__":
    unittest.main()
