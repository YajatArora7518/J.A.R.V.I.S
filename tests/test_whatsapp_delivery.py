# tests/test_whatsapp_delivery.py
# Targeted Unit Test Suite for WhatsApp Real Message Sending & Verification

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.whatsapp import whatsapp, resolve_whatsapp_contact
from actions.whatsapp_automation import (
    resolve_contact,
    whatsapp_send_message,
    _async_whatsapp_send,
)


class TestWhatsAppDeliveryUnit(unittest.TestCase):

    def test_recipient_resolution_exact(self):
        res = resolve_contact("Krish")
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["contact"]["name"], "Krish")

    def test_recipient_resolution_ambiguous(self):
        res = resolve_contact("Rahul")
        self.assertEqual(res["status"], "AMBIGUOUS_CONTACT")
        self.assertTrue(res["requires_clarification"])
        self.assertIn("Rahul Sharma", res["matches"])
        self.assertIn("Rahul Mehta", res["matches"])

    def test_recipient_resolution_unknown_passthrough(self):
        res = resolve_contact("Ananya")
        self.assertEqual(res["status"], "exact")
        self.assertEqual(res["contact"]["name"], "Ananya")

    def test_confirmation_required_by_default(self):
        res = whatsapp_send_message("Krish", "Hello bhai!", force_send=False)
        self.assertFalse(res["success"])
        self.assertTrue(res["requires_confirmation"])
        self.assertEqual(res["status"], "CONFIRMATION_REQUIRED")
        self.assertIn("Should I send it?", res["message"])

    def test_ambiguous_contact_blocks_send(self):
        res = whatsapp_send_message("Rahul", "Meeting at 5pm", force_send=True)
        self.assertFalse(res["success"])
        self.assertTrue(res["requires_clarification"])
        self.assertEqual(res["status"], "AMBIGUOUS_CONTACT")
        self.assertIn("I found multiple", res["message"])

    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": False, "status": "CDP_UNAVAILABLE", "message": "CDP port 9222 unavailable."})
    @patch("actions.whatsapp_automation.is_cdp_active", return_value=False)
    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome", return_value={"success": True})
    @patch("actions.whatsapp_automation.ensure_cdp_chrome")
    def test_fallback_when_cdp_unavailable(self, mock_ensure, mock_open, mock_is_active, mock_health):
        res = whatsapp_send_message("Krish", "Test fallback", force_send=True)
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "CDP_UNAVAILABLE")
        self.assertIn("Cannot send WhatsApp message automatically", res["message"])

    def test_login_required_detection(self):
        mock_page = AsyncMock()
        mock_qr = MagicMock()
        mock_page.query_selector = AsyncMock(side_effect=lambda sel: mock_qr if "Scan" in sel or "data-ref" in sel else None)

        with patch("actions.whatsapp_automation.browser_automation_engine") as mock_engine:
            mock_engine.get_or_open_page = AsyncMock(return_value=mock_page)
            import asyncio
            res = asyncio.run(_async_whatsapp_send("Krish", "Hello", force_send=True))

        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "LOGIN_REQUIRED")
        self.assertEqual(res["error"], "Login required")
        self.assertIn("not logged in", res["message"])

    def test_contact_not_found_handling(self):
        mock_page = AsyncMock()
        # Search input found, but search result item and #main chat not found
        mock_search_el = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=lambda sel, **kw: mock_search_el if "contenteditable" in sel else None)
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.query_selector = AsyncMock(return_value=None)

        with patch("actions.whatsapp_automation.browser_automation_engine") as mock_engine:
            mock_engine.get_or_open_page = AsyncMock(return_value=mock_page)
            import asyncio
            res = asyncio.run(_async_whatsapp_send("UnknownContactXYZ", "Hello", force_send=True))

        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertIn("couldn't open conversation", res["message"])

    def test_successful_verified_send_with_unicode_and_emojis(self):
        mock_page = AsyncMock()
        mock_search_el = AsyncMock()
        mock_main_chat = AsyncMock()
        mock_input_el = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(side_effect=lambda sel, **kw: mock_search_el if "side" in sel or "data-tab=\"3\"" in sel else (mock_input_el if "main" in sel or "data-tab=\"10\"" in sel else None))
        mock_page.query_selector = AsyncMock(side_effect=lambda sel: None if "Scan" in sel else (mock_main_chat if sel == "#main" else None))

        # Sent bubble verification mock
        mock_bubble = AsyncMock()
        msg_text = "Kal college aa raha hai? 😂👍 (Hindi test: क्या हाल है)"
        mock_bubble.inner_text = AsyncMock(return_value=f"10:45 AM\n{msg_text}\n✓✓")
        mock_page.query_selector_all = AsyncMock(side_effect=lambda sel: [mock_bubble] if "message-out" in sel or "_akbu" in sel else [])

        with patch("actions.whatsapp_automation.browser_automation_engine") as mock_engine:
            mock_engine.get_or_open_page = AsyncMock(return_value=mock_page)
            import asyncio
            res = asyncio.run(_async_whatsapp_send("Krish", msg_text, force_send=True))

        self.assertTrue(res["success"])
        self.assertTrue(res["verified"])
        self.assertEqual(res["status"], "SENT_VERIFIED")
        self.assertIn("Done, Boss. I sent the message", res["message"])

    def test_unverified_send(self):
        mock_page = AsyncMock()
        mock_search_el = AsyncMock()
        mock_main_chat = AsyncMock()
        mock_input_el = AsyncMock()

        mock_page.wait_for_selector = AsyncMock(side_effect=lambda sel, **kw: mock_search_el if "side" in sel else (mock_input_el if "main" in sel else None))
        mock_page.query_selector = AsyncMock(side_effect=lambda sel: None if "Scan" in sel else (mock_main_chat if sel == "#main" else None))
        # Sent bubbles mock returns empty/different text -> verification fails
        mock_page.query_selector_all = AsyncMock(return_value=[])

        with patch("actions.whatsapp_automation.browser_automation_engine") as mock_engine:
            mock_engine.get_or_open_page = AsyncMock(return_value=mock_page)
            import asyncio
            res = asyncio.run(_async_whatsapp_send("Krish", "Unverified text", force_send=True))

        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "SENT_UNVERIFIED")
        self.assertIn("couldn't verify that WhatsApp delivered it", res["message"])


if __name__ == "__main__":
    unittest.main()
