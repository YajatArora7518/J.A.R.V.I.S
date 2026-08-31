# tests/test_daily_use_readiness.py
"""
Comprehensive Unit Test Suite for Daily-Use Readiness.
"""

import unittest
from unittest.mock import patch, MagicMock

from actions.chrome_profile import get_chrome_executable, resolve_chrome_profile, is_chrome_running
from actions.browser_automation import is_cdp_active, browser_automation_engine
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
from core.intent_router import classify_intent


class TestDailyUseReadiness(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.resume_awareness()
        permission_manager.set_permission("CAMERA_ACCESS", True)
        permission_manager.set_permission("SCREEN_ACCESS", True)
        permission_manager.set_permission("WHATSAPP_READ", True)
        permission_manager.set_permission("EMAIL_READ", True)
        permission_manager.set_permission("CALENDAR_READ", True)
        permission_manager.set_permission("INSTAGRAM_READ", True)

    def test_single_state_provider_reporting(self):
        """Verify status_registry produces exact single state labels."""
        summary = status_registry.get_summary_string()
        self.assertIn("CAM", summary)
        self.assertIn("WA", summary)
        self.assertNotIn("/", summary)

    def test_hinglish_and_english_intent_classification(self):
        """Verify natural Hinglish & English voice queries map cleanly to intents."""
        def _get_intent(cmd: str) -> str:
            res = classify_intent(cmd)
            return res.get("primary", str(res)) if isinstance(res, dict) else str(res)

        self.assertEqual(_get_intent("Jarvis, time kya hua hai?"), "GENERAL_QUERY")
        self.assertEqual(_get_intent("Mera Gmail check karo."), "EMAIL_READ")
        self.assertEqual(_get_intent("Mera next meeting kab hai?"), "CALENDAR_READ")
        self.assertEqual(_get_intent("WhatsApp check karo."), "WHATSAPP_READ")
        self.assertEqual(_get_intent("Calculator kholo."), "APP_LAUNCH")

    def test_privacy_mode_absolute_suppression(self):
        """Verify Privacy Mode suppresses all awareness contexts."""
        privacy_mode_manager.enable_privacy_mode()
        ctx = context_engine.get_current_context()
        self.assertEqual(ctx.get("activity"), "PRIVACY_MODE_ACTIVE")
        self.assertIsNone(proactive_engine.evaluate_proactive_speech(ctx))

        privacy_mode_manager.resume_awareness()
        ctx_res = context_engine.get_current_context()
        self.assertNotEqual(ctx_res.get("activity"), "PRIVACY_MODE_ACTIVE")


if __name__ == "__main__":
    unittest.main()
