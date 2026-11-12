# scripts/test_task_manager.py
# Behavior-focused unit and integration tests for Unified Task Manager (Phase 4E)

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.task_manager import UnifiedTaskManager, TaskItem


class TestTaskManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_dir.name) / "test_tasks.json"
        self.tm = UnifiedTaskManager(store_path=self.store_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_add_task_and_attributes(self):
        """Verify task creation with full structured attributes."""
        task, is_new = self.tm.add_task(
            title="Prepare AI presentation",
            description="Slides on multi-agent systems",
            category="project",
            priority="HIGH",
            due_at="2026-09-15 14:00",
            project_or_subject="JARVIS"
        )
        self.assertTrue(is_new)
        self.assertEqual(task.title, "Prepare AI presentation")
        self.assertEqual(task.priority, "HIGH")
        self.assertEqual(task.status, "PENDING")
        self.assertEqual(task.project_or_subject, "JARVIS")
        self.assertIsNotNone(task.created_at)

    def test_02_deduplication_prevention(self):
        """Verify adding near-identical tasks updates existing without creating duplicates."""
        task1, is_new1 = self.tm.add_task("Submit Machine Learning assignment", due_at="2026-09-12")
        self.assertTrue(is_new1)

        # Attempt duplicate insertion
        task2, is_new2 = self.tm.add_task("Submit Machine Learning assignment", priority="CRITICAL")
        self.assertFalse(is_new2)
        self.assertEqual(task1.id, task2.id)
        self.assertEqual(task2.priority, "CRITICAL")

        all_pending = self.tm.get_pending_tasks()
        # Count matching tasks
        ml_tasks = [t for t in all_pending if "Machine Learning" in t.title]
        self.assertEqual(len(ml_tasks), 1)

    def test_03_priority_sorting(self):
        """Verify tasks sort by priority (CRITICAL > HIGH > MEDIUM > LOW)."""
        self.tm.add_task("Low priority cleanup", priority="LOW")
        self.tm.add_task("Critical bug fix", priority="CRITICAL")
        self.tm.add_task("Medium documentation", priority="MEDIUM")
        self.tm.add_task("High deadline task", priority="HIGH")

        pending = self.tm.get_pending_tasks()
        priorities = [t.priority for t in pending]
        self.assertEqual(priorities[0], "CRITICAL")
        self.assertEqual(priorities[1], "HIGH")

    def test_04_natural_language_hinglish_commands(self):
        """Verify natural Hinglish command processing."""
        # 1. "Kal assignment submit karna hai"
        res1 = self.tm.handle_natural_command("Kal assignment submit karna hai")
        self.assertIn("Due tomorrow", res1)

        # 2. "Pending tasks batao"
        res2 = self.tm.handle_natural_command("Pending tasks batao")
        self.assertIn("pending tasks", res2)

        # 3. "Sabse important kya hai?"
        res3 = self.tm.handle_natural_command("Sabse important kya hai?")
        self.assertIn("important task hai", res3)

        # 4. "Is task ko complete mark karo"
        res4 = self.tm.handle_natural_command("Is task ko complete mark karo")
        self.assertIn("completed mark kar diya", res4)


if __name__ == "__main__":
    unittest.main()
