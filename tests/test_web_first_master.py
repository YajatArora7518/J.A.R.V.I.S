# tests/test_web_first_master.py
# Dedicated Master Regression Test Suite for Web-First Browser & Social Media Architecture

import unittest
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.chrome_profile import (
    resolve_chrome_profile,
    open_url_in_chrome_profile,
    open_url_in_yajat_chrome,
    sanitize_web_url,
    redact_secrets,
    get_chrome_executable
)
from actions.web_registry import KNOWN_WEBSITES, resolve_website_url, open_website_in_yajat_profile
from actions.whatsapp import open_whatsapp_web_in_yajat_profile
from actions.telegram import open_telegram_web_in_yajat_profile
from actions.web_search import detect_web_search_intent, web_search_structured
from actions.open_app import open_app_structured
from core.intent_router import classify_intent


class TestWebFirstMasterArchitecture(unittest.TestCase):

    # 1. CHROME YAJAT PROFILE RESOLUTION
    def test_chrome_yajat_profile_resolution(self):
        res = resolve_chrome_profile("Yajat")
        self.assertTrue(res.get("verified"), f"Profile resolution failed: {res}")
        self.assertIn("yajat", res.get("display_name", "").lower())
        self.assertTrue(Path(res["path"]).is_dir())

    # 2. ALL KNOWN WEB & SOCIAL PLATFORMS ROUTE TO YAJAT CHROME PROFILE
    def test_social_media_and_web_platforms_resolution(self):
        platforms = [
            ("whatsapp", "https://web.whatsapp.com/"),
            ("telegram", "https://web.telegram.org/"),
            ("instagram", "https://www.instagram.com/"),
            ("facebook", "https://www.facebook.com/"),
            ("twitter", "https://x.com/"),
            ("x", "https://x.com/"),
            ("youtube", "https://www.youtube.com/"),
            ("reddit", "https://www.reddit.com/"),
            ("discord", "https://discord.com/app"),
            ("linkedin", "https://www.linkedin.com/"),
            ("pinterest", "https://www.pinterest.com/"),
            ("snapchat", "https://web.snapchat.com/"),
            ("spotify", "https://open.spotify.com/"),
            ("github", "https://github.com/"),
            ("gmail", "https://mail.google.com/"),
            ("google drive", "https://drive.google.com/"),
            ("google docs", "https://docs.google.com/"),
            ("google maps", "https://maps.google.com/"),
            ("google", "https://www.google.com/")
        ]
        for key, expected_url in platforms:
            rec = resolve_website_url(key)
            self.assertIsNotNone(rec, f"Failed to resolve platform: {key}")
            self.assertEqual(rec["url"], expected_url, f"Mismatch for {key}")

    # 3. ABSOLUTE SECURITY & NORMAL BROWSING FLAGS (NO INCOGNITO / NO GUEST / NO EDGE)
    @patch("subprocess.Popen")
    @patch("actions.chrome_profile.get_chrome_executable")
    def test_web_launch_normal_mode_guarantee(self, mock_get_exe, mock_popen):
        mock_get_exe.return_value = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        res = open_website_in_yajat_profile("instagram")
        self.assertTrue(res.get("success"))
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]

        # Verify normal browsing mode flags
        self.assertIn("chrome.exe", cmd_args[0].lower())
        self.assertNotIn("msedge.exe", cmd_args[0].lower())
        self.assertNotIn("--incognito", cmd_args)
        self.assertNotIn("--guest", cmd_args)
        self.assertIn("https://www.instagram.com/", cmd_args)

    # 4. NATURAL LANGUAGE INTENT ROUTING
    def test_intent_routing_priority_chain(self):
        # WHATSAPP_WEB & EXPLICIT WEB REQUESTS
        self.assertEqual(classify_intent("Open WhatsApp Web")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("WhatsApp Web kholo")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("Open Telegram Web")["intent"], "TELEGRAM_WEB")

        # WINDOWS_APPLICATION (App-First Discovery for open commands)
        self.assertEqual(classify_intent("Open WhatsApp")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("WhatsApp kholo")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open Telegram")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Telegram kholo")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open Instagram")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Instagram kholo")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open YouTube")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open Discord")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open Notepad")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open Calculator")["intent"], "WINDOWS_APPLICATION")

    # 5. DISAMBIGUATION: OPEN VS SEARCH
    def test_open_vs_search_disambiguation(self):
        # Open commands -> WINDOWS_APPLICATION (App-First)
        self.assertEqual(classify_intent("Open Instagram")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open YouTube")["intent"], "WINDOWS_APPLICATION")

        # Search commands -> WEB_SEARCH
        self.assertEqual(classify_intent("Search YouTube for Virat Kohli")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("Search Instagram for latest posts")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("Google latest cricket news")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("Online check karo")["intent"], "WEB_SEARCH")

    # 6. TIME-SENSITIVE / CURRENT INFO WEB SEARCH
    def test_time_sensitive_web_search_triggers(self):
        queries = [
            "What is the latest news about SpaceX",
            "What is the current price of Bitcoin",
            "What happened today in Delhi",
            "Latest version of Python",
            "Who won the match today",
            "Search the web for best laptop under 75k"
        ]
        for q in queries:
            is_search, clean_q, prov = detect_web_search_intent(q)
            self.assertTrue(is_search, f"Failed for query: {q}")

    # 7. OPEN APP INTERCEPTION (NO 'NO APP FOUND' FOR WEB SERVICES)
    def test_open_app_interception_for_web_services(self):
        web_services = ["instagram", "telegram", "github", "discord", "youtube", "gmail"]
        for service in web_services:
            res = open_app_structured(service)
            self.assertTrue(res.get("success"), f"Failed for open_app: {service}")
            self.assertNotEqual(res.get("mode"), "none")

    # 8. SANITIZE WEB URL REJECTIONS (PROHIBITED PROTOCOLS)
    def test_sanitize_web_url_rejections(self):
        self.assertIsNone(sanitize_web_url("customdesktopapp://foo"))
        self.assertIsNone(sanitize_web_url("customdesktopapp:"))
        self.assertIsNone(sanitize_web_url("ms-windows-store:"))
        self.assertIsNone(sanitize_web_url("whatsapp:"))
        self.assertIsNone(sanitize_web_url("telegram:"))
        self.assertIsNone(sanitize_web_url("file:///C:/Windows/System32/cmd.exe"))
        self.assertIsNone(sanitize_web_url("javascript:alert(1)"))
        self.assertIsNone(sanitize_web_url("data:text/html,test"))

        # Safe URLs accepted
        self.assertEqual(sanitize_web_url("https://web.whatsapp.com/"), "https://web.whatsapp.com/")
        self.assertEqual(sanitize_web_url("https://web.telegram.org/"), "https://web.telegram.org/")
        self.assertEqual(sanitize_web_url("web.whatsapp.com"), "https://web.whatsapp.com")

    # 9. MISSING YAJAT PROFILE FAILS SAFELY
    @patch("actions.chrome_profile.resolve_chrome_profile")
    def test_missing_yajat_profile_safety(self, mock_resolve):
        mock_resolve.return_value = {"verified": False, "error": "Yajat Chrome profile was not found."}
        res = open_url_in_yajat_chrome("https://web.whatsapp.com/")
        self.assertFalse(res["success"])
        self.assertIn("Yajat Chrome profile was not found", res["message"])

    # 10. SECRET REDACTION AUDIT
    def test_secret_redaction(self):
        secret_text = "API Key sk-or-v1-abcdef1234567890 and token AIzaSy1234567890_secret"
        clean = redact_secrets(secret_text)
        self.assertNotIn("sk-or-v1-abcdef1234567890", clean)
        self.assertNotIn("AIzaSy1234567890_secret", clean)


if __name__ == "__main__":
    unittest.main()
