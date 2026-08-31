# tests/test_web_automation.py
# Comprehensive Test Suite for JARVIS Web Automation Engine & Hardened Subsystems

import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from actions.chrome_profile import resolve_chrome_profile, sanitize_web_url, open_url_in_yajat_chrome
from actions.whatsapp_automation import resolve_contact, whatsapp_send_message, whatsapp_read_messages, whatsapp_make_call
from actions.instagram_automation import instagram_create_post, instagram_open
from actions.telegram_automation import resolve_telegram_contact, telegram_send_message, telegram_read_messages
from actions.college_schedule import ScheduleParser, ScheduleStore, ScheduleQueryEngine
from core.intent_router import classify_intent
from actions.web_search import detect_web_search_intent


class TestWebAutomationEngine(unittest.TestCase):

    def test_chrome_yajat_profile_resolution(self):
        res = resolve_chrome_profile("Yajat")
        self.assertTrue(res["verified"])
        self.assertEqual(res["display_name"], "Yajat")
        self.assertEqual(res["dir_name"], "Default")

    def test_prohibited_url_schemes_rejection(self):
        bad_urls = [
            "customdesktopapp://test",
            "customdesktopapp:",
            "whatsapp:12345",
            "telegram:test",
            "ms-windows-store:app",
            "file:///C:/cmd.exe",
            "javascript:alert(1)"
        ]
        for url in bad_urls:
            self.assertIsNone(sanitize_web_url(url), f"Failed to reject prohibited URL: {url}")

    def test_valid_https_url_sanitization(self):
        valid = "https://web.whatsapp.com/"
        self.assertEqual(sanitize_web_url(valid), valid)
        self.assertEqual(sanitize_web_url("web.whatsapp.com"), "https://web.whatsapp.com")

    def test_whatsapp_ambiguous_contact_resolution(self):
        res = resolve_contact("Rahul")
        self.assertIn(res["status"], ["ambiguous", "AMBIGUOUS_CONTACT"])
        self.assertTrue(res.get("requires_clarification"))
        self.assertIn("Rahul Sharma", res["matches"])
        self.assertIn("Rahul Mehta", res["matches"])

    def test_whatsapp_exact_contact_resolution(self):
        res = resolve_contact("Krish")
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["contact"]["name"], "Krish")

    def test_whatsapp_send_confirmation_safety(self):
        res = whatsapp_send_message("Krish", "Hello bhai", force_send=False)
        self.assertFalse(res["success"])
        self.assertTrue(res.get("requires_confirmation"))

    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome")
    def test_whatsapp_force_send_without_cdp(self, mock_open):
        """When CDP is unavailable, force_send opens WhatsApp Web but reports verified=False honestly."""
        mock_open.return_value = {"success": True}
        res = whatsapp_send_message("Krish", "Hello bhai", force_send=True)
        # Without CDP, the fallback opens WhatsApp Web but does NOT claim verified success
        self.assertEqual(res["action"], "whatsapp_send")
        self.assertFalse(res["verified"])
        self.assertIn("manual", res.get("message", "").lower())

    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome")
    def test_whatsapp_read_messages_without_cdp(self, mock_open):
        """Without CDP, WhatsApp read honestly reports it cannot read messages."""
        mock_open.return_value = {"success": True}
        res = whatsapp_read_messages(recipient="Rahul Sharma")
        # Without CDP, we can't read real DOM data — must NOT return fake data
        self.assertFalse(res["success"])
        self.assertFalse(res.get("verified", False))
        self.assertEqual(res["action"], "whatsapp_read")

    def test_whatsapp_call_confirmation(self):
        res = whatsapp_make_call("Krish", call_type="voice", confirm_call=False)
        self.assertFalse(res["success"])
        self.assertTrue(res.get("requires_confirmation"))

    def test_instagram_media_path_validation(self):
        res = instagram_create_post(media_path="invalid_path.jpg", caption="Test")
        self.assertFalse(res["success"])
        self.assertTrue(res.get("requires_media_input"))

    def test_telegram_contact_resolution(self):
        res = resolve_telegram_contact("Rahul")
        self.assertEqual(res["status"], "ambiguous")

    def test_college_schedule_query_engine(self):
        engine = ScheduleQueryEngine()
        res = engine.get_today_schedule()
        self.assertTrue("day" in res)
        self.assertTrue("classes" in res)

    def test_college_schedule_natural_queries(self):
        engine = ScheduleQueryEngine()
        res1 = engine.query_schedule_natural("Today meri class kya hai?")
        self.assertTrue(res1["success"])
        self.assertEqual(res1["type"], "today_schedule")

        res2 = engine.query_schedule_natural("Abhi meri class kaunsi hai?")
        self.assertTrue(res2["success"])
        self.assertEqual(res2["type"], "current_next_class")

    def test_communication_intent_priority_routing(self):
        res1 = classify_intent("Krish ko WhatsApp par Hello bhej")
        self.assertEqual(res1["intent"], "WHATSAPP_MESSAGE")
        self.assertEqual(res1["tool"], "whatsapp")

        res2 = classify_intent("Rahul ko WhatsApp call karo")
        self.assertEqual(res2["intent"], "WHATSAPP_CALL")

        res3 = classify_intent("Instagram pe ye photo post karo")
        self.assertEqual(res3["intent"], "INSTAGRAM_POST")

        res4 = classify_intent("Today meri class kya hai?")
        self.assertEqual(res4["intent"], "COLLEGE_QUERY")

    def test_web_search_intent_detection(self):
        is_search, q, prov = detect_web_search_intent("latest NVIDIA news")
        self.assertTrue(is_search)


if __name__ == "__main__":
    unittest.main()
