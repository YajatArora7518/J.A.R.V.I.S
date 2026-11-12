# scripts/test_proactive_assistant.py
# Behavior-focused unit and integration tests for Proactive Assistant (Phase 4F)

import time
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.proactive_engine import ProactiveDecisionEngine


class TestProactiveAssistant(unittest.TestCase):

    def setUp(self):
        self.engine = ProactiveDecisionEngine()
        self.engine.proactive_enabled = True
        self.engine.global_cooldown_seconds = 0  # Zero for focused test evaluations

    def test_01_quiet_hours_suppresses_normal_speech(self):
        """Verify normal spoken notifications are suppressed during quiet hours (11 PM - 7 AM)."""
        # Test at 2 AM (quiet hour)
        self.assertTrue(self.engine.is_in_quiet_hours(hour=2))
        self.assertTrue(self.engine.is_in_quiet_hours(hour=23))
        self.assertFalse(self.engine.is_in_quiet_hours(hour=14))

        ctx = {
            "explicit_event": {
                "type": "NORMAL_REMINDER",
                "priority": "MEDIUM",
                "message": "Routine notification",
                "urgent": False
            }
        }
        res_quiet = self.engine.evaluate_proactive_speech(context=ctx, current_hour=2)
        self.assertIsNone(res_quiet)  # Suppressed during quiet hours!

    def test_02_urgent_notification_bypasses_quiet_hours(self):
        """Verify URGENT/CRITICAL notifications bypass quiet hours."""
        ctx_urgent = {
            "explicit_event": {
                "type": "CRITICAL_SECURITY_ALERT",
                "priority": "CRITICAL",
                "message": "Critical security breach detected!",
                "urgent": True
            }
        }
        res_urgent = self.engine.evaluate_proactive_speech(context=ctx_urgent, current_hour=3)
        self.assertIsNotNone(res_urgent)
        self.assertTrue(res_urgent.get("should_interrupt"))
        self.assertIn("Critical security", res_urgent.get("message"))

    def test_03_antispam_deduplication(self):
        """Verify identical notification is never repeatedly spoken."""
        ctx = {
            "explicit_event": {
                "type": "CLASS_REMINDER",
                "priority": "HIGH",
                "message": "Machine Learning lecture in Room 204",
                "urgent": False
            }
        }
        # First delivery at 10 AM
        res1 = self.engine.evaluate_proactive_speech(context=ctx, current_hour=10)
        self.assertIsNotNone(res1)

        # Immediate second delivery of identical message
        res2 = self.engine.evaluate_proactive_speech(context=ctx, current_hour=10)
        self.assertIsNone(res2)  # Deduplicated and suppressed!

    def test_04_active_user_gating(self):
        """Verify assistant does not interrupt while user is speaking or command is executing."""
        ctx = {
            "explicit_event": {
                "type": "TASK_ALERT",
                "priority": "HIGH",
                "message": "Project deadline approaching",
                "urgent": False
            }
        }
        # User is speaking
        self.engine.set_system_state(is_user_speaking=True)
        res = self.engine.evaluate_proactive_speech(context=ctx, current_hour=15)
        self.assertIsNone(res)

        # Command is executing
        self.engine.set_system_state(is_user_speaking=False, is_command_executing=True)
        res_cmd = self.engine.evaluate_proactive_speech(context=ctx, current_hour=15)
        self.assertIsNone(res_cmd)

        # Clear active state -> now permitted
        self.engine.set_system_state(is_command_executing=False)
        res_ok = self.engine.evaluate_proactive_speech(context=ctx, current_hour=15)
        self.assertIsNotNone(res_ok)


if __name__ == "__main__":
    unittest.main()
