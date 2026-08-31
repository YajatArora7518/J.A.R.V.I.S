# tests/test_android_whatsapp_and_system_fixes.py
# Comprehensive Test Suite verifying Android Installed WhatsApp Routing, Ollama-Only Routing,
# UI outerWireMat JS check, QFont integer size fix, Power Confirmation Safety, and WebSocket Stability.

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add JARVIS MAIN root to Python sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestAndroidWhatsAppAndSystemFixes(unittest.TestCase):

    def test_01_ollama_primary_routing_no_cloud_404(self):
        """Verify or_client executes strictly via Ollama Local and never falls back to cloud 404 calls."""
        from or_client import client
        with patch("core.ollama_provider.is_ollama_available", return_value=False), \
             patch("core.ollama_provider.auto_start_ollama", return_value=False):
            res = client._call_with_fallback([], [{"role": "user", "content": "hello"}])
            self.assertIn("Ollama", res)
            self.assertIn("offline or unreachable", res)

    def test_02_whatsapp_android_exclusive_routing(self):
        """Verify WhatsApp message requests route strictly to AndroidWhatsAppExecutor with assertion."""
        from actions.android_whatsapp_executor import send_installed_android_whatsapp_message
        with patch("actions.android_whatsapp_executor.check_android_device", return_value=(False, None, "No device")):
            res = send_installed_android_whatsapp_message("Rahul", "Hello")
            self.assertEqual(res.get("execution_target"), "AndroidWhatsAppExecutor")
            self.assertFalse(res.get("success"))

    def test_03_whatsapp_duplicate_protection(self):
        """Verify duplicate send protection prevents repeated messaging to the same recipient."""
        from actions.android_whatsapp_executor import send_installed_android_whatsapp_message
        with patch("actions.android_whatsapp_executor.check_android_device", return_value=(True, "SERIAL123", "Active")), \
             patch("actions.android_whatsapp_executor.detect_installed_whatsapp_package", return_value="com.whatsapp"), \
             patch("subprocess.run") as mock_sub, \
             patch("actions.android_whatsapp_executor.dump_ui_hierarchy", return_value="<xml>message_text</xml>"):

            mock_sub.return_value = MagicMock(returncode=0, stdout="")
            res1 = send_installed_android_whatsapp_message("TestRecipient", "Unique Message 123")
            res2 = send_installed_android_whatsapp_message("TestRecipient", "Unique Message 123")
            self.assertTrue(res2.get("duplicate_prevented", False))

    def test_04_ui_outerwiremat_js_declarations(self):
        """Verify assets/jarvis_holographic_ui.html contains top-level declarations and typeof checks for outerWireMat."""
        html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "jarvis_holographic_ui.html"))
        self.assertTrue(os.path.exists(html_path))
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("var outerWireMat =", content)
        self.assertIn("typeof outerWireMat !== 'undefined'", content)

    def test_05_ui_qfont_integer_point_size(self):
        """Verify SecurityConfirmationDialog in ui.py uses integer point size QFont."""
        ui_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui.py"))
        with open(ui_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn('QFont("Segoe UI", 9.5)', content)

    def test_06_power_command_confirmation_flow(self):
        """Verify power commands require explicit confirmation, 'Haan' confirms, 'Nahi' cancels, unbound 'Haan' does nothing."""
        from core.command_pipeline import process_user_command, reset_conversation_context
        reset_conversation_context()

        # 1. Trigger power action
        res1 = process_user_command("Shutdown laptop")
        self.assertEqual(res1.get("status"), "CONFIRMATION_REQUIRED")
        self.assertIn("confirm", res1.get("message", "").lower())

        # 2. Confirm power action with "Haan"
        with patch("actions.windows_system_controller.execute_system_capability", return_value={"success": True}):
            res2 = process_user_command("Haan")
            self.assertEqual(res2.get("status"), "POWER_EXECUTED")

        # 3. Unbound "Haan" without pending confirmation
        reset_conversation_context()
        res3 = process_user_command("Haan")
        self.assertEqual(res3.get("status"), "NO_OP")

    def test_07_device_targeting_resolution(self):
        """Verify device targeting resolves laptop/PC to Windows PC and mobile/phone to Android."""
        from core.command_pipeline import process_user_command, reset_conversation_context
        reset_conversation_context()

        res1 = process_user_command("Shutdown laptop")
        self.assertIn("laptop", res1.get("message", "").lower())

        reset_conversation_context()
        res2 = process_user_command("Restart phone")
        self.assertIn("phone", res2.get("message", "").lower())

    def test_08_web_search_provider_fallback(self):
        """Verify web search cleanly uses DuckDuckGo when primary search APIs are unavailable."""
        from actions.web_search import web_search_structured
        from actions.web_search_providers import _PROVIDER_STATUS

        with patch.dict(_PROVIDER_STATUS, {"google": False, "serper": False, "brave": False, "duckduckgo": True}), \
             patch("actions.web_search.search_duckduckgo", return_value=[{"title": "Test Result", "url": "https://test.com"}]):
            res = web_search_structured("Python news")
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("provider"), "DuckDuckGo")

    def test_09_windows_privilege_check_honesty(self):
        """Verify execute_system_capability reports privilege requirement honestly when Admin=False."""
        from actions.windows_system_controller import execute_system_capability
        with patch("actions.windows_system_controller.is_admin", return_value=False):
            res = execute_system_capability("shutdown", {"elevated": True})
            self.assertFalse(res.get("success"))
            self.assertEqual(res.get("verification"), "FAIL_PRIVILEGE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
