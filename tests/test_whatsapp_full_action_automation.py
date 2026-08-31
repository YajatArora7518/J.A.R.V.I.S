# tests/test_whatsapp_full_action_automation.py
# Comprehensive Test Suite for Full WhatsApp Action Automation (Calls, Messages, Open Chat, Search, Security)

import sys
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.intent_router import classify_intent
from core.tool_registry import default_tool_registry
from actions.open_app import open_app_structured
from actions.whatsapp import (
    whatsapp,
    whatsapp_open_tool,
    whatsapp_search_contact_tool,
    whatsapp_open_chat_tool,
    whatsapp_send_message_tool,
    whatsapp_reply_tool,
    whatsapp_voice_call_tool,
    whatsapp_video_call_tool,
    whatsapp_read_messages_tool,
    resolve_whatsapp_contact
)
from actions.whatsapp_automation import (
    whatsapp_open_chat,
    whatsapp_search_contact,
    whatsapp_send_message,
    whatsapp_make_call,
    _async_whatsapp_call_cdp,
    _async_whatsapp_send,
    _async_whatsapp_open_chat_cdp
)


import core.register_tools

class TestWhatsAppFullActionAutomation(unittest.TestCase):

    def setUp(self):
        core.register_tools.initialize_all_tools()

    # 1. TOOL REGISTRY DISCOVERY
    def test_whatsapp_tool_registry_registration(self):
        registered_tools = default_tool_registry.list_tools()
        required_tools = [
            "whatsapp",
            "whatsapp_open",
            "whatsapp_search_contact",
            "whatsapp_open_chat",
            "whatsapp_send_message",
            "whatsapp_reply",
            "whatsapp_voice_call",
            "whatsapp_video_call",
            "whatsapp_read_messages"
        ]
        for t in required_tools:
            self.assertIn(t, registered_tools, f"Tool '{t}' must be registered in ToolRegistry.")

    # 2. INTENT CLASSIFICATION DISAMBIGUATION
    def test_intent_classification_whatsapp_actions(self):
        # Open commands
        self.assertEqual(classify_intent("Open WhatsApp")["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(classify_intent("Open WhatsApp Web")["intent"], "WHATSAPP_WEB")
        self.assertEqual(classify_intent("WhatsApp Web kholo")["intent"], "WHATSAPP_WEB")

        # Voice call commands
        self.assertEqual(classify_intent("Call Rahul on WhatsApp")["intent"], "WHATSAPP_CALL")
        self.assertEqual(classify_intent("Rahul ko WhatsApp pe call karo")["intent"], "WHATSAPP_CALL")

        # Video call commands
        self.assertEqual(classify_intent("Video call Rahul on WhatsApp")["intent"], "WHATSAPP_VIDEO_CALL")
        self.assertEqual(classify_intent("Rahul ko WhatsApp pe video call karo")["intent"], "WHATSAPP_VIDEO_CALL")

        # Messaging commands
        self.assertEqual(classify_intent("Message Rahul on WhatsApp saying I'll be late")["intent"], "WHATSAPP_MESSAGE")
        self.assertEqual(classify_intent("Rahul ko WhatsApp pe message karo ki main 10 min late hoon")["intent"], "WHATSAPP_MESSAGE")

        # Open chat commands
        self.assertEqual(classify_intent("Rahul ki WhatsApp chat kholo")["intent"], "WHATSAPP_OPEN_CHAT")
        self.assertEqual(classify_intent("open WhatsApp chat with Rahul")["intent"], "WHATSAPP_OPEN_CHAT")

    # 3. CONTACT SAFETY & AMBIGUITY
    def test_contact_resolution_safety(self):
        res = resolve_whatsapp_contact("Rahul")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "AMBIGUOUS_CONTACT")
        self.assertTrue(res.get("requires_clarification"))

        res_single = resolve_whatsapp_contact("Priya")
        self.assertTrue(res_single["success"])
        self.assertEqual(res_single["contact"]["name"], "Priya Patel")

    # 4. SECURITY — NO CONFIRMATION BYPASS
    def test_security_manager_authoritative(self):
        # Send message requires force_send=True
        msg_res = whatsapp_send_message("Priya Patel", "Test security", force_send=False)
        self.assertFalse(msg_res["success"])
        self.assertEqual(msg_res["status"], "CONFIRMATION_REQUIRED")
        self.assertTrue(msg_res.get("requires_confirmation"))

        # Voice call requires confirm_call=True
        call_res = whatsapp_make_call("Priya Patel", call_type="voice", confirm_call=False)
        self.assertFalse(call_res["success"])
        self.assertEqual(call_res["status"], "CONFIRMATION_REQUIRED")
        self.assertTrue(call_res.get("requires_confirmation"))

        # Video call requires confirm_call=True
        vcall_res = whatsapp_make_call("Priya Patel", call_type="video", confirm_call=False)
        self.assertFalse(vcall_res["success"])
        self.assertEqual(vcall_res["status"], "CONFIRMATION_REQUIRED")
        self.assertTrue(vcall_res.get("requires_confirmation"))

    # 5. VOICE CALL EXECUTION & HONEST UNEXPOSED CONTROLS REPORTING
    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": True, "status": "WHATSAPP_READY", "message": "CDP endpoint active."})
    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch("actions.whatsapp_automation.browser_automation_engine")
    def test_voice_call_dom_unexposed_controls_reporting(self, mock_engine, mock_cdp, mock_health):
        mock_page = MagicMock()
        # Mock selector wait & find call button as None (unexposed in browser tab)
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        mock_page.query_selector = AsyncMock(return_value=None)

        async def mock_get_page(*args, **kwargs):
            return mock_page

        mock_engine.get_or_open_page = mock_get_page
        mock_engine.run = lambda coro: asyncio.run(coro)

        res = whatsapp_make_call("Priya Patel", call_type="voice", confirm_call=True)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "CALL_UNAVAILABLE")
        self.assertIn("call controls are unexposed", res["message"].lower())
        self.assertFalse(res["verified"])

    # 6. VIDEO CALL EXECUTION & HONEST UNEXPOSED CONTROLS REPORTING
    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": True, "status": "WHATSAPP_READY", "message": "CDP endpoint active."})
    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch("actions.whatsapp_automation.browser_automation_engine")
    def test_video_call_dom_unexposed_controls_reporting(self, mock_engine, mock_cdp, mock_health):
        mock_page = MagicMock()
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        mock_page.query_selector = AsyncMock(return_value=None)

        async def mock_get_page(*args, **kwargs):
            return mock_page

        mock_engine.get_or_open_page = mock_get_page
        mock_engine.run = lambda coro: asyncio.run(coro)

        res = whatsapp_make_call("Priya Patel", call_type="video", confirm_call=True)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "VIDEO_CALL_UNAVAILABLE")
        self.assertIn("video call controls are unexposed", res["message"].lower())
        self.assertFalse(res["verified"])

    # 7. VOICE CALL SUCCESS DOM VERIFICATION
    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": True, "status": "WHATSAPP_READY", "message": "CDP endpoint active."})
    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch("actions.whatsapp_automation.browser_automation_engine")
    def test_voice_call_verified_success(self, mock_engine, mock_cdp, mock_health):
        mock_page = MagicMock()
        mock_btn = MagicMock()
        mock_btn.click = MagicMock(side_effect=lambda: asyncio.sleep(0))

        mock_call_ui = MagicMock()

        async def mock_query(sel):
            if "phone" in sel or "voice" in sel or "call" in sel:
                return mock_btn
            if "End call" in sel or "call-end" in sel:
                return mock_call_ui
            return None

        mock_page.query_selector = mock_query

        async def mock_get_page(*args, **kwargs):
            return mock_page

        mock_engine.get_or_open_page = mock_get_page
        mock_engine.run = lambda coro: asyncio.run(coro)

        res = whatsapp_make_call("Priya Patel", call_type="voice", confirm_call=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "CALL_INITIATED")
        self.assertTrue(res["verified"])

    # 8. OPEN CHAT ACTION
    @patch("actions.whatsapp_automation.check_cdp_health", return_value={"ready": True, "status": "WHATSAPP_READY", "message": "CDP endpoint active."})
    @patch("actions.browser_automation.is_cdp_active", return_value=True)
    @patch("actions.whatsapp_automation.browser_automation_engine")
    def test_whatsapp_open_chat_verified(self, mock_engine, mock_cdp, mock_health):
        mock_page = MagicMock()
        mock_header = MagicMock()

        async def mock_inner_text():
            return "Priya Patel"

        mock_header.inner_text = mock_inner_text

        async def mock_wait(sel, **kwargs):
            return MagicMock()

        mock_page.wait_for_selector = mock_wait

        async def mock_query(sel):
            if "#main header" in sel:
                return mock_header
            return MagicMock()

        mock_page.query_selector = mock_query

        async def mock_get_page(*args, **kwargs):
            return mock_page

        mock_engine.get_or_open_page = mock_get_page
        mock_engine.run = lambda coro: asyncio.run(coro)

        res = whatsapp_open_chat("Priya Patel")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "CHAT_OPENED")
        self.assertTrue(res["verified"])

    # 9. DISCRETE TOOL REGISTRY DISPATCH
    def test_tool_registry_whatsapp_execution(self):
        res = default_tool_registry.execute_tool("whatsapp_search_contact", {"query": "Priya"})
        self.assertTrue(res.success)
        self.assertEqual(res.data["contact"]["name"], "Priya Patel")


if __name__ == "__main__":
    unittest.main()
