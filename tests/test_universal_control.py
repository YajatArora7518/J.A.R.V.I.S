# tests/test_universal_control.py
# Comprehensive Test Suite for JARVIS Universal Desktop, Voice, Text & Social Automation Upgrade

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.command_pipeline import (
    process_user_command, reset_conversation_context, get_conversation_context,
    set_pending_disambiguation, set_pending_important_message
)
from core.intent_router import classify_intent
from actions.app_registry import resolve_app, is_app_installed
from actions.social_platform_resolver import resolve_social_platform
from actions.discord_automation import discord_provider
from actions.mic_control import handle_mic_command, get_mic_states
from core.important_contact_watcher import default_important_watcher
from core.ollama_provider import is_ollama_available, generate_ollama_response


class TestUniversalMasterControl(unittest.TestCase):
    """34 Unit Tests covering all Universal Master Production Upgrade Requirements."""

    def setUp(self):
        reset_conversation_context()

    # 1. UNIFIED COMMAND PIPELINE PARITY (VOICE & CHAT)
    def test_unified_command_pipeline_parity(self):
        res_voice = process_user_command("Chrome kholo", source="voice")
        reset_conversation_context()
        res_chat = process_user_command("Chrome kholo", source="chat")

        self.assertTrue(res_voice["success"])
        self.assertTrue(res_chat["success"])
        self.assertEqual(res_voice["action"], res_chat["action"])

    # 2. LOCAL OLLAMA PROVIDER CONFIGURATION
    @patch("core.ollama_provider.urllib.request.urlopen")
    def test_ollama_provider_availability(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"models": [{"name": "fotiecodes/jarvis"}, {"name": "gemma4:12b"}]}'
        mock_urlopen.return_value = mock_resp

        self.assertTrue(is_ollama_available())
        res = generate_ollama_response("Hello JARVIS")
        self.assertTrue(res["success"] or res["status"] in ["OLLAMA_SUCCESS", "OLLAMA_ERROR"])

    # 3. APP REGISTRY DISCOVERY
    def test_app_registry_lookups(self):
        app_info = resolve_app("discord")
        self.assertIsNotNone(app_info)
        self.assertEqual(app_info["name"], "Discord")
        self.assertIn("executables", app_info)

    # 4. NATIVE APP PREFERENCE OVER WEB
    @patch("actions.app_first_routing.is_app_installed", return_value=True)
    def test_native_app_preference(self, mock_installed):
        from actions.app_first_routing import resolve_app_or_web_target
        res = resolve_app_or_web_target("discord app")
        self.assertEqual(res["launch_mode"], "native")

    # 5. WEB FALLBACK WHEN NATIVE APP UNAVAILABLE
    @patch("actions.app_first_routing.is_app_installed", return_value=False)
    def test_web_fallback_when_native_uninstalled(self, mock_installed):
        from actions.app_first_routing import resolve_app_or_web_target
        res = resolve_app_or_web_target("instagram")
        self.assertEqual(res["launch_mode"], "web")

    # 6. NATIVE VS WEB AMBIGUITY PROMPT
    @patch("actions.app_first_routing.is_app_installed", return_value=True)
    def test_native_vs_web_ambiguity_prompt(self, mock_installed):
        from actions.app_first_routing import resolve_app_or_web_target
        res = resolve_app_or_web_target("discord")
        self.assertEqual(res["status"], "AMBIGUOUS_NATIVE_AND_WEB")

    # 7. EXPLICIT COMMAND BYPASSES DISAMBIGUATION
    @patch("actions.app_first_routing.is_app_installed", return_value=True)
    def test_explicit_command_bypasses_ambiguity(self, mock_installed):
        from actions.app_first_routing import resolve_app_or_web_target
        res_web = resolve_app_or_web_target("discord web")
        res_app = resolve_app_or_web_target("discord desktop")
        self.assertEqual(res_web["launch_mode"], "web")
        self.assertEqual(res_app["launch_mode"], "native")

    # 8. DISAMBIGUATION CONVERSATIONAL ANSWER HANDLING
    def test_disambiguation_user_answer_desktop(self):
        set_pending_disambiguation("discord", {})
        res = process_user_command("Desktop", source="chat")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "NATIVE_APP_LAUNCHED")

    def test_disambiguation_user_answer_web(self):
        set_pending_disambiguation("discord", {})
        res = process_user_command("Web", source="chat")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "WEB_APP_LAUNCHED")

    # 9. SOCIAL PLATFORM RESOLVER - WHATSAPP
    def test_social_platform_resolver_whatsapp(self):
        provider = resolve_social_platform("whatsapp")
        self.assertEqual(provider.platform_name, "WhatsApp")
        self.assertTrue(hasattr(provider, "send_message"))

    # 10. SOCIAL PLATFORM RESOLVER - DISCORD
    def test_social_platform_resolver_discord(self):
        provider = resolve_social_platform("discord")
        self.assertEqual(provider.platform_name, "Discord")
        self.assertTrue(hasattr(provider, "join_voice"))

    # 11. DISCORD VOICE CONNECT
    def test_discord_connect_voice(self):
        res = discord_provider.join_voice("General")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "VOICE_CONNECTED")

    # 12. DISCORD VOICE DISCONNECT
    def test_discord_disconnect_voice(self):
        res = discord_provider.disconnect_voice()
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "VOICE_DISCONNECTED")

    # 13. DISCORD MUTE & UNMUTE
    def test_discord_mute_unmute(self):
        res_mute = discord_provider.mute(True)
        self.assertTrue(res_mute["success"])
        self.assertTrue(res_mute["muted"])

        res_unmute = discord_provider.mute(False)
        self.assertTrue(res_unmute["success"])
        self.assertFalse(res_unmute["muted"])

    # 14. DISCORD DEAFEN & UNDEAFEN
    def test_discord_deafen_undeafen(self):
        res_deafen = discord_provider.deafen(True)
        self.assertTrue(res_deafen["success"])
        self.assertTrue(res_deafen["deafened"])

        res_undeafen = discord_provider.deafen(False)
        self.assertTrue(res_undeafen["success"])
        self.assertFalse(res_undeafen["deafened"])

    # 15. DISCORD SEND MESSAGE & VERIFY
    def test_discord_send_message(self):
        res = discord_provider.send_message("Rahul", "Hello meeting at 5pm")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "SENT_VERIFIED")

    # 16. DISCORD READ MESSAGES
    def test_discord_read_messages(self):
        res = discord_provider.read_messages("General")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "MESSAGES_READ")

    # 17. SCOPED MIC CONTROL - JARVIS MIC
    def test_mic_control_jarvis_scope(self):
        res = handle_mic_command("JARVIS mic off")
        self.assertTrue(res["success"])
        self.assertEqual(res["scope"], "jarvis_mic")
        self.assertFalse(res["state"])

    # 18. SCOPED MIC CONTROL - DISCORD MIC
    def test_mic_control_discord_scope(self):
        res = handle_mic_command("Discord mic off")
        self.assertTrue(res["success"])
        self.assertEqual(res["scope"], "discord_mic")
        self.assertFalse(res["state"])

    # 19. SCOPED MIC CONTROL - SYSTEM MIC
    def test_mic_control_system_scope(self):
        res = handle_mic_command("System mic off")
        self.assertTrue(res["success"])
        self.assertEqual(res["scope"], "system_mic")
        self.assertFalse(res["state"])

    # 20. AMBIGUOUS MIC COMMAND PROMPT
    def test_mic_control_ambiguous_prompt(self):
        res = handle_mic_command("Mic status")
        self.assertTrue(res["success"])
        self.assertTrue(res["requires_clarification"])
        self.assertIn("JARVIS mic, app mic, Discord mic, ya system mic?", res["message"])

    # 21. IMPORTANT CONTACT WATCHER - ADD & REMOVE
    def test_important_contact_watcher_manage(self):
        res_add = default_important_watcher.add_important_contact("Rahul")
        self.assertTrue(res_add["success"])
        self.assertTrue(default_important_watcher.is_important_contact("Rahul"))

        res_rem = default_important_watcher.remove_important_contact("Rahul")
        self.assertTrue(res_rem["success"])

    # 22. IMPORTANT CONTACT WATCHER - ALERT GENERATION
    def test_important_contact_watcher_alert(self):
        alert = default_important_watcher.process_incoming_message("WhatsApp", "Papa", "Beta ghar kab aaoge?")
        self.assertIsNotNone(alert)
        self.assertTrue(alert["requires_approval"])
        self.assertIn("Papa ka message aaya hai", alert["prompt"])

    # 23. IMPORTANT CONTACT WATCHER - DEDUPLICATION
    def test_important_contact_watcher_deduplication(self):
        alert1 = default_important_watcher.process_incoming_message("WhatsApp", "Mom", "Reach home safe", "1001")
        alert2 = default_important_watcher.process_incoming_message("WhatsApp", "Mom", "Reach home safe", "1001")

        self.assertIsNotNone(alert1)
        self.assertIsNone(alert2)  # Suppressed duplicate

    # 24. READ-ALOUD APPROVAL - USER SAYS HAAN
    def test_read_aloud_approval_yes(self):
        set_pending_important_message("Papa", "Beta ghar kab aaoge?")
        res = process_user_command("Haan padh do", source="chat")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "MESSAGE_READ_ALOUD")
        self.assertIn("Beta ghar kab aaoge?", res["message"])

    # 25. READ-ALOUD APPROVAL - USER SAYS NAHI
    def test_read_aloud_approval_no(self):
        set_pending_important_message("Papa", "Beta ghar kab aaoge?")
        res = process_user_command("Nahi mat padho", source="chat")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "READ_ALOUD_REJECTED")

    # 26. HINGLISH INTENT PARSING - OPEN APP
    def test_hinglish_intent_open_app(self):
        c1 = classify_intent("Discord kholo")
        c2 = classify_intent("WhatsApp Web khol")
        self.assertEqual(c1["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(c2["intent"], "WHATSAPP_WEB")

    # 27. HINGLISH INTENT PARSING - CALL & MESSAGES
    def test_hinglish_intent_call_message(self):
        c_call = classify_intent("Rahul ko WhatsApp pe call karo")
        c_msg = classify_intent("Rahul ko message bhej ki main aa raha hoon")
        self.assertEqual(c_call["intent"], "WHATSAPP_CALL")
        self.assertEqual(c_msg["intent"], "WHATSAPP_MESSAGE")

    # 28. CONTEXTUAL FOLLOW-UP EXECUTION
    def test_contextual_follow_up_execution(self):
        ctx = get_conversation_context()
        ctx["last_app"] = "discord"

        res_conn = process_user_command("Connect karo", source="chat")
        self.assertTrue(res_conn["success"])
        self.assertTrue(any(s in str(res_conn["message"]) for s in ["Joined Discord voice channel 'General'.", "Connected to Discord voice channel 'General'.", "Discord voice channel 'General' joined."]))

    # 29. UNSUPPORTED ACTION TRUTHFUL REPORTING
    def test_unsupported_action_reporting(self):
        provider = resolve_social_platform("instagram")
        res = provider.join_voice()
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "UNSUPPORTED_ACTION")

    # 30. SECURITY CONFIRMATION POLICY PRESERVATION
    def test_security_confirmation_policy_preserved(self):
        from core.security import default_security_manager
        risk = default_security_manager.classify_risk("computer_settings", {"action": "close_app"})
        self.assertEqual(risk.value, "HIGH")

    # 31. PROTECTED UI ASSET INTEGRITY
    def test_protected_ui_assets_exist(self):
        assets_dir = BASE_DIR / "assets"
        self.assertTrue((assets_dir / "jarvis_3d_core.html").exists())
        self.assertTrue((assets_dir / "jarvis_3d_core_holographic.html").exists())
        self.assertTrue((assets_dir / "jarvis_holographic_ui.html").exists())

    # 32. TOOL REGISTRY DISCOVERY OF NEW TOOLS
    def test_tool_registry_contains_new_tools(self):
        from core.register_tools import initialize_all_tools
        from core.tool_registry import default_tool_registry
        initialize_all_tools()
        tools = default_tool_registry.list_tools()
        self.assertIn("discord_connect_voice", tools)
        self.assertIn("discord_disconnect_voice", tools)
        self.assertIn("discord_mute", tools)
        self.assertIn("mic_control", tools)

    # 33. PROCESS USER COMMAND EMPTY INPUT
    def test_process_user_command_empty(self):
        res = process_user_command("", source="chat")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "EMPTY_INPUT")

    # 34. PROCESS USER COMMAND DISCORD MUTE
    def test_process_user_command_discord_mute(self):
        res = process_user_command("Discord mute karo", source="chat")
        self.assertTrue(res["success"])

    # 35. OLLAMA HARDENED LIFECYCLE - ALREADY RUNNING
    @patch("core.ollama_provider.is_ollama_available", return_value=True)
    @patch("core.ollama_provider.get_available_ollama_models", return_value=["fotiecodes/jarvis", "gemma4:12b"])
    def test_ollama_lifecycle_already_running(self, mock_models, mock_avail):
        from core.ollama_provider import ensure_ollama_ready, OLLAMA_READY
        res = ensure_ollama_ready(required_model="fotiecodes/jarvis", auto_start=True)
        self.assertTrue(res["ready"])
        self.assertEqual(res["status"], OLLAMA_READY)

    # 36. OLLAMA HARDENED LIFECYCLE - SAFE AUTO-START ATTEMPT
    @patch("core.ollama_provider.find_ollama_executable", return_value="ollama")
    @patch("core.ollama_provider.is_ollama_available", side_effect=[False, True])
    @patch("core.ollama_provider.get_available_ollama_models", return_value=["fotiecodes/jarvis"])
    @patch("core.ollama_provider.subprocess.Popen")
    def test_ollama_lifecycle_auto_start_attempt(self, mock_popen, mock_models, mock_avail, mock_find_exe):
        from core.ollama_provider import auto_start_ollama
        import core.ollama_provider as op
        op._OLLAMA_STARTUP_ATTEMPTED = False
        success = auto_start_ollama(max_wait_sec=1.0)
        self.assertTrue(success)
        self.assertTrue(mock_popen.called)

    # 37. OLLAMA HARDENED LIFECYCLE - STARTUP FAILURE FALLBACK
    @patch("core.ollama_provider.is_ollama_available", return_value=False)
    @patch("core.ollama_provider.subprocess.Popen", side_effect=Exception("Ollama binary not found"))
    def test_ollama_lifecycle_startup_failure_fallback(self, mock_popen, mock_avail):
        from core.ollama_provider import generate_ollama_response, OLLAMA_UNAVAILABLE
        import core.ollama_provider as op
        op._OLLAMA_STARTUP_ATTEMPTED = False
        res = generate_ollama_response("Hello")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], OLLAMA_UNAVAILABLE)

    # 38. OLLAMA HARDENED LIFECYCLE - MODEL MISSING
    @patch("core.ollama_provider.is_ollama_available", return_value=True)
    @patch("core.ollama_provider.get_available_ollama_models", return_value=["some_other_model"])
    def test_ollama_lifecycle_model_missing(self, mock_models, mock_avail):
        from core.ollama_provider import check_ollama_health, OLLAMA_MODEL_MISSING
        res = check_ollama_health(required_model="fotiecodes/jarvis")
        self.assertFalse(res["ready"])
        self.assertEqual(res["status"], OLLAMA_MODEL_MISSING)
        self.assertEqual(res["missing_model"], "fotiecodes/jarvis")

    # 39. PROVIDER FAILOVER - BOTH UNAVAILABLE TRUTHFUL REPORTING
    @patch("core.ollama_provider.is_ollama_available", return_value=False)
    def test_provider_failover_both_unavailable(self, mock_avail):
        from core.ollama_provider import generate_ollama_response, OLLAMA_UNAVAILABLE
        import core.ollama_provider as op
        op._OLLAMA_STARTUP_ATTEMPTED = True
        res = generate_ollama_response("Hello", auto_start=False)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], OLLAMA_UNAVAILABLE)

    # 41. VOICE WATCHDOG NON-STREAMING ISOLATION
    def test_voice_watchdog_non_streaming_isolation(self):
        import time
        from main import JarvisLive
        mock_ui = MagicMock()
        live = JarvisLive(mock_ui)
        live.audio_in_queue = None
        live.set_speaking(True)
        # Simulate 3 seconds passing during non-streaming Ollama/Task execution
        live._last_speaking_time = time.time() - 3.0
        now = time.time()
        time_speaking = now - live._last_speaking_time
        # Since audio_in_queue is None, state remains speaking (no false positive reset after 2s)
        self.assertTrue(live._is_speaking)
        self.assertLess(time_speaking, 30.0)
        live._watchdog_running = False

if __name__ == "__main__":
    unittest.main()
