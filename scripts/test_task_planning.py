# scripts/test_task_planning.py
# Behavior-focused unit and integration tests for Task Planner (Phase 4A)

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.task_planner import TaskPlanner, PlanStep, ExecutionPlan, ActionType
from core.security import RiskLevel, SecurityManager


class TestTaskPlanning(unittest.TestCase):

    def setUp(self):
        self.planner = TaskPlanner()

    def test_01_complex_antigravity_instruction(self):
        """Verify the exact canonical multi-step instruction breaks into structured typed plan."""
        instruction = "Antigravity kholo, mera JARVIS project open karo aur build error check karo."
        plan = self.planner.create_plan(instruction)

        self.assertIsInstance(plan, ExecutionPlan)
        self.assertEqual(len(plan.steps), 7)
        self.assertEqual(plan.status, "PENDING")

        expected_types = [
            ActionType.RESOLVE_APP.value,
            ActionType.LAUNCH_APP.value,
            ActionType.VERIFY_WINDOW.value,
            ActionType.RESOLVE_PROJECT.value,
            ActionType.INSPECT_PROJECT.value,
            ActionType.ANALYZE_ERROR.value,
            ActionType.REPORT.value
        ]

        for idx, step in enumerate(plan.steps):
            self.assertEqual(step.step_number, idx + 1)
            self.assertEqual(step.action_type, expected_types[idx])
            self.assertIn("status", step.to_dict())
            self.assertEqual(step.status, "PENDING")

        # Step 2 (LAUNCH_APP) must be classified as MEDIUM risk and require confirmation
        launch_step = plan.steps[1]
        self.assertEqual(launch_step.risk_level, RiskLevel.MEDIUM)
        self.assertTrue(launch_step.requires_confirmation)

    def test_02_notepad_write_plan(self):
        """Verify 'Open Notepad and write my notes' workflow."""
        instruction = "Open Notepad and write my notes: finalize presentation"
        plan = self.planner.create_plan(instruction)

        types = [s.action_type for s in plan.steps]
        self.assertIn(ActionType.RESOLVE_APP.value, types)
        self.assertIn(ActionType.LAUNCH_APP.value, types)
        self.assertIn(ActionType.SAFE_WRITE_FILE.value, types)
        self.assertIn(ActionType.REPORT.value, types)

        write_step = next(s for s in plan.steps if s.action_type == ActionType.SAFE_WRITE_FILE.value)
        self.assertEqual(write_step.risk_level, RiskLevel.MEDIUM)
        self.assertTrue(write_step.requires_confirmation)

    def test_03_delete_file_security_boundary(self):
        """Verify file deletion is classified as HIGH risk requiring confirmation."""
        instruction = 'Delete this file "obsolete_temp.txt"'
        plan = self.planner.create_plan(instruction)

        delete_step = next(s for s in plan.steps if s.action_type == ActionType.SAFE_DELETE_FILE.value)
        self.assertEqual(delete_step.risk_level, RiskLevel.HIGH)
        self.assertTrue(delete_step.requires_confirmation)

    def test_04_security_authority_invariance(self):
        """Verify the planner CANNOT downgrade risk or bypass SecurityManager."""
        sec_mgr = SecurityManager()
        custom_planner = TaskPlanner(security_manager=sec_mgr)

        step = PlanStep(
            step_number=1,
            action_type=ActionType.SAFE_DELETE_FILE.value,
            description="Try to delete file",
            parameters={"path": "C:\\Windows\\System32\\critical.dll"}
        )

        risk, req_conf = custom_planner.classify_step_risk(step)
        self.assertEqual(risk, RiskLevel.HIGH)
        self.assertTrue(req_conf)

        # Plan execution must immediately reject protected system path
        plan = ExecutionPlan(plan_id="sec_test", goal="test", steps=[step])
        executed_plan = custom_planner.execute_plan(plan, auto_confirm_medium=True)
        self.assertEqual(executed_plan.status, "DENIED")
        self.assertIn("strictly forbidden", executed_plan.error)


if __name__ == "__main__":
    unittest.main()
