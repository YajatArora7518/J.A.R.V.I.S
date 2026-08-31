# tests/test_runtime_routing_fixes.py
# Comprehensive Regression & Contract Verification Test Suite for JARVIS Runtime Fixes

import unittest
from unittest.mock import patch, MagicMock

from core.register_tools import initialize_all_tools
from core.tool_registry import default_tool_registry
from core.intent_router import classify_intent
from core.command_pipeline import process_user_command, reset_conversation_context, get_conversation_context
from core.safe_calculator import calculate, normalize_math_query
from actions.open_app import open_app, open_app_structured
from actions.computer_control import computer_control
from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor, WindowsWhatsAppDesktopExecutor
from actions.screen_processor import screen_process, analyze_screen_vision


class TestRuntimeRoutingFixes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialize_all_tools()

    def setUp(self):
        reset_conversation_context()

    # -------------------------------------------------------------
    # 1. WhatsApp Desktop Direct Launch Tests
    # -------------------------------------------------------------
    def test_whatsapp_desktop_executor_method_exists(self):
        """Verify WindowsWhatsAppDesktopExecutor has focus_installed_whatsapp_desktop method."""
        self.assertTrue(hasattr(windows_whatsapp_desktop_executor, "focus_installed_whatsapp_desktop"))
        self.assertTrue(callable(getattr(windows_whatsapp_desktop_executor, "focus_installed_whatsapp_desktop")))

    def test_whatsapp_open_app_structured_no_attribute_error(self):
        """Verify open_app_structured('WhatsApp') executes without AttributeError."""
        with patch.object(windows_whatsapp_desktop_executor, "focus_installed_whatsapp_desktop", return_value=(True, "Focused existing WhatsApp window")):
            res = open_app_structured("WhatsApp")
            self.assertTrue(res.get("success"))
            self.assertEqual(res.get("app"), "WhatsApp")
            self.assertEqual(res.get("mode"), "desktop")
            self.assertIn("Focused", res.get("message"))

    def test_whatsapp_open_app_tool_handler(self):
        """Verify open_app tool handler returns structured response for WhatsApp."""
        with patch.object(windows_whatsapp_desktop_executor, "focus_installed_whatsapp_desktop", return_value=(True, "Launched WhatsApp Desktop")):
            res = open_app(parameters={"app_name": "WhatsApp"})
            self.assertTrue(res.get("success"))
            self.assertIn("WhatsApp", res.get("message"))

    # -------------------------------------------------------------
    # 2. Computer Control Contract & Keyword Arguments Tests
    # -------------------------------------------------------------
    def test_computer_control_with_speak_via_tool_registry(self):
        """Verify default_tool_registry executes computer_control with speak kwarg without TypeError."""
        dummy_speak = MagicMock()
        with patch("actions.computer_control._hotkey", return_value="Hotkey: win"):
            res = default_tool_registry.execute_tool(
                "computer_control",
                {"action": "hotkey", "keys": "win"},
                speak=dummy_speak
            )
            self.assertTrue(res.success)
            self.assertIn("Hotkey", res.message)

    def test_computer_control_direct_invocations(self):
        """Verify direct keyword invocations of computer_control work without TypeError."""
        with patch("actions.computer_control._hotkey", return_value="Hotkey: win"):
            res1 = computer_control(action="hotkey", keys="win")
            self.assertEqual(res1, "Hotkey: win")

        with patch("actions.computer_control._type", return_value="Typed: WhatsApp"):
            res2 = computer_control(action="type", text="WhatsApp")
            self.assertEqual(res2, "Typed: WhatsApp")

        with patch("actions.computer_control._press", return_value="Pressed: enter"):
            res3 = computer_control(action="key", key="enter")
            self.assertEqual(res3, "Pressed: enter")

    # -------------------------------------------------------------
    # 3. Desktop Application Direct Launch Tests
    # -------------------------------------------------------------
    def test_desktop_app_intent_classification(self):
        """Verify natural desktop launch variations map to WINDOWS_APPLICATION / open_app."""
        apps_to_test = [
            ("Open Google Chrome", "google chrome"),
            ("Launch Chrome", "chrome"),
            ("Start Chrome", "chrome"),
            ("Open WhatsApp", "whatsapp"),
            ("Launch WhatsApp", "whatsapp"),
            ("Start WhatsApp Desktop", "whatsapp"),
            ("Open Spotify", "spotify"),
            ("Launch Discord", "discord"),
            ("Open VS Code", "vs code"),
            ("Open Settings", "settings"),
        ]
        for query, expected_target in apps_to_test:
            clf = classify_intent(query)
            self.assertEqual(clf.get("intent"), "WINDOWS_APPLICATION", f"Failed on {query}")
            self.assertEqual(clf.get("tool"), "open_app", f"Failed tool on {query}")
            self.assertIn(expected_target, clf.get("target", "").lower(), f"Target mismatch on {query}")

    def test_settings_direct_launch_completed(self):
        """Verify Settings direct launch resolves and completes without computer_control."""
        res = open_app_structured("Settings")
        self.assertTrue(res.get("success"))
        self.assertIn("Settings", res.get("app"))

    # -------------------------------------------------------------
    # 4. Safe Computation Intent & AST Evaluator Tests
    # -------------------------------------------------------------
    def test_safe_calculator_core_evaluator(self):
        """Verify AST-based math evaluations return exact formatted numerical values."""
        cases = [
            ("25 * 37", 925),
            ("984 / 12", 82),
            ("2 ^ 10", 1024),
            ("sqrt(144)", 12),
            ("17% of 850", 144.5),
            ("125 + 378", 503),
            ("50 - 18", 32),
            ("100 // 3", 33),
            ("10 % 3", 1),
            ("abs(-42)", 42),
            ("round(3.14159, 2)", 3.14),
        ]
        for query, expected in cases:
            res = calculate(query)
            self.assertTrue(res.get("success"), f"Calculation failed for: {query}")
            self.assertEqual(res.get("result"), expected, f"Result mismatch for {query}: got {res.get('result')}")

    def test_computation_intent_routing(self):
        """Verify computational queries classify as COMPUTATION."""
        queries = [
            "Calculate 25 times 37",
            "What is 984 divided by 12?",
            "Calculate 2^10",
            "What is the square root of 144?",
            "Compute 17 percent of 850",
            "What's 125 + 378?",
            "25 * 37",
            "sqrt(144)",
            "17% of 850",
            "125 + 378"
        ]
        for q in queries:
            clf = classify_intent(q)
            self.assertEqual(clf.get("intent"), "COMPUTATION", f"Failed intent for: {q}")
            self.assertEqual(clf.get("tool"), "safe_calculator", f"Failed tool for: {q}")

    def test_computation_command_pipeline_execution(self):
        """Verify command pipeline executes pure computation without GUI automation or opening Calculator."""
        res = process_user_command("Calculate 25 times 37", source="voice")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("intent"), "COMPUTATION")
        self.assertEqual(res.get("action"), "computation")
        self.assertIn("925", res.get("message"))

    def test_safe_calculator_rejects_unsafe_code(self):
        """Verify AST safe evaluator rejects arbitrary python statements, imports, and builtins."""
        unsafe_payloads = [
            "__import__('os').system('dir')",
            "open('config/api_keys.json').read()",
            "eval('2 + 2')",
            "exec('import sys')",
            "globals()",
        ]
        for payload in unsafe_payloads:
            res = calculate(payload)
            self.assertFalse(res.get("success"), f"Unsafe payload was not rejected: {payload}")

    # -------------------------------------------------------------
    # 5. Screen Analysis & Vision Intent Tests
    # -------------------------------------------------------------
    def test_screen_analysis_intent_classification(self):
        """Verify screen observation commands map to SCREEN_ANALYSIS."""
        queries = [
            "Screen dekh",
            "Screen analyze karo",
            "What's on my screen?",
            "Screen pe kya hai?",
            "Look at my screen",
            "Can you see my screen?",
            "Analyze my screen",
            "Ek bar screen dekh"
        ]
        for q in queries:
            clf = classify_intent(q)
            self.assertEqual(clf.get("intent"), "SCREEN_ANALYSIS", f"Failed intent for: {q}")
            self.assertEqual(clf.get("tool"), "screen_process", f"Failed tool for: {q}")

    def test_screen_analysis_execution_and_observation(self):
        """Verify screen_process executes screenshot capture, vision reasoning, and structured return."""
        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "Boss, VS Code mein Python code visible hai. Kya main code structure inspect karun?"

        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_gemini_resp
            mock_client_cls.return_value = mock_client

            res = analyze_screen_vision("Screen dekh")
            self.assertTrue(res.get("success"))
            self.assertTrue(res.get("screenshot_available"))
            self.assertIn("VS Code", res.get("observation"))
            self.assertEqual(res.get("confidence"), 1.0)

    # -------------------------------------------------------------
    # 6. Multi-turn Screen Context Resolution Tests
    # -------------------------------------------------------------
    def test_screen_conversation_multiturn_context(self):
        """Verify multi-turn screen conversation preserves context when user answers 'Haan'."""
        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "Boss, VS Code mein AttributeError dikh raha hai. Kya root cause identify karun?"

        with patch("google.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_gemini_resp
            mock_client_cls.return_value = mock_client

            # Turn 1: Screen dekh
            res1 = process_user_command("Screen dekh", source="voice")
            self.assertTrue(res1.get("success"))
            self.assertEqual(res1.get("intent"), "SCREEN_ANALYSIS")
            self.assertIsNotNone(get_conversation_context().get("pending_screen_context"))

            # Turn 2: User responds "Haan"
            res2 = process_user_command("Haan", source="voice")
            self.assertTrue(res2.get("success"))
            self.assertEqual(res2.get("action"), "screen_followup_acknowledged")
            self.assertIn("inspect kar raha hoon", res2.get("message"))
            # Context consumed
            self.assertIsNone(get_conversation_context().get("pending_screen_context"))

    # -------------------------------------------------------------
    # 7. Tool Registry 62 Tools Invariance Test
    # -------------------------------------------------------------
    def test_tool_registry_preserves_62_tools(self):
        """Verify exactly 62 tools remain registered in default_tool_registry."""
        tools = default_tool_registry.list_tools()
        self.assertEqual(len(tools), 62)


if __name__ == "__main__":
    unittest.main()
