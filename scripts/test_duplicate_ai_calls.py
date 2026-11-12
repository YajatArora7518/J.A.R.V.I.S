# scripts/test_duplicate_ai_calls.py
# Verification Test for Detecting and Preventing Duplicate AI Requests
# Ensures that user commands trigger only necessary AI calls and zero redundant requests.

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.command_pipeline import process_user_command
from core.ai_multitier_engine import get_ai_engine


class TestDuplicateAICalls(unittest.TestCase):

    def setUp(self):
        self.ai_engine = get_ai_engine()

    def test_deterministic_commands_trigger_zero_ai_calls(self):
        """Deterministic commands (app open, calculator, settings, etc.) must NEVER invoke AI Brain."""
        deterministic_queries = [
            "Open Notepad",
            "Open Calculator",
            "Volume badhao",
            "Calculate 100 * 5 + 20",
            "Jarvis status",
            "Chup"
        ]

        with patch.object(self.ai_engine, 'generate_response') as mock_ai:
            for cmd in deterministic_queries:
                mock_ai.reset_mock()
                res = process_user_command(cmd, source="voice")
                self.assertTrue(res.get("success", False), f"Command '{cmd}' failed.")
                self.assertEqual(
                    mock_ai.call_count, 0,
                    f"Deterministic command '{cmd}' triggered {mock_ai.call_count} unexpected AI Brain calls!"
                )

    def test_conversational_query_triggers_single_ai_call(self):
        """Conversational query should trigger exactly ONE AI call, never duplicate or retry unnecessarily."""
        query = "Explain the difference between RAM and ROM in one sentence."

        with patch.object(self.ai_engine, 'generate_response', return_value={
            "success": True, "text": "RAM is volatile high-speed memory while ROM is non-volatile permanent storage.", "tier": "TIER_1_OLLAMA"
        }) as mock_ai:
            res = process_user_command(query, source="voice")
            self.assertTrue(res.get("success", False))
            self.assertEqual(
                mock_ai.call_count, 1,
                f"Conversational query triggered {mock_ai.call_count} AI calls instead of exactly 1!"
            )

    def test_screen_analysis_does_not_trigger_text_ai_brain(self):
        """Screen query must use screen vision pipeline, not invoke conversational text AI Brain."""
        query = "What is on my screen?"

        with patch.object(self.ai_engine, 'generate_response') as mock_ai:
            with patch("actions.screen_processor.analyze_screen_vision", return_value={
                "success": True, "active_window": "VS Code", "observation": "Code editor visible.", "message": "Code editor visible."
            }) as mock_vision:
                res = process_user_command(query, source="voice")
                self.assertTrue(res.get("success", False))
                self.assertEqual(mock_vision.call_count, 1, "Vision pipeline should be called once.")
                self.assertEqual(mock_ai.call_count, 0, "Text AI Brain should NOT be called on screen query.")

    def test_multi_step_planner_does_not_call_conversational_ai_redundantly(self):
        """Multi-step planner executes structured tool tasks without redundant conversational AI calls."""
        cmd = "Open Notepad and write my daily notes"

        with patch.object(self.ai_engine, 'generate_response') as mock_ai:
            with patch("agent.task_planner.TaskPlanner.create_plan") as mock_plan:
                mock_plan_obj = MagicMock()
                mock_plan_obj.steps = [MagicMock()]
                mock_plan_obj.status = "PLANNED"
                mock_plan.return_value = mock_plan_obj

                with patch("agent.task_planner.TaskPlanner.execute_plan") as mock_exec:
                    mock_exec_obj = MagicMock()
                    mock_exec_obj.status = "COMPLETED"
                    mock_exec_obj.summary = "Completed all steps."
                    mock_exec_obj.error = None
                    mock_exec_obj.to_dict.return_value = {"status": "COMPLETED"}
                    mock_exec.return_value = mock_exec_obj

                    res = process_user_command(cmd, source="voice")
                    self.assertTrue(res.get("success", False))
                    self.assertEqual(mock_ai.call_count, 0, "Task planner should not trigger conversational fallback AI.")


def run_duplicate_ai_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDuplicateAICalls)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_duplicate_ai_test()
    sys.exit(0 if success else 1)
