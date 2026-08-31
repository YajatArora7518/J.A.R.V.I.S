# tests/test_chrome_whatsapp_web_search.py
# Comprehensive Regression Test Suite for Chrome Profile, WhatsApp Web, and Web Search Routing

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.chrome_profile import resolve_chrome_profile, open_url_in_chrome_profile, redact_secrets, get_chrome_executable
from actions.whatsapp import open_whatsapp_web_in_yajat_profile, whatsapp
from actions.web_search import detect_web_search_intent, web_search, web_search_structured
from actions.open_app import open_app_structured
from core.intent_router import classify_intent


class TestChromeWhatsAppWebSearch(unittest.TestCase):

    # 1. INTENT ROUTING FOR WHATSAPP PHRASES
    def test_whatsapp_intent_triggers(self):
        phrases = [
            "Open WhatsApp",
            "Open WhatsApp Web",
            "WhatsApp khol",
            "WhatsApp Web khol",
            "Open WhatsApp in Chrome",
            "Open my WhatsApp"
        ]
        for phrase in phrases:
            info = classify_intent(phrase)
            self.assertEqual(info["intent"], "WHATSAPP_WEB", f"Failed for phrase: {phrase}")
            self.assertEqual(info["target"], "https://web.whatsapp.com/")
            self.assertNotEqual(info["intent"], "WINDOWS_APPLICATION")

    # 2. LOCAL STATE CHROME PROFILE RESOLUTION
    def test_chrome_profile_resolution_from_local_state(self):
        res = resolve_chrome_profile("Yajat")
        self.assertTrue(res.get("verified"), f"Resolution failed: {res}")
        self.assertTrue(res.get("dir_name"), "Profile dir_name should not be empty")
        self.assertIn("yajat", res.get("display_name", "").lower())
        self.assertTrue(Path(res["path"]).is_dir(), f"Profile path does not exist: {res['path']}")

    # 3. REJECT UNKNOWN CHROME PROFILE
    def test_chrome_profile_resolution_missing(self):
        res = resolve_chrome_profile("NonExistentProfile12345")
        self.assertFalse(res.get("verified"))
        self.assertIn("was not found", res.get("error", ""))

    # 4. NORMAL CHROME MODE GUARANTEE (NO INCOGNITO / NO GUEST)
    @patch("subprocess.Popen")
    @patch("actions.chrome_profile.get_chrome_executable")
    def test_chrome_normal_mode_args(self, mock_get_exe, mock_popen):
        mock_get_exe.return_value = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        res = open_url_in_chrome_profile("Yajat", "https://web.whatsapp.com/")
        self.assertTrue(res.get("success"))
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        
        # Verify normal browsing mode flags
        self.assertNotIn("--incognito", cmd_args)
        self.assertNotIn("--guest", cmd_args)
        self.assertIn("https://web.whatsapp.com/", cmd_args)

    # 5. WHATSAPP WEB URL VALIDATION & NO "NO APP FOUND"
    def test_open_app_structured_whatsapp_no_no_app_found(self):
        res = open_app_structured("whatsapp")
        self.assertNotEqual(res.get("mode"), "none")
        self.assertNotIn("not found", res.get("message", "").lower())
        self.assertTrue(res.get("success"))

        res_khol = open_app_structured("WhatsApp Web khol")
        self.assertTrue(res_khol.get("success"))

    # 6. WEB SEARCH INTENT DETECTION
    def test_web_search_intent_detection(self):
        search_phrases = [
            "Search the web for latest NVIDIA RTX 50 series news",
            "Google latest cricket news",
            "Search for the official OpenAI website",
            "Search YouTube for Virat Kohli",
            "Google karke batao latest news",
            "Online search karo"
        ]
        for phrase in search_phrases:
            is_search, clean_q, prov = detect_web_search_intent(phrase)
            self.assertTrue(is_search, f"Failed search intent for: {phrase}")
            self.assertTrue(len(clean_q) > 0)

    # 7. ROUTE SEPARATION MATRIX
    def test_intent_route_separation_matrix(self):
        self.assertIn(classify_intent("Open youtube.com")["intent"], ["WEBSITE", "KNOWN_WEBSITE"])
        self.assertEqual(classify_intent("Search YouTube for Virat Kohli")["intent"], "WEB_SEARCH")
        self.assertEqual(classify_intent("Open WhatsApp")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("Open Calculator")["intent"], "WINDOWS_APPLICATION")

    # 8. WEB SEARCH EXECUTION & REDACTION SAFETY
    def test_web_search_execution_and_redaction(self):
        data = web_search_structured("Python programming language specs", num_results=2)
        self.assertTrue(data.get("success"))
        self.assertTrue(len(data.get("results", [])) > 0)

        raw_secret = "User API key is sk-or-v1-1234567890abcdef and AIzaSy1234567890_secret"
        redacted = redact_secrets(raw_secret)
        self.assertNotIn("sk-or-v1-1234567890abcdef", redacted)
        self.assertNotIn("AIzaSy1234567890_secret", redacted)
        self.assertIn("...", redacted)

    # 9. ABSOLUTE PROHIBITION ON Edge / Desktop App / Incognito FOR WHATSAPP
    @patch("subprocess.Popen")
    @patch("actions.chrome_profile.get_chrome_executable")
    def test_whatsapp_strict_guarantee(self, mock_get_exe, mock_popen):
        mock_get_exe.return_value = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        res = open_whatsapp_web_in_yajat_profile()
        self.assertTrue(res.get("success"))
        cmd_args = mock_popen.call_args[0][0]
        
        # Verify Chrome executable is used and parameters are strictly correct
        self.assertIn("chrome.exe", cmd_args[0].lower())
        self.assertNotIn("msedge.exe", cmd_args[0].lower())
        self.assertNotIn("--incognito", cmd_args)
        self.assertNotIn("--guest", cmd_args)
        self.assertIn("https://web.whatsapp.com/", cmd_args)

    # 10. ERROR HANDLING (MISSING EXECUTABLE / MISSING PROFILE)
    @patch("actions.chrome_profile.get_chrome_executable", return_value=None)
    def test_missing_chrome_executable_handling(self, mock_get_exe):
        res = open_url_in_chrome_profile("Yajat", "https://web.whatsapp.com/")
        self.assertFalse(res.get("success"))
        self.assertIn("not found", res.get("message", "").lower())

    @patch("actions.chrome_profile.resolve_chrome_profile")
    def test_missing_yajat_profile_handling(self, mock_resolve):
        mock_resolve.return_value = {"verified": False, "error": "Yajat Chrome profile was not found."}
        res = open_whatsapp_web_in_yajat_profile()
        self.assertFalse(res.get("success"))
        self.assertIn("yajat chrome profile was not found", res.get("message", "").lower())


if __name__ == "__main__":
    unittest.main()
