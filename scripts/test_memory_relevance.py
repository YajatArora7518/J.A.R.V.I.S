# scripts/test_memory_relevance.py
# Behavior-focused unit and integration tests for Memory Relevance & Corrections (Phase 4D)

import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from memory.memory_manager import (
    retrieve_relevant_memories,
    handle_memory_correction,
    update_memory,
    load_memory,
    save_memory
)


class TestMemoryRelevance(unittest.TestCase):

    def setUp(self):
        # Backup existing memory
        self.original_memory = load_memory()

        # Seed known test memories
        test_seed = {
            "identity": {
                "user_name": {"value": "Yajat", "confidence": 1.0, "source": "user_explicit", "updated": "2026-09-01"},
            },
            "preferences": {
                "favorite_editor": {"value": "Antigravity", "confidence": 1.0, "source": "user_explicit", "updated": "2026-09-02"},
                "favorite_drink": {"value": "Cold Coffee", "confidence": 0.9, "source": "user_explicit", "updated": "2026-08-15"},
                "inferred_food": {"value": "Pizza", "confidence": 0.6, "source": "inferred", "updated": "2026-07-10"}
            },
            "projects": {
                "jarvis": {"value": "Advanced AI Assistant", "confidence": 1.0, "source": "user_explicit", "updated": "2026-09-05"}
            },
            "notes": {
                "temp_reminder_note": {"value": "Meeting tomorrow at 10", "confidence": 1.0, "source": "user_explicit", "updated": "2026-09-06"}
            }
        }
        save_memory(test_seed)

    def tearDown(self):
        # Restore original memory
        save_memory(self.original_memory)

    def test_01_retrieve_relevant_memories_ranking(self):
        """Verify ranking prioritizes semantic match and explicit user source over inferred."""
        results = retrieve_relevant_memories("Which editor do I like?", limit=3)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertEqual(top["key"], "favorite_editor")
        self.assertEqual(top["value"], "Antigravity")
        self.assertEqual(top["source"], "user_explicit")
        # Ensure schema compatibility with entry['value']
        self.assertIn("value", top)

    def test_02_explicit_source_outranks_inferred(self):
        """Verify explicit user source scores higher than inferred source on matching queries."""
        results = retrieve_relevant_memories("food and drink preferences", limit=5)
        keys = [r["key"] for r in results]
        self.assertIn("favorite_drink", keys)
        self.assertIn("inferred_food", keys)

        drink_score = next(r["score"] for r in results if r["key"] == "favorite_drink")
        food_score = next(r["score"] for r in results if r["key"] == "inferred_food")
        self.assertGreater(drink_score, food_score)

    def test_03_correction_removes_only_target_preference(self):
        """Verify 'Nahi, ye preference galat hai' removes target without deleting unrelated memories."""
        correction_res = handle_memory_correction("Nahi, ye favorite_editor preference galat hai.")
        self.assertIsNotNone(correction_res)
        self.assertEqual(correction_res.get("action"), "deleted_preference")

        current_mem = load_memory()
        # Target preference must be deleted
        self.assertNotIn("favorite_editor", current_mem.get("preferences", {}))

        # Unrelated memories MUST be completely intact!
        self.assertIn("favorite_drink", current_mem.get("preferences", {}))
        self.assertIn("user_name", current_mem.get("identity", {}))
        self.assertIn("jarvis", current_mem.get("projects", {}))

    def test_04_correction_dont_remember(self):
        """Verify 'Ye yaad mat rakh' removes target note cleanly."""
        res = handle_memory_correction("Ye yaad mat rakh: temp_reminder_note")
        self.assertIsNotNone(res)

        current_mem = load_memory()
        self.assertNotIn("temp_reminder_note", current_mem.get("notes", {}))
        # Identity and project still preserved
        self.assertIn("user_name", current_mem.get("identity", {}))


if __name__ == "__main__":
    unittest.main()
