# tests/test_whatsapp_production_upgrade.py
# Targeted tests for JARVIS WhatsApp production upgrade
# Tests: Contact resolution, Hinglish parsing, intent routing, no-web-fallback

import sys
import os
import unittest
import re
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestContactResolution(unittest.TestCase):
    """Tests unified contact resolution from config/important_contacts.json with alias support."""

    def test_mumma_resolves_to_mom(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Mumma")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")

    def test_mummy_resolves_to_mom(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Mummy")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")

    def test_mom_resolves_to_mom(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Mom")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")

    def test_maa_resolves_to_mom(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Maa")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")

    def test_papa_resolves_to_papa(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Papa")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Papa")

    def test_dad_resolves_to_papa(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Dad")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Papa")

    def test_unknown_contact_passthrough(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Rahul")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Rahul")

    def test_empty_contact(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("")
        self.assertEqual(res["status"], "EMPTY")

    def test_case_insensitive(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("mumma")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")

    def test_mother_alias(self):
        from actions.windows_whatsapp_desktop_executor import resolve_contact_ambiguity
        res = resolve_contact_ambiguity("Mother")
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["contact"], "Mumma")


class TestHinglishParsing(unittest.TestCase):
    """Tests parse_whatsapp_command for all required Hinglish patterns."""

    def test_mumma_ko_hello_bhej(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko hello bhej")
        self.assertEqual(res["contact"], "Mumma")
        self.assertEqual(res["message"], "hello")

    def test_mumma_ko_hello_send_kar(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko hello send kar")
        self.assertEqual(res["contact"], "Mumma")
        self.assertEqual(res["message"], "hello")

    def test_mumma_ko_bol_hello(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko bol hello")
        self.assertEqual(res["contact"], "Mumma")
        self.assertEqual(res["message"], "hello")

    def test_mumma_ko_bol_kal_college_late(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko bol kal college late aaunga")
        self.assertEqual(res["contact"], "Mumma")
        self.assertIn("kal college late aaunga", res["message"])

    def test_mumma_ko_message_kar_hello(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko message kar hello")
        self.assertEqual(res["contact"], "Mumma")
        self.assertEqual(res["message"], "hello")

    def test_mumma_ko_ping_kar(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko ping kar")
        self.assertEqual(res["contact"], "Mumma")
        # ping kar may or may not have message body

    def test_existing_english_patterns_preserved(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Send Rahul a WhatsApp message saying I'll be late")
        self.assertEqual(res["contact"], "Rahul")
        self.assertIn("late", res["message"])

    def test_existing_hinglish_ko_pattern(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Rahul ko whatsapp pe message karo ki main 10 minute late hoon")
        self.assertEqual(res["contact"], "Rahul")
        self.assertIn("10 minute late", res["message"])

    def test_call_laga_pattern(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko call laga")
        self.assertEqual(res["contact"], "Mumma")

    def test_video_call_laga_pattern(self):
        from actions.whatsapp_automation import parse_whatsapp_command
        res = parse_whatsapp_command("Mumma ko video call laga")
        self.assertEqual(res["contact"], "Mumma")


class TestIntentRouting(unittest.TestCase):
    """Tests intent router correctly classifies WhatsApp commands."""

    def test_whatsapp_kholo_is_app(self):
        from core.intent_router import classify_intent
        res = classify_intent("WhatsApp kholo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_whatsapp_web_kholo_is_web(self):
        from core.intent_router import classify_intent
        res = classify_intent("WhatsApp Web kholo")
        self.assertEqual(res["intent"], "WHATSAPP_WEB")

    def test_mumma_ko_hello_bhej_is_message(self):
        from core.intent_router import classify_intent
        res = classify_intent("Mumma ko hello bhej")
        self.assertEqual(res["intent"], "WHATSAPP_MESSAGE")

    def test_mumma_ko_bol_hello_is_message(self):
        from core.intent_router import classify_intent
        res = classify_intent("Mumma ko bol hello")
        self.assertEqual(res["intent"], "WHATSAPP_MESSAGE")

    def test_mumma_ko_call_laga_is_call(self):
        from core.intent_router import classify_intent
        res = classify_intent("Mumma ko call laga")
        self.assertEqual(res["intent"], "WHATSAPP_CALL")

    def test_mumma_ko_video_call_is_video(self):
        from core.intent_router import classify_intent
        res = classify_intent("Mumma ko video call laga")
        self.assertEqual(res["intent"], "WHATSAPP_VIDEO_CALL")

    def test_bhai_whatsapp_kholo_strips_bhai(self):
        from core.intent_router import classify_intent
        res = classify_intent("Bhai WhatsApp kholo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_notepad_kholo_unchanged(self):
        from core.intent_router import classify_intent
        res = classify_intent("Notepad kholo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_google_kholo_unchanged(self):
        from core.intent_router import classify_intent
        res = classify_intent("Google kholo")
        # Google should route to website, not desktop app
        self.assertIn(res["intent"], ["KNOWN_WEBSITE", "WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_mumma_ko_message_kar_hello(self):
        from core.intent_router import classify_intent
        res = classify_intent("Mumma ko message kar hello")
        self.assertEqual(res["intent"], "WHATSAPP_MESSAGE")


class TestNoWebFallback(unittest.TestCase):
    """Tests that WhatsApp Desktop NEVER falls back to WhatsApp Web."""

    def test_whatsapp_open_tool_targets_desktop(self):
        from actions.whatsapp import whatsapp
        res = whatsapp(action="open")
        # Should target desktop, not web
        if res.get("target"):
            self.assertNotIn("web.whatsapp.com", str(res.get("target", "")))

    def test_whatsapp_web_explicit(self):
        from actions.whatsapp import whatsapp
        res = whatsapp(action="open", query="WhatsApp web kholo")
        # This one should target web because "web" is in the query
        # (just testing the routing logic, not actual launch)

    def test_intent_router_whatsapp_is_not_web(self):
        from core.intent_router import classify_intent
        res = classify_intent("WhatsApp kholo")
        # Must NOT be WHATSAPP_WEB
        self.assertNotEqual(res["intent"], "WHATSAPP_WEB")

    def test_intent_router_whatsapp_web_is_web(self):
        from core.intent_router import classify_intent
        res = classify_intent("WhatsApp Web kholo")
        self.assertEqual(res["intent"], "WHATSAPP_WEB")


class TestExistingFunctionality(unittest.TestCase):
    """Regression tests for existing JARVIS functionality."""

    def test_time_intent(self):
        from core.intent_router import classify_intent
        res = classify_intent("Time kya hai")
        self.assertEqual(res["intent"], "CURRENT_TIME")

    def test_chrome_open_intent(self):
        from core.intent_router import classify_intent
        res = classify_intent("Chrome kholo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_calculator_open_intent(self):
        from core.intent_router import classify_intent
        res = classify_intent("Calculator kholo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_notepad_open_intent(self):
        from core.intent_router import classify_intent
        res = classify_intent("Notepad open karo")
        self.assertIn(res["intent"], ["WINDOWS_APPLICATION", "OPEN_APPLICATION"])

    def test_stop_is_barge_in(self):
        from core.intent_router import classify_intent
        # "stop" should not be classified as something else
        res = classify_intent("stop")
        # It may be "OTHER" or "CANCEL" — just not a crash




class TestFollowupAndMultiStep(unittest.TestCase):
    """Tests pronoun follow-up, multi-step sequential execution, and honest verification."""

    def setUp(self):
        # These are command routing tests, never actual desktop sends/calls.
        desktop = patch('actions.whatsapp_desktop_dom.desktop_action', return_value={
            'success': False, 'verified': False, 'status': 'MOCK_DESKTOP', 'message': 'Mocked desktop boundary.',
            'execution_target': 'WINDOWS_INSTALLED_WHATSAPP_DESKTOP'})
        desktop.start()
        self.addCleanup(desktop.stop)
        from core.command_pipeline import reset_conversation_context
        reset_conversation_context()
        self.addCleanup(reset_conversation_context)

    def test_pronoun_followup_usko(self):
        """Old contact fields cannot authorize a send to an unverified recipient."""
        from core.command_pipeline import _CONVERSATION_CONTEXT, process_user_command
        _CONVERSATION_CONTEXT["last_contact"] = "Mom"
        _CONVERSATION_CONTEXT["last_app"] = "whatsapp"
        _CONVERSATION_CONTEXT["last_action"] = "whatsapp_send_message"

        with patch('core.command_pipeline.default_tool_registry.execute_tool') as execute:
            res = process_user_command("Ab usko bol main 10 minute mein aaunga", source="text")
        self.assertEqual(res['status'], 'CONTACT_CONTEXT_REQUIRED')
        execute.assert_not_called()

    def test_whatsapp_multistep_execution(self):
        """Isolated app + exact quoted-message sequence; no native account controls."""
        from core.command_pipeline import process_user_command
        from core.tool_registry import ToolResult
        fixture = ToolResult(True, 'whatsapp_send_message', 'fixture', verification={'verified': True})
        with patch('core.command_pipeline.default_tool_registry.execute_tool', return_value=fixture) as execute:
            res = process_user_command('WhatsApp kholo aur WhatsApp par Fixture ko message bhejo "hello"', source="text")
        self.assertTrue(res['verified'])
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(execute.call_args.args, ('whatsapp_send_message', {'contact': 'Fixture', 'message': 'hello', 'force_send': True}))

    def test_whatsapp_verification_distinguishes_desktop_and_web(self):
        """Test verify_whatsapp_launched distinguishes between Desktop and Web."""
        from core.verification import verify_whatsapp_launched
        res = verify_whatsapp_launched(timeout=1.0, target="desktop")
        self.assertIn("target_type", res)
        self.assertIn(res["target_type"], ["WHATSAPP_DESKTOP", "WHATSAPP_WEB", "UNKNOWN"])

    def test_notepad_typing_context_preserved(self):
        """Test 'Notepad kholo' followed by 'Isme hello type karo'."""
        from core.command_pipeline import _CONVERSATION_CONTEXT, process_user_command
        _CONVERSATION_CONTEXT["last_app"] = "notepad"
        from core.intent_router import classify_intent
        res = classify_intent("Isme hello type karo")
        self.assertEqual(res.get("intent"), "TYPING")
        self.assertEqual(res.get("tool"), "computer_control")

    def test_voice_call_dry_run_safety(self):
        """Test that voice call in dry-run mode does not crash and respects mock boundary."""
        from core.command_pipeline import process_user_command
        res = process_user_command("Mumma ko call laga", source="text")
        self.assertEqual(res.get("recipient"), "Mumma")
        self.assertEqual(res.get("action"), "whatsapp_voice_call")
        self.assertIn("execution_target", res)

    def test_video_call_dry_run_safety(self):
        """Test that video call in dry-run mode does not crash and respects mock boundary."""
        from core.command_pipeline import process_user_command
        res = process_user_command("Mumma ko video call laga", source="text")
        self.assertEqual(res.get("recipient"), "Mumma")
        self.assertEqual(res.get("action"), "whatsapp_video_call")
        self.assertIn("execution_target", res)


if __name__ == "__main__":
    unittest.main()
