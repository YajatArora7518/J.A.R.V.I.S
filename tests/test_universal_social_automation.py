# tests/test_universal_social_automation.py
# Automated Test Suite for Universal Social Media & Communication Automation

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.service_discovery import universal_service_registry, discover_communication_services
from actions.notification_engine import notification_aggregator, ImportanceFilter
from actions.universal_messaging import send_universal_message, resolve_recipient_contact
from actions.universal_calls_sms import make_call, send_sms_message
from actions.mobile_pc_gateway import mobile_pc_gateway
from actions.social_actions import execute_social_action
from core.intent_router import classify_intent
from core.tool_registry import default_tool_registry


class TestUniversalSocialAutomation(unittest.TestCase):

    def test_01_service_discovery(self):
        """Verify dynamic discovery of Windows, Chrome, and Mobile services."""
        discovered = universal_service_registry.discover_services()
        self.assertGreater(len(discovered), 0)
        self.assertIn("whatsapp", discovered)
        
        wa_service = discovered["whatsapp"]
        self.assertTrue(wa_service.installed)
        self.assertIn("SEND_MESSAGE", wa_service.capabilities)

        summary_res = discover_communication_services()
        self.assertTrue(summary_res.get("success"))
        self.assertIn("services_count", summary_res)

    def test_02_importance_filter_and_notification_aggregator(self):
        """Verify priority classification (HIGH, MEDIUM, LOW) and notification aggregation."""
        high_prio = ImportanceFilter.classify("whatsapp", "Rahul", "Missed call", "Call me back asap urgent")
        self.assertEqual(high_prio, "HIGH")

        low_prio = ImportanceFilter.classify("instagram", "System", "Promo", "50% off discount update available")
        self.assertEqual(low_prio, "LOW")

        notif = notification_aggregator.add_notification(
            service_id="discord",
            service_name="Discord",
            sender="Aman",
            title="Direct Message",
            message="Join the call now",
            platform="windows"
        )
        self.assertEqual(notif.sender, "Aman")

        summary = notification_aggregator.get_summary(only_important=True)
        self.assertTrue(summary.get("success"))
        self.assertGreater(summary.get("count"), 0)

    def test_03_recipient_ambiguity_resolution(self):
        """Verify that ambiguous contacts trigger clarification prompts."""
        res = resolve_recipient_contact("Rahul")
        self.assertEqual(res.get("status"), "AMBIGUOUS")
        self.assertIn("Which one do you mean?", res.get("message"))

        res_send = send_universal_message("Rahul", "Hello")
        self.assertTrue(res_send.get("ambiguous_recipient"))

    def test_04_no_fake_success_guardrail(self):
        """Verify that unconfirmed message sends return honest failure message."""
        res = send_universal_message("NonExistentContact9999", "Test Message", platform="generic_app")
        # Unconfirmed generic app send should fail verification or report inability to confirm
        self.assertFalse(res.get("verified"))

    def test_05_multilingual_intent_classification(self):
        """Verify English, Hindi, and Hinglish intent classification."""
        intent_1 = classify_intent("Which communication apps do I have available")
        self.assertEqual(intent_1.get("tool"), "service_discovery")

        intent_2 = classify_intent("Check my unread messages")
        self.assertEqual(intent_2.get("tool"), "read_notifications")

        intent_3 = classify_intent("Who called me")
        self.assertEqual(intent_3.get("tool"), "read_call_log")

    def test_06_mobile_pc_gateway_offline_handling(self):
        """Verify offline device reporting in cross-device gateway."""
        # Route to phone when offline
        res = mobile_pc_gateway.route_cross_device_action("pc", "phone", "send_sms", {"recipient": "Rahul", "message": "Test"})
        if not mobile_pc_gateway.is_android_online():
            self.assertTrue(res.get("device_offline"))
            self.assertIn("offline", res.get("message").lower())

    def test_07_social_actions(self):
        """Verify execution of social engagement actions (like, media control)."""
        res_yt = execute_social_action("youtube", "play_media", target="Lo-fi beats")
        self.assertTrue(res_yt.get("success"))
        self.assertEqual(res_yt.get("status"), "SUPPORTED")

    def test_08_tool_registry_integration(self):
        """Verify that new universal tools are registered in ToolRegistry."""
        from core.register_tools import initialize_all_tools
        initialize_all_tools()
        registered_names = list(default_tool_registry._tools.keys())
        self.assertIn("service_discovery", registered_names)
        self.assertIn("read_notifications", registered_names)
        self.assertIn("make_call", registered_names)
        self.assertIn("read_call_log", registered_names)
        self.assertIn("send_sms", registered_names)
        self.assertIn("read_sms", registered_names)
        self.assertIn("social_action", registered_names)
        self.assertIn("mobile_gateway", registered_names)
        self.assertIn("unified_connection_status", registered_names)

    def test_09_unified_connection_status(self):
        """Verify unified connection status diagnostic handler."""
        from actions.mobile_pc_gateway import get_unified_connection_status
        res = get_unified_connection_status()
        self.assertTrue(res.get("success"))
        self.assertIn("WINDOWS:", res.get("message"))
        self.assertIn("ANDROID:", res.get("message"))


if __name__ == "__main__":
    unittest.main()
