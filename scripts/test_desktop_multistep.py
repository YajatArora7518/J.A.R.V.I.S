# scripts/test_desktop_multistep.py
# Behavior-focused unit and integration tests for Real Desktop Multi-Step Workflows (Phase 4I, 4P, 4Q)

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.task_planner import TaskPlanner, ActionType
from core.command_pipeline import process_user_command, reset_conversation_context
from agent.task_manager import default_task_manager
from core.security import RiskLevel


class TestDesktopMultiStep(unittest.TestCase):

    def setUp(self):
        reset_conversation_context()
        self.planner = TaskPlanner()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        reset_conversation_context()
        self.temp_dir.cleanup()

    def test_01_open_antigravity_and_project(self):
        """Scenario: 'Open Antigravity and open my JARVIS project.' -> Plan, execute, verify."""
        plan = self.planner.create_plan("Open Antigravity and open my JARVIS project.")
        self.assertEqual(len(plan.steps), 5)
        step_types = [s.action_type for s in plan.steps]
        self.assertIn(ActionType.RESOLVE_APP.value, step_types)
        self.assertIn(ActionType.RESOLVE_PROJECT.value, step_types)
        self.assertIn(ActionType.REPORT.value, step_types)

        # Execute with confirmation callback
        executed = self.planner.execute_plan(
            plan,
            confirmation_callback=lambda prompt: True,
            auto_confirm_medium=True
        )
        self.assertEqual(executed.status, "COMPLETED")
        self.assertTrue(executed.steps[0].verification_result.get("verified"))

    def test_02_open_notepad_and_write_notes(self):
        """Scenario: 'Open Notepad and write my notes' -> Safe write & verification."""
        notes_file = os.path.join(self.temp_dir.name, "multi_step_notes.txt")
        plan = self.planner.create_plan("Open Notepad and write my notes: Complete Phase 4 testing")

        # Override path to temp directory for isolated test
        for s in plan.steps:
            if s.action_type == ActionType.SAFE_WRITE_FILE.value:
                s.parameters["path"] = notes_file

        executed = self.planner.execute_plan(
            plan,
            confirmation_callback=lambda prompt: True,
            auto_confirm_medium=True
        )
        self.assertEqual(executed.status, "COMPLETED")
        self.assertTrue(os.path.exists(notes_file))
        with open(notes_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("Phase 4", content)

    def test_03_screen_aware_assistance(self):
        """Scenario: 'What is on my screen?' -> Request-driven vision dispatch."""
        res = process_user_command("What is on my screen?", source="chat")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("action"), "screen_process")
        self.assertTrue(res.get("verified"))

    def test_04_task_management_workflow(self):
        """Scenario: 'Kal assignment submit karna hai' and 'Pending tasks batao'."""
        res_add = process_user_command("Kal assignment submit karna hai", source="chat")
        self.assertTrue(res_add.get("success"))
        self.assertIn("Due tomorrow", res_add.get("message"))

        res_list = process_user_command("Pending tasks batao", source="chat")
        self.assertTrue(res_list.get("success"))
        self.assertIn("pending tasks", res_list.get("message"))

    def test_05_delete_file_security_confirmation_barrier(self):
        """Scenario: 'Delete this file' requires explicit confirmation before execution."""
        target_file = os.path.join(self.temp_dir.name, "critical_delete_target.txt")
        with open(target_file, "w") as f:
            f.write("Important data")

        plan = self.planner.create_plan(f'Delete this file "{target_file}"')

        # 1. User denies confirmation
        denied_exec = self.planner.execute_plan(plan, confirmation_callback=lambda p: False)
        self.assertEqual(denied_exec.status, "DENIED")
        self.assertTrue(os.path.exists(target_file))  # Still exists!

        # 2. User approves confirmation
        approved_exec = self.planner.execute_plan(plan, confirmation_callback=lambda p: True)
        self.assertEqual(approved_exec.status, "COMPLETED")
        self.assertFalse(os.path.exists(target_file))  # Now safely verified deleted!


if __name__ == "__main__":
    unittest.main()
