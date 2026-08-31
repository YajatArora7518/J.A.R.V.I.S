# tests/test_telegram_cdp.py
# Unit Test Suite for Telegram Web CDP DOM Reader (Phase 6C)

import unittest
from unittest.mock import patch, MagicMock
from actions.telegram_automation import telegram_read_messages, resolve_telegram_contact


class TestTelegramCDPReader(unittest.TestCase):
    """Verify Telegram Web contact resolution, CDP DOM extraction, and fallback mechanisms."""

    def test_resolve_telegram_contact_exact(self):
        res = resolve_telegram_contact("Rahul Sharma")
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["contact"]["handle"], "@rahul_sharma")

    def test_resolve_telegram_contact_ambiguous(self):
        res = resolve_telegram_contact("Rahul")
        self.assertEqual(res["status"], "ambiguous")
        self.assertTrue(res["requires_clarification"])
        self.assertIn("Rahul Sharma", res["matches"])
        self.assertIn("Rahul Mehta", res["matches"])

    @patch("actions.telegram_automation.is_cdp_active", return_value=False)
    @patch("actions.telegram_automation.open_url_in_yajat_chrome", return_value={"success": True})
    def test_cdp_unavailable_fallback(self, mock_chrome, mock_cdp):
        """When CDP is inactive, it opens Telegram Web and returns structured fallback dict."""
        res = telegram_read_messages("Rahul Sharma")
        self.assertFalse(res["success"])
        self.assertEqual(res["action"], "telegram_read")
        self.assertIn("unavailable", res["message"])
        mock_chrome.assert_called_once()

    @patch("actions.telegram_automation.is_cdp_active", return_value=True)
    @patch("actions.telegram_automation.browser_automation_engine.run")
    def test_cdp_active_successful_extraction(self, mock_engine_run, mock_cdp):
        """When CDP is active and returns messages, telegram_read_messages returns success dict."""
        mock_engine_run.return_value = {
            "success": True,
            "action": "telegram_read",
            "platform": "telegram",
            "recipient": "Rahul Sharma",
            "messages": [{"sender": "Rahul Sharma", "text": "Hello JARVIS", "timestamp": "10:30 AM"}],
            "verified": True
        }

        # Intercept async function to prevent unawaited coroutine warning
        with patch("actions.telegram_automation._async_telegram_read_cdp", return_value=None):
            res = telegram_read_messages("Rahul Sharma")
            self.assertTrue(res["success"])
            self.assertEqual(len(res["messages"]), 1)
            self.assertEqual(res["messages"][0]["text"], "Hello JARVIS")


if __name__ == "__main__":
    unittest.main()
