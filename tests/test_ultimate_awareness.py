# tests/test_ultimate_awareness.py
"""
Comprehensive Test Suite for Ultimate Proactive Personal AI Awareness & Companion System.
"""

import unittest
from unittest.mock import patch, MagicMock

from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.camera_provider import camera_provider
from agent.awareness.screen_provider import screen_provider
from agent.awareness.email_provider import email_provider
from agent.awareness.calendar_provider import calendar_provider
from agent.awareness.instagram_provider import instagram_provider
from agent.awareness.whatsapp_provider import whatsapp_provider
from agent.awareness.status_model import status_registry, ProviderState
from agent.context_engine import context_engine
from agent.proactive_engine import proactive_engine


class TestUltimateAwareness(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.resume_awareness()
        permission_manager.set_permission("CAMERA_ACCESS", True)
        permission_manager.set_permission("SCREEN_ACCESS", True)
        permission_manager.set_permission("WHATSAPP_READ", True)
        permission_manager.set_permission("EMAIL_READ", True)
        permission_manager.set_permission("CALENDAR_READ", True)
        permission_manager.set_permission("INSTAGRAM_READ", True)
        permission_manager.set_permission("PROACTIVE_MODE", True)

        camera_provider.enable()
        screen_provider.enable()

    def test_provider_status_registry(self):
        """Verify ProviderStatus registry operates as the single authoritative source of truth."""
        status_registry.update_status("camera", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
        status_registry.update_status("whatsapp", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
        summary = status_registry.get_summary_string()
        self.assertIn("CAM", summary)
        self.assertIn("WA", summary)

    def test_proactive_priority_scoring(self):
        """Verify priority scoring ranks events from 10 to 100 correctly."""
        self.assertEqual(proactive_engine.score_event("CRITICAL_SECURITY_ALERT"), 100)
        self.assertEqual(proactive_engine.score_event("CALENDAR_UPCOMING_5MIN"), 90)
        self.assertEqual(proactive_engine.score_event("IMPORTANT_WHATSAPP"), 80)
        self.assertEqual(proactive_engine.score_event("IMPORTANT_EMAIL"), 70)
        self.assertEqual(proactive_engine.score_event("CASUAL_COMPANION"), 15)

    def test_interruption_prechecks(self):
        """Verify proactive engine suppresses speech when user or JARVIS is speaking."""
        proactive_engine.set_system_state(is_user_speaking=True)
        eval_res = proactive_engine.evaluate_proactive_speech()
        self.assertIsNone(eval_res)

        proactive_engine.set_system_state(is_user_speaking=False, is_speaking=True)
        eval_res_jarvis = proactive_engine.evaluate_proactive_speech()
        self.assertIsNone(eval_res_jarvis)

        proactive_engine.set_system_state(is_speaking=False)

    def test_privacy_mode_isolation(self):
        """Verify Privacy Mode instantly pauses all awareness feeds and proactive alerts."""
        privacy_mode_manager.enable_privacy_mode()
        ctx = context_engine.get_current_context()
        self.assertEqual(ctx.get("activity"), "PRIVACY_MODE_ACTIVE")
        self.assertIsNone(proactive_engine.evaluate_proactive_speech())
        privacy_mode_manager.resume_awareness()

    def test_context_engine_fields(self):
        """Verify ContextEngine compiles complete ContextObject data fields."""
        ctx = context_engine.get_current_context()
        self.assertIn("gmail_context", ctx)
        self.assertIn("calendar_context", ctx)
        self.assertIn("instagram_context", ctx)
        self.assertIn("whatsapp_context", ctx)
        self.assertIn("screen_context", ctx)
        self.assertIn("camera_context", ctx)


if __name__ == "__main__":
    unittest.main()
