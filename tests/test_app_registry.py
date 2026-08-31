# tests/test_app_registry.py
# Unit and Mock Integration Tests for JARVIS Application Registry, Discovery & Security

import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from actions.app_registry import resolve_app, normalize_app_name, APP_REGISTRY
from actions.open_app import open_app, open_app_structured
from core.security import default_security_manager, RiskLevel


class TestAppRegistryAndLauncher(unittest.TestCase):

    # 1. Alias Resolution
    def test_alias_resolution(self):
        self.assertEqual(resolve_app("wa")["name"], "WhatsApp")
        self.assertEqual(resolve_app("tg")["name"], "Telegram")
        self.assertEqual(resolve_app("disc")["name"], "Discord")
        self.assertEqual(resolve_app("twt")["name"], "X (Twitter)")

    # 2. Natural Language Normalization
    def test_natural_language_normalization(self):
        self.assertEqual(normalize_app_name("Open my WhatsApp please"), "whatsapp")
        self.assertEqual(normalize_app_name("Take me to Instagram web"), "instagram")
        self.assertEqual(normalize_app_name("Check my Gmail email"), "gmail")
        self.assertEqual(normalize_app_name("Launch VS Code app"), "vs code")

    # 3. Fuzzy Matching
    def test_fuzzy_matching(self):
        self.assertEqual(resolve_app("launch insta")["name"], "Instagram")
        self.assertEqual(resolve_app("open google mail")["name"], "Gmail")
        self.assertEqual(resolve_app("start spotify music")["name"], "Spotify")

    # 4. WhatsApp Resolution
    def test_whatsapp_resolution(self):
        wa = resolve_app("open whatsapp")
        self.assertIsNotNone(wa)
        self.assertEqual(wa["name"], "WhatsApp")
        self.assertEqual(wa["category"], "messaging")
        self.assertIn("https://web.whatsapp.com", wa["web_url"])

    # 5. Gmail Resolution
    def test_gmail_resolution(self):
        gmail = resolve_app("check my gmail")
        self.assertIsNotNone(gmail)
        self.assertEqual(gmail["name"], "Gmail")
        self.assertEqual(gmail["category"], "email")
        self.assertIn("mail.google.com", gmail["web_url"])

    # 6. Instagram Resolution
    def test_instagram_resolution(self):
        insta = resolve_app("open instagram")
        self.assertIsNotNone(insta)
        self.assertEqual(insta["name"], "Instagram")
        self.assertEqual(insta["category"], "social")

    # 7. Discord Resolution
    def test_discord_resolution(self):
        disc = resolve_app("launch discord")
        self.assertIsNotNone(disc)
        self.assertEqual(disc["name"], "Discord")
        self.assertEqual(disc["category"], "messaging")

    # 8. YouTube Resolution
    def test_youtube_resolution(self):
        yt = resolve_app("open youtube")
        self.assertIsNotNone(yt)
        self.assertEqual(yt["name"], "YouTube")
        self.assertEqual(yt["category"], "social")

    # 9. Outlook Resolution
    def test_outlook_resolution(self):
        outlook = resolve_app("open outlook")
        self.assertIsNotNone(outlook)
        self.assertEqual(outlook["name"], "Outlook")
        self.assertEqual(outlook["category"], "email")

    # 10. Unknown Application Handling
    def test_unknown_app_handling(self):
        unknown = resolve_app("open my custom unknown helper app")
        self.assertIsNotNone(unknown)
        self.assertEqual(unknown["name"], "Custom Unknown Helper App")

    # 11. Desktop Discovery (Mocked)
    @patch("actions.open_app.shutil.which", return_value=r"C:\Windows\System32\notepad.exe")
    @patch("actions.open_app.verify_app_launched")
    def test_desktop_discovery_mocked(self, mock_verify, mock_which):
        mock_verify.return_value = {"verified": True}
        res = open_app_structured("notepad")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "desktop")

    # 12. Registry Discovery (Mocked)
    @patch("actions.open_app.find_app_path_in_registry")
    @patch("actions.open_app.subprocess.Popen")
    @patch("actions.open_app.verify_app_launched")
    def test_registry_discovery_mocked(self, mock_verify, mock_popen, mock_find_reg):
        mock_find_reg.return_value = r"C:\Program Files\CustomDesktopApp\App.exe"
        mock_verify.return_value = {"verified": True}
        res = open_app_structured("customdesktopapp")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "desktop")

    # 13. PATH Discovery (Mocked)
    @patch("actions.open_app.shutil.which")
    @patch("actions.open_app.subprocess.Popen")
    @patch("actions.open_app.verify_app_launched")
    def test_path_discovery_mocked(self, mock_verify, mock_popen, mock_which):
        mock_which.return_value = r"C:\Windows\System32\notepad.exe"
        mock_verify.return_value = {"verified": True}
        res = open_app_structured("notepad")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "desktop")

    # 14. Web Fallback (Mocked)
    @patch("actions.chrome_profile.open_url_in_yajat_chrome")
    @patch("actions.open_app._is_process_running", return_value=False)
    @patch("actions.open_app.shutil.which", return_value=None)
    @patch("actions.open_app.find_app_path_in_registry", return_value=None)
    def test_web_fallback_mocked(self, mock_reg, mock_which, mock_running, mock_chrome):
        mock_chrome.return_value = {"success": True, "message": "Opened web fallback"}
        res = open_app_structured("customdesktopapp")
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "web_fallback")

    # 15. Security Boundaries
    def test_security_boundaries(self):
        risk_open = default_security_manager.classify_risk("open_app", {"app_name": "whatsapp"})
        self.assertIn(risk_open, [RiskLevel.LOW, RiskLevel.MEDIUM])

        risk_delete = default_security_manager.classify_risk("file_controller", {"action": "delete", "path": "test.txt"})
        self.assertEqual(risk_delete, RiskLevel.HIGH)

    # 16. Structured Results
    @patch("actions.chrome_profile.open_url_in_yajat_chrome")
    def test_structured_results(self, mock_chrome):
        mock_chrome.return_value = {"success": True, "message": "Opened Gmail in Yajat Chrome"}
        res = open_app_structured("gmail")
        self.assertIn("success", res)
        self.assertIn("app", res)
        self.assertIn("mode", res)
        self.assertIn("message", res)
        self.assertIn("Gmail", res["app"])


if __name__ == "__main__":
    unittest.main()
