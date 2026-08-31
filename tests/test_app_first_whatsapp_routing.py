# tests/test_app_first_whatsapp_routing.py
# Comprehensive Test Suite for App-First Resolution, Search vs Open Routing & WhatsApp Web Automation

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.intent_router import classify_intent
from actions.open_app import open_app, open_app_structured, _focus_existing_window
from actions.app_registry import resolve_app, normalize_app_name
from actions.whatsapp import whatsapp, resolve_whatsapp_contact
from actions.whatsapp_automation import resolve_contact, parse_whatsapp_command


class TestAppFirstAndWhatsAppRouting(unittest.TestCase):

    # 1. OPEN WHATSAPP -> APP-FIRST DISCOVERY
    @patch("actions.open_app._is_process_running", return_value=False)
    @patch("actions.open_app._launch_desktop_windows")
    def test_open_whatsapp_app_first_native(self, mock_launch, mock_running):
        mock_launch.return_value = (True, "desktop", "WhatsApp Desktop launched via protocol handler 'whatsapp:'")
        res = open_app_structured("WhatsApp")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "desktop")
        self.assertIn("WhatsApp", res["app"])

    # 2. OPEN WHATSAPP -> FALLBACK TO WEB WHEN DESKTOP NOT INSTALLED
    @patch("actions.open_app._is_process_running", return_value=False)
    @patch("actions.open_app._launch_desktop_windows", return_value=(False, "", "Desktop app not found"))
    @patch("actions.chrome_profile.open_url_in_yajat_chrome")
    def test_open_whatsapp_web_fallback(self, mock_chrome, mock_launch, mock_running):
        mock_chrome.return_value = {"success": True, "message": "Opened web fallback in Yajat Chrome"}
        res = open_app_structured("WhatsApp")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "web_fallback")
        self.assertIn("WhatsApp", res["app"])

    # 3. EXPLICIT WHATSAPP WEB REQUEST -> DIRECT WEB
    @patch("actions.chrome_profile.open_url_in_yajat_chrome")
    def test_explicit_whatsapp_web_request(self, mock_chrome):
        mock_chrome.return_value = {"success": True, "message": "Opened WhatsApp Web in Yajat Chrome"}
        res = open_app_structured("WhatsApp Web")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "web_fallback")

    # 4. INTENT CLASSIFICATION TEST MATRIX
    def test_search_vs_open_intent_classification(self):
        # Open WhatsApp -> WINDOWS_APPLICATION (App-First)
        self.assertEqual(classify_intent("open WhatsApp")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("WhatsApp kholo")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("open Chrome")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("open VS Code")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("open Calculator")["intent"], "WINDOWS_APPLICATION")

        # Explicit Web requests -> WHATSAPP_WEB / KNOWN_WEBSITE
        self.assertEqual(classify_intent("open WhatsApp Web")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("WhatsApp Web kholo")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("open youtube.com")["intent"], "KNOWN_WEBSITE")

        # Search commands -> WEB_SEARCH
        self.assertEqual(classify_intent("search WhatsApp")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("search best laptops")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("google latest news")["intent"], "WEB_SEARCH")

        # WhatsApp Messaging & Calling intents
        self.assertEqual(classify_intent("message Rahul on WhatsApp")["intent"], "WHATSAPP_MESSAGE")
        self.assertEqual(classify_intent("call Rahul on WhatsApp")["intent"], "WHATSAPP_CALL")
        self.assertEqual(classify_intent("WhatsApp Rahul and say I'm coming")["intent"], "WHATSAPP_MESSAGE")
        self.assertEqual(classify_intent("WhatsApp pe mummy ko call karo")["intent"], "WHATSAPP_CALL")
        self.assertEqual(classify_intent("read my unread WhatsApp messages")["intent"], "WHATSAPP_READ")

    # 5. NATURAL LANGUAGE WHATSAPP PARSER
    def test_whatsapp_natural_command_parser(self):
        p1 = parse_whatsapp_command("Send Rahul a WhatsApp message saying I'll be late")
        self.assertEqual(p1["contact"], "Rahul")
        self.assertEqual(p1["message"], "I'll be late")

        p2 = parse_whatsapp_command("WhatsApp Rahul and tell him I'm coming")
        self.assertEqual(p2["contact"], "Rahul")
        self.assertEqual(p2["message"], "I'm coming")

        p3 = parse_whatsapp_command("Rahul ko WhatsApp pe message karo ki main 10 minute late hoon")
        self.assertEqual(p3["contact"], "Rahul")
        self.assertEqual(p3["message"], "main 10 minute late hoon")

        p4 = parse_whatsapp_command("Call Rahul on WhatsApp")
        self.assertEqual(p4["contact"], "Rahul")

        p5 = parse_whatsapp_command("WhatsApp pe mummy ko call karo")
        self.assertEqual(p5["contact"], "mummy")

    # 6. CONTACT RESOLUTION & AMBIGUITY CLARIFICATION
    def test_contact_resolution_ambiguity(self):
        res = resolve_whatsapp_contact("Rahul")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "AMBIGUOUS_CONTACT")
        self.assertTrue(res.get("requires_clarification"))
        self.assertGreater(len(res.get("matches", [])), 1)

        res_single = resolve_whatsapp_contact("Priya")
        self.assertTrue(res_single["success"])
        self.assertEqual(res_single["contact"]["name"], "Priya Patel")

    # 7. WHATSAPP SECURITY CONFIRMATION REQUIRED
    def test_whatsapp_messaging_confirmation_policy(self):
        res = whatsapp(action="send_message", contact="Priya Patel", message="Test message", force_send=False)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "CONFIRMATION_REQUIRED")
        self.assertTrue(res.get("requires_confirmation"))

    # 8. WHATSAPP CALLING HONEST REPORTING
    def test_whatsapp_calling_confirmation_policy(self):
        res = whatsapp(action="call", contact="Priya Patel", confirm_call=False)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "CONFIRMATION_REQUIRED")
        self.assertTrue(res.get("requires_confirmation"))

    # 9. RUNNING PROCESS WINDOW FOCUSING
    @patch("actions.open_app._is_process_running", return_value=True)
    @patch("actions.open_app._focus_existing_window", return_value=True)
    def test_running_process_window_focusing(self, mock_focus, mock_running):
        res = open_app_structured("chrome")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "desktop")
        mock_focus.assert_called_once()


if __name__ == "__main__":
    unittest.main()
