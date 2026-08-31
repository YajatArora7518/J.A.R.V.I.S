# tests/test_google_chrome_session.py
"""
Comprehensive Unit Test Suite for Chrome Session Integration across Gmail, Calendar, Instagram, and WhatsApp Web.
"""

import unittest
from unittest.mock import patch, MagicMock

from actions.chrome_profile import get_chrome_executable, resolve_chrome_profile, is_chrome_running
from actions.browser_automation import is_cdp_active, browser_automation_engine
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.email_provider import email_provider
from agent.awareness.calendar_provider import calendar_provider
from agent.awareness.instagram_provider import instagram_provider
from agent.awareness.whatsapp_provider import whatsapp_provider
from agent.awareness.status_model import status_registry, ProviderState
from agent.context_engine import context_engine


class TestGoogleChromeSession(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.resume_awareness()
        permission_manager.set_permission("EMAIL_READ", True)
        permission_manager.set_permission("CALENDAR_READ", True)
        permission_manager.set_permission("INSTAGRAM_READ", True)
        permission_manager.set_permission("WHATSAPP_READ", True)

    def test_chrome_executable_and_profile_discovery(self):
        """Verify dynamic discovery of installed Chrome binary and Yajat profile."""
        chrome_bin = get_chrome_executable()
        self.assertIsNotNone(chrome_bin)
        self.assertTrue(chrome_bin.endswith("chrome.exe"))

        prof_info = resolve_chrome_profile("Yajat")
        self.assertTrue(prof_info.get("verified"))
        self.assertEqual(prof_info.get("display_name"), "Yajat")

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_gmail_chrome_session_verified(self, mock_auth, mock_cdp):
        """Verify email_provider returns LIVE_VERIFIED when Gmail authenticated in Chrome."""
        mock_auth.return_value = {
            "status": "LIVE_VERIFIED",
            "authenticated": True,
            "unread_count": 2,
            "message": "Gmail authenticated session active."
        }
        res = email_provider.check_inbox()
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res.get("source"), "chrome_session")
        st = status_registry.get_status("email")
        self.assertIsNotNone(st)
        self.assertEqual(st.state, ProviderState.LIVE_VERIFIED)

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_calendar_chrome_session_verified(self, mock_auth, mock_cdp):
        """Verify calendar_provider returns LIVE_VERIFIED when Google Calendar authenticated in Chrome."""
        mock_auth.return_value = {
            "status": "LIVE_VERIFIED",
            "authenticated": True,
            "events": [],
            "message": "Google Calendar authenticated session active."
        }
        res = calendar_provider.check_events()
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res.get("source"), "chrome_session")
        st = status_registry.get_status("calendar")
        self.assertIsNotNone(st)
        self.assertEqual(st.state, ProviderState.LIVE_VERIFIED)

    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch.object(browser_automation_engine, "check_service_auth_sync")
    def test_instagram_chrome_session_verified(self, mock_auth, mock_cdp):
        """Verify instagram_provider returns LIVE_VERIFIED when Instagram authenticated in Chrome."""
        mock_auth.return_value = {
            "status": "LIVE_VERIFIED",
            "authenticated": True,
            "activity": [],
            "message": "Instagram authenticated session active."
        }
        res = instagram_provider.check_activity()
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res.get("source"), "chrome_session")
        st = status_registry.get_status("instagram")
        self.assertIsNotNone(st)
        self.assertEqual(st.state, ProviderState.LIVE_VERIFIED)

    def test_privacy_mode_isolation(self):
        """Verify Privacy Mode instantly pauses all awareness providers."""
        privacy_mode_manager.enable_privacy_mode()
        em_res = email_provider.check_inbox()
        cal_res = calendar_provider.check_events()
        ig_res = instagram_provider.check_activity()
        wa_res = whatsapp_provider.check_unread()

        self.assertEqual(em_res["status"], "EMAIL_UNAVAILABLE")
        self.assertEqual(cal_res["status"], "CALENDAR_UNAVAILABLE")
        self.assertEqual(ig_res["status"], "INSTAGRAM_UNAVAILABLE")
        self.assertEqual(wa_res["status"], "WHATSAPP_UNAVAILABLE")

        st_em = status_registry.get_status("email")
        self.assertEqual(st_em.state, ProviderState.PAUSED)
        privacy_mode_manager.resume_awareness()

    def test_context_engine_aggregation(self):
        """Verify ContextEngine includes all provider context keys cleanly."""
        ctx = context_engine.get_current_context()
        self.assertIn("gmail_context", ctx)
        self.assertIn("calendar_context", ctx)
        self.assertIn("instagram_context", ctx)
        self.assertIn("whatsapp_context", ctx)
        self.assertIn("screen_context", ctx)
        self.assertIn("camera_context", ctx)


if __name__ == "__main__":
    unittest.main()
