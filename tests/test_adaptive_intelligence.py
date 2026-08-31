# tests/test_adaptive_intelligence.py
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from memory.adaptive_intelligence import (
    AdaptiveIntelligenceEngine,
    redact_secrets,
)


class TestAdaptiveIntelligence(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.insights_file = self.test_dir / "test_adaptive_insights.json"
        self.engine = AdaptiveIntelligenceEngine(insights_path=self.insights_file)

    def tearDown(self):
        try:
            shutil.rmtree(self.test_dir)
        except Exception:
            pass

    def test_secret_redaction(self):
        raw_text = "My API key is sk-1234567890abcdef1234567890 and card is 4111-2222-3333-4444"
        redacted = redact_secrets(raw_text)
        self.assertNotIn("sk-1234567890abcdef1234567890", redacted)
        self.assertNotIn("4111-2222-3333-4444", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)

    def test_preference_learning_and_reinforcement(self):
        # 1st observation: low initial confidence
        insight1 = self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred", initial_confidence=0.35)
        self.assertIsNotNone(insight1)
        self.assertEqual(insight1["confidence"], 0.35)
        self.assertEqual(insight1["observation_count"], 1)

        # 2nd observation: confidence reinforced
        insight2 = self.engine.add_or_update_insight("preference", "editor", "VS Code", source="inferred", initial_confidence=0.35)
        self.assertGreater(insight2["confidence"], 0.35)
        self.assertEqual(insight2["observation_count"], 2)

    def test_explicit_preference_priority(self):
        # Inferred preference
        self.engine.add_or_update_insight("preference", "browser", "Firefox", source="inferred", initial_confidence=0.4)

        # Explicit preference overrides inferred
        explicit_insight = self.engine.add_or_update_insight("preference", "browser", "Chrome", source="explicit", initial_confidence=0.98)
        self.assertEqual(explicit_insight["value"], "Chrome")
        self.assertEqual(explicit_insight["confidence"], 0.98)
        self.assertEqual(explicit_insight["source"], "explicit")

        # Subsequent inferred variation does NOT override explicit
        inferred_again = self.engine.add_or_update_insight("preference", "browser", "Edge", source="inferred")
        self.assertEqual(inferred_again["value"], "Chrome")
        self.assertEqual(inferred_again["confidence"], 0.98)

    def test_confidence_decay(self):
        # Add inferred insight with old timestamp
        insight = self.engine.add_or_update_insight("preference", "theme", "Dark", source="inferred", initial_confidence=0.6)
        old_date = (datetime.now() - timedelta(days=20)).isoformat()
        insight["last_seen"] = old_date
        self.engine.save()

        # Apply decay
        self.engine.apply_decay(days_threshold=14, decay_factor=0.2)
        updated_insight = self.engine.data["insights"][insight["insight_id"]]
        self.assertLess(updated_insight["confidence"], 0.6)

    def test_tool_reflex_learning(self):
        failed = {"query": "python 3.14 specs"}
        corrected = {"query": "python 3.14 documentation"}

        self.engine.record_tool_reflex("web_search", failed, corrected)
        suggested = self.engine.suggest_tool_correction("web_search", failed)
        self.assertEqual(suggested, corrected)

        # Non-matching args return original
        self.assertEqual(self.engine.suggest_tool_correction("web_search", {"query": "other"}), {"query": "other"})

    def test_atomic_persistence_and_recovery(self):
        self.engine.add_or_update_insight("preference", "os", "Windows 11", source="explicit")
        self.assertTrue(self.insights_file.exists())

        # Corrupt file manually
        self.insights_file.write_text("MALFORMED JSON {{{", encoding="utf-8")

        # Re-instantiate engine: must recover cleanly without crash
        new_engine = AdaptiveIntelligenceEngine(insights_path=self.insights_file)
        self.assertIsNotNone(new_engine.data)
        self.assertIn("insights", new_engine.data)

    def test_disable_enable_and_reset(self):
        self.engine.add_or_update_insight("preference", "voice", "Jarvis", source="explicit")
        self.assertGreater(len(self.engine.data["insights"]), 0)

        # Handle disable voice command
        self.engine.observe_interaction("Jarvis, stop adaptive learning", "Understood.")
        self.assertFalse(self.engine.learning_enabled)

        # When disabled, new insights are ignored
        ret = self.engine.add_or_update_insight("preference", "lang", "English")
        self.assertIsNone(ret)

        # Handle reset command
        self.engine.observe_interaction("Jarvis, reset adaptive intelligence", "Resetting.")
        self.assertEqual(len(self.engine.data["insights"]), 0)
        self.assertTrue(self.engine.learning_enabled)

    def test_context_limiting(self):
        # Add 10 insights
        for i in range(10):
            self.engine.add_or_update_insight("preference", f"pref_{i}", f"val_{i}", source="explicit")

        context = self.engine.get_adaptive_context(max_insights=3)
        lines = context.strip().split("\n")
        # Header + 3 lines max
        self.assertLessEqual(len(lines), 4)

    def test_fail_safe_isolation(self):
        # Engine should swallow internal attribute errors gracefully
        self.engine.session_active = False
        res = self.engine.add_or_update_insight("test", "a", "b")
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
