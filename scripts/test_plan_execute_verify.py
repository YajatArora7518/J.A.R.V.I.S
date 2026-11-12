# scripts/test_plan_execute_verify.py
# Behavior-focused unit and integration tests for Plan-Execute-Verify Loop (Phase 4B)

import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.task_planner import TaskPlanner, PlanStep, ExecutionPlan, ActionType
from core.security import RiskLevel, SecurityManager


class TestPlanExecuteVerify(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.planner = TaskPlanner()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_user_rejection_halts_plan_immediately(self):
        """Verify when user rejects confirmation for MEDIUM/HIGH step, execution stops immediately."""
        test_file = os.path.join(self.temp_dir.name, "target.txt")
        with open(test_file, "w") as f:
            f.write("content")

        step1 = PlanStep(
            step_number=1,
            action_type=ActionType.SAFE_DELETE_FILE.value,
            description="Delete target test file",
            parameters={"path": test_file}
        )
        step2 = PlanStep(
            step_number=2,
            action_type=ActionType.REPORT.value,
            description="Final Report",
            parameters={"summary": "File deleted"}
        )

        plan = ExecutionPlan(plan_id="reject_test", goal="Delete file", steps=[step1, step2])

        # Confirmation callback explicitly returns False (user denied confirmation)
        rejection_callback = lambda prompt: False

        executed = self.planner.execute_plan(plan, confirmation_callback=rejection_callback)

        self.assertEqual(executed.status, "DENIED")
        self.assertEqual(executed.steps[0].status, "DENIED")
        self.assertEqual(executed.steps[1].status, "PENDING")  # Step 2 never ran!
        self.assertTrue(os.path.exists(test_file))  # File was NOT deleted

    def test_02_verification_failure_halts_plan(self):
        """Verify if step verification fails, execution stops immediately and reports failure."""
        non_existent_app = "NonExistentApp99999XYZ"
        step1 = PlanStep(
            step_number=1,
            action_type=ActionType.VERIFY_WINDOW.value,
            description=f"Verify window for non-running app {non_existent_app}",
            parameters={"app_name": non_existent_app}
        )
        step2 = PlanStep(
            step_number=2,
            action_type=ActionType.REPORT.value,
            description="Should not execute",
            parameters={"summary": "Done"}
        )

        plan = ExecutionPlan(plan_id="verif_fail_test", goal="Run unknown app", steps=[step1, step2])

        # Approval callback
        approval_callback = lambda prompt: True

        executed = self.planner.execute_plan(plan, confirmation_callback=approval_callback)

        self.assertEqual(executed.status, "FAILED")
        self.assertEqual(executed.steps[0].status, "FAILED")
        self.assertEqual(executed.steps[1].status, "PENDING")  # Step 2 never ran
        self.assertIsNotNone(executed.steps[0].failure_info)

    def test_03_successful_safe_write_delete_verification_loop(self):
        """Verify safe write, verification, safe delete, and post-delete verification."""
        test_file = os.path.join(self.temp_dir.name, "loop_test.txt")

        step1 = PlanStep(
            step_number=1,
            action_type=ActionType.SAFE_WRITE_FILE.value,
            description="Write test file",
            parameters={"path": test_file, "content": "J.A.R.V.I.S Verification Engine Test"}
        )
        step2 = PlanStep(
            step_number=2,
            action_type=ActionType.SAFE_DELETE_FILE.value,
            description="Delete test file",
            parameters={"path": test_file}
        )
        step3 = PlanStep(
            step_number=3,
            action_type=ActionType.REPORT.value,
            description="Report success",
            parameters={"summary": "Write and delete verified"}
        )

        plan = ExecutionPlan(plan_id="full_loop_test", goal="Safe lifecycle", steps=[step1, step2, step3])

        spoken_messages = []
        speak_cb = lambda msg: spoken_messages.append(msg)
        approval_cb = lambda prompt: True

        executed = self.planner.execute_plan(
            plan,
            confirmation_callback=approval_cb,
            speak=speak_cb,
            auto_confirm_medium=True
        )

        self.assertEqual(executed.status, "COMPLETED")
        self.assertEqual(executed.steps[0].status, "VERIFIED")
        self.assertEqual(executed.steps[1].status, "VERIFIED")
        self.assertEqual(executed.steps[2].status, "VERIFIED")

        # Verify post-condition: file is genuinely deleted
        self.assertFalse(os.path.exists(test_file))

        # Verify spoken acknowledgement happened
        self.assertTrue(any("boss" in msg.lower() or "check" in msg.lower() for msg in spoken_messages))


if __name__ == "__main__":
    unittest.main()
