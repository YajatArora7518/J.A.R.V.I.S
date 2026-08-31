# tests/test_proactive_companion.py
"""
Comprehensive Unit Test Suite for JARVIS Proactive Personal AI Companion.
Verifies camera, screen, context engine, proactive engine, permissions, privacy mode, anti-spam, provider statuses, and security integration.
"""

import unittest
import time
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.camera_provider import camera_provider
from agent.awareness.screen_provider import screen_provider
from agent.awareness.whatsapp_provider import whatsapp_provider
from agent.awareness.email_provider import email_provider
from agent.awareness.calendar_provider import calendar_provider
from agent.awareness.instagram_provider import instagram_provider
from agent.context_engine import context_engine, unified_analyzer
from agent.proactive_engine import proactive_decision_engine
from agent.ambient_orchestrator import ambient_orchestrator


class TestProactiveCompanion(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.set_privacy_mode(False)
        privacy_mode_manager.pause_all_awareness(False)
        permission_manager.set_permission("CAMERA_ACCESS", False)
        permission_manager.set_permission("SCREEN_ACCESS", False)
        permission_manager.set_permission("PROACTIVE_MODE", True)
        permission_manager.set_permission("COMPANION_MODE", False)
        camera_provider.disable()
        screen_provider.disable()

    def test_permission_manager(self):
        self.assertFalse(permission_manager.is_granted("CAMERA_ACCESS"))
        permission_manager.set_permission("CAMERA_ACCESS", True)
        self.assertTrue(permission_manager.is_granted("CAMERA_ACCESS"))

    def test_privacy_mode_manager(self):
        self.assertFalse(privacy_mode_manager.is_privacy_mode_active())
        privacy_mode_manager.set_privacy_mode(True)
        self.assertTrue(privacy_mode_manager.is_privacy_mode_active())

    def test_camera_provider_disabled_and_unavailable(self):
        # Default OFF
        self.assertFalse(camera_provider.is_camera_active())
        res = camera_provider.sample_context()
        self.assertEqual(res["status"], "CAMERA_UNAVAILABLE")

    def test_camera_provider_enable(self):
        permission_manager.set_permission("CAMERA_ACCESS", True)
        self.assertTrue(camera_provider.enable())
        self.assertTrue(camera_provider.is_camera_active())
        res = camera_provider.sample_context()
        self.assertEqual(res["status"], "OK")
        camera_provider.disable()
        self.assertFalse(camera_provider.is_camera_active())

    def test_screen_provider_classification(self):
        self.assertFalse(screen_provider.is_enabled())
        permission_manager.set_permission("SCREEN_ACCESS", True)
        self.assertTrue(screen_provider.enable())
        res = screen_provider.classify_context()
        self.assertEqual(res["status"], "OK")
        self.assertIn("category", res)
        screen_provider.disable()

    def test_provider_unavailable_fallback_statuses(self):
        wa = whatsapp_provider.check_unread()
        em = email_provider.check_inbox()
        cal = calendar_provider.check_events()
        insta = instagram_provider.check_activity()

        self.assertIn(wa["status"], ["OK", "WHATSAPP_UNAVAILABLE"])
        self.assertEqual(em["status"], "EMAIL_UNAVAILABLE")
        self.assertEqual(cal["status"], "CALENDAR_UNAVAILABLE")
        self.assertEqual(insta["status"], "INSTAGRAM_UNAVAILABLE")

    def test_context_engine_normalization(self):
        ctx = context_engine.get_current_context()
        self.assertIn("timestamp", ctx)
        self.assertIn("activity", ctx)
        self.assertIn("provider_statuses", ctx)

    def test_unified_context_analyzer(self):
        ctx = context_engine.get_current_context()
        summary = unified_analyzer.summarize(ctx)
        self.assertIsInstance(summary, str)

    def test_proactive_engine_interruption_prevention(self):
        # Speaking -> Should not speak
        proactive_decision_engine.set_system_state(is_speaking=True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

        # Executing command -> Should not speak
        proactive_decision_engine.set_system_state(is_speaking=False, is_command_executing=True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

        # Privacy active -> Should not speak
        proactive_decision_engine.set_system_state(is_speaking=False, is_command_executing=False)
        privacy_mode_manager.set_privacy_mode(True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

    def test_proactive_engine_cooldown_and_deduplication(self):
        proactive_decision_engine.set_system_state(is_speaking=False, is_command_executing=False, is_user_busy=False)
        proactive_decision_engine.last_proactive_timestamp = time.time() - 360  # expired cooldown
        proactive_decision_engine.preferred_sleep_time = time.strftime("%H:%M")  # trigger sleep reminder

        res = proactive_decision_engine.evaluate_proactive_speech()
        if res:
            self.assertEqual(res["type"], "SLEEP_REMINDER")
            # Immediate subsequent evaluation should hit cooldown
            res2 = proactive_decision_engine.evaluate_proactive_speech()
            self.assertIsNone(res2)

    def test_ambient_orchestrator_lifecycle(self):
        ambient_orchestrator.start()
        self.assertTrue(ambient_orchestrator._running)
        ambient_orchestrator.stop()
        self.assertFalse(ambient_orchestrator._running)


if __name__ == "__main__":
    unittest.main()
