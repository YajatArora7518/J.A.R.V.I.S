# tests/test_whatsapp_upgrade.py
# Comprehensive Unit Test Suite for WhatsApp Communication Layer Upgrade

import json
import time
import unittest
from unittest.mock import patch, MagicMock

from actions.whatsapp_automation import (
    resolve_contact,
    whatsapp_send_message,
    whatsapp_read_messages,
    whatsapp_reply,
    whatsapp_set_auto_reply,
    whatsapp_check_auto_reply,
    whatsapp_make_call,
    whatsapp_end_call,
    load_autoreply_config,
    save_autoreply_config,
    load_autoreply_state,
    save_autoreply_state,
    AUTOREPLY_CONFIG_PATH,
    AUTOREPLY_STATE_PATH
)
from actions.whatsapp import whatsapp
from actions.send_message import send_message
from core.intent_router import classify_intent


class TestWhatsAppUpgrade(unittest.TestCase):

    def setUp(self):
        # Save existing auto-reply configs if present
        self._orig_cfg = load_autoreply_config()
        self._orig_state = load_autoreply_state()

    def tearDown(self):
        # Restore auto-reply configs
        save_autoreply_config(self._orig_cfg)
        save_autoreply_state(self._orig_state)

    def test_contact_resolution(self):
        """Verify exact, ambiguous, and unknown contact resolution."""
        # Exact match
        res_exact = resolve_contact("Priya Patel")
        self.assertEqual(res_exact["status"], "exact")
        self.assertEqual(res_exact["contact"]["name"], "Priya Patel")

        # Ambiguous match (Rahul)
        res_ambig = resolve_contact("Rahul")
        self.assertEqual(res_ambig["status"], "AMBIGUOUS_CONTACT")
        self.assertTrue(res_ambig["requires_clarification"])
        self.assertIn("Rahul Sharma", res_ambig["matches"])

        # Pass-through unlisted contact name
        res_unk = resolve_contact("Unknown Person")
        self.assertEqual(res_unk["status"], "exact")
        self.assertEqual(res_unk["contact"]["name"], "Unknown Person")

    @patch("actions.whatsapp.whatsapp")
    def test_send_message_routes_to_whatsapp(self, mock_whatsapp):
        """Verify send_message tool delegates WhatsApp platform requests to actions.whatsapp."""
        mock_whatsapp.return_value = {"success": True, "message": "Done, Boss. Sent message."}
        res = send_message({"receiver": "Rahul Sharma", "message_text": "Hello", "platform": "whatsapp"})
        self.assertEqual(res, "Done, Boss. Sent message.")
        mock_whatsapp.assert_called_once_with(action="send_message", contact="Rahul Sharma", message="Hello", force_send=True)

    def test_whatsapp_send_requires_confirmation(self):
        """Verify force_send=False asks for user confirmation."""
        res = whatsapp_send_message("Rahul Sharma", "Test Msg", force_send=False)
        self.assertFalse(res["success"])
        self.assertTrue(res["requires_confirmation"])
        self.assertEqual(res["status"], "CONFIRMATION_REQUIRED")
        self.assertIn("ready for Rahul Sharma", res["message"])

    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": False, "status": "CDP_UNAVAILABLE", "message": "CDP port 9222 unavailable."})
    @patch("actions.whatsapp_automation.ensure_cdp_chrome")
    @patch("actions.whatsapp_automation.is_cdp_active", return_value=False)
    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome", return_value={"success": True})
    def test_whatsapp_send_cdp_unavailable_fallback(self, mock_open, mock_cdp, mock_ensure, mock_health):
        """Verify honest fallback report when CDP is unavailable (success=False, verified=False)."""
        res = whatsapp_send_message("Rahul Sharma", "Test Msg", force_send=True)
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "CDP_UNAVAILABLE")
        self.assertIn("Cannot send WhatsApp message automatically", res["message"])

    @patch("actions.whatsapp_automation.ensure_cdp_chrome")
    @patch("actions.whatsapp_automation.is_cdp_active", return_value=False)
    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome", return_value={"success": True})
    def test_whatsapp_read_cdp_unavailable_fallback(self, mock_open, mock_cdp, mock_ensure):
        """Verify honest fallback report when reading messages without CDP."""
        res = whatsapp_read_messages("Rahul Sharma")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "CDP_UNAVAILABLE")
        self.assertIn("CDP unavailable", res["error"])

    def test_sent_unverified_no_auto_resend(self):
        """Verify SENT_UNVERIFIED status reports success=False and does NOT trigger resend."""
        # Simulated unverified send response
        res = {
            "success": False,
            "action": "whatsapp_send",
            "platform": "whatsapp",
            "status": "SENT_UNVERIFIED",
            "contact": "Rahul Sharma",
            "message_text": "Test Msg",
            "message": "Boss, I attempted to send the message to Rahul Sharma, but I couldn't verify that WhatsApp delivered it.",
            "verified": False,
            "error": "DOM send verification unconfirmed"
        }
        self.assertFalse(res["success"])
        self.assertFalse(res["verified"])
        self.assertEqual(res["status"], "SENT_UNVERIFIED")

    def test_auto_reply_configuration_disabled_by_default(self):
        """Verify auto-reply is disabled by default and requires explicit configuration."""
        cfg = load_autoreply_config()
        self.assertFalse(cfg["enabled"])

        res = whatsapp_set_auto_reply(enabled=True, contact="Rahul Sharma", template="I am away.")
        self.assertTrue(res["success"])
        self.assertTrue(res["enabled"])
        self.assertIn("Rahul Sharma", res["allowed_contacts"])

        cfg2 = load_autoreply_config()
        self.assertTrue(cfg2["enabled"])
        self.assertIn("Rahul Sharma", cfg2["allowed_contacts"])

    @patch("actions.whatsapp_automation.open_url_in_yajat_chrome", return_value={"success": True})
    @patch("actions.whatsapp_automation.whatsapp_read_messages")
    @patch("actions.whatsapp_automation.whatsapp_reply")
    def test_auto_reply_loop_protection(self, mock_reply, mock_read, mock_open):
        """Verify loop protection: allowed contacts, direction filter, 5-min rate limit, processed ID tracking."""
        whatsapp_set_auto_reply(enabled=True, contact="Rahul Sharma", template="Away")

        # Mock unread message from allowed contact
        mock_read.return_value = {
            "success": True,
            "chats": [
                {
                    "contact": "Rahul Sharma",
                    "last_message": "Hey are you free?",
                    "time": "10:30 AM",
                    "direction": "incoming",
                    "unread": True
                }
            ]
        }
        mock_reply.return_value = {"success": True, "status": "SENT_VERIFIED", "verified": True}

        # First check -> should trigger reply
        res1 = whatsapp_check_auto_reply()
        self.assertTrue(res1["success"])
        self.assertTrue(res1["replied"])
        mock_reply.assert_called_once()

        # Immediate second check -> rate limited / processed ID -> should NOT reply again
        mock_reply.reset_mock()
        res2 = whatsapp_check_auto_reply()
        self.assertTrue(res2["success"])
        self.assertFalse(res2["replied"])
        mock_reply.assert_not_called()

    def test_whatsapp_call_confirmation(self):
        """Verify WhatsApp call initiation requires confirmation."""
        res = whatsapp_make_call("Rahul Sharma", call_type="voice", confirm_call=False)
        self.assertFalse(res["success"])
        self.assertTrue(res["requires_confirmation"])
        self.assertEqual(res["status"], "CONFIRMATION_REQUIRED")
        self.assertIn("requires confirmation", res["message"])

    def test_whatsapp_intent_routing(self):
        """Verify natural language patterns classify correctly into WhatsApp tools."""
        # Send
        intent_send = classify_intent("Papa ko WhatsApp par hello bhejo")
        self.assertEqual(intent_send["intent"], "WHATSAPP_MESSAGE")
        self.assertIn(intent_send["tool"], ["whatsapp", "whatsapp_send_message"])

        # Read / Read aloud
        intent_read = classify_intent("Papa ka message padh ke suna")
        self.assertEqual(intent_read["intent"], "WHATSAPP_READ")

        intent_read_en = classify_intent("Read my latest WhatsApp message")
        self.assertEqual(intent_read_en["intent"], "WHATSAPP_READ")

        # Reply
        intent_reply = classify_intent("Papa ko reply karo ki main 20 min mein aa raha hoon")
        self.assertEqual(intent_reply["intent"], "WHATSAPP_REPLY")

        # Call
        intent_call = classify_intent("Papa ko WhatsApp call karo")
        self.assertEqual(intent_call["intent"], "WHATSAPP_CALL")

        # End Call
        intent_end = classify_intent("Call kaat do")
        self.assertEqual(intent_end["intent"], "WHATSAPP_END_CALL")


if __name__ == "__main__":
    unittest.main()
