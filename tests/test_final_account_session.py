# tests/test_final_account_session.py
"""
Comprehensive Unit Test Suite for Final Real Account Session Verification & Production Hardening.
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


class TestFinalAccountSession(unittest.TestCase):

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

    def test_chrome_and_profile_discovery(self):
        """Verify dynamic discovery of Chrome executable and Yajat profile."""
        chrome_bin = get_chrome_executable()
        self.assertIsNotNone(chrome_bin)

        prof_info = resolve_chrome_profile("Yajat")
        self.assertTrue(prof_info.get("verified"))

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_gmail_authentication_detection(self, mock_auth, mock_cdp):
        """Verify single-state ProviderState reporting for Gmail."""
        # Authenticated state
        mock_auth.return_value = {"status": "LIVE_VERIFIED", "authenticated": True, "message": "Gmail active."}
        res_live = email_provider.check_inbox()
        self.assertEqual(res_live["status"], "OK")
        self.assertEqual(status_registry.get_status("email").state, ProviderState.LIVE_VERIFIED)

        # Unauthenticated / Login required state
        mock_auth.return_value = {"status": "AUTHENTICATION_REQUIRED", "authenticated": False, "message": "Login required."}
        res_auth = email_provider.check_inbox()
        self.assertEqual(res_auth["status"], "EMAIL_UNAVAILABLE")
        self.assertEqual(status_registry.get_status("email").state, ProviderState.AUTHENTICATION_REQUIRED)

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_calendar_authentication_detection(self, mock_auth, mock_cdp):
        """Verify single-state ProviderState reporting for Calendar."""
        mock_auth.return_value = {"status": "LIVE_VERIFIED", "authenticated": True, "message": "Calendar active."}
        res_live = calendar_provider.check_events()
        self.assertEqual(res_live["status"], "OK")
        self.assertEqual(status_registry.get_status("calendar").state, ProviderState.LIVE_VERIFIED)

        mock_auth.return_value = {"status": "AUTHENTICATION_REQUIRED", "authenticated": False, "message": "Login required."}
        res_auth = calendar_provider.check_events()
        self.assertEqual(res_auth["status"], "CALENDAR_UNAVAILABLE")
        self.assertEqual(status_registry.get_status("calendar").state, ProviderState.AUTHENTICATION_REQUIRED)

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_instagram_authentication_detection(self, mock_auth, mock_cdp):
        """Verify single-state ProviderState reporting for Instagram."""
        mock_auth.return_value = {"status": "LIVE_VERIFIED", "authenticated": True, "message": "Instagram active."}
        res_live = instagram_provider.check_activity()
        self.assertEqual(res_live["status"], "OK")
        self.assertEqual(status_registry.get_status("instagram").state, ProviderState.LIVE_VERIFIED)

        mock_auth.return_value = {"status": "AUTHENTICATION_REQUIRED", "authenticated": False, "message": "Login required."}
        res_auth = instagram_provider.check_activity()
        self.assertEqual(res_auth["status"], "INSTAGRAM_UNAVAILABLE")
        self.assertEqual(status_registry.get_status("instagram").state, ProviderState.AUTHENTICATION_REQUIRED)

    def test_privacy_mode_isolation(self):
        """Verify Privacy Mode instantly pauses all awareness providers."""
        privacy_mode_manager.enable_privacy_mode()
        em_res = email_provider.check_inbox()
        ctx = context_engine.get_current_context()
        self.assertEqual(ctx.get("activity"), "PRIVACY_MODE_ACTIVE")
        self.assertEqual(status_registry.get_status("email").state, ProviderState.PAUSED)
        privacy_mode_manager.resume_awareness()

    def test_single_state_summary_string(self):
        """Verify get_summary_string produces non-ambiguous single status string."""
        summary = status_registry.get_summary_string()
        self.assertIn("CAM", summary)
        self.assertIn("WA", summary)
        self.assertNotIn("/", summary)  # Ensure no slash ambiguous status


if __name__ == "__main__":
    unittest.main()
