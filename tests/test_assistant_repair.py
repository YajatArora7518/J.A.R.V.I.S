"""Offline regressions: no real apps, microphones, sends or calls."""
import asyncio
import json
import os
import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from actions.social_chat import parse_social_command, execute_social_chat
from config import get_api_key
from core.ai_policy import is_cloud_ai_allowed
from core.intent_router import classify_intent
from core.reminder_parser import parse_reminder_query
from core.security import RiskLevel
from core.tool_registry import Tool, ToolResult


@pytest.mark.parametrize("query,platform,action,recipient,message", [
    ("Discord pe Aman ko hello bhej", "discord", "send", "Aman", "hello"),
    ("Aman ko discord pe message bhejo kal milte hain", "discord", "send", "Aman", "kal milte hain"),
    ("Send to aman on discord saying hello", "discord", "send", "aman", "hello"),
    ("Insta pe divu ko message kar hello", "instagram", "send", "divu", "hello"),
    ("Discord messages padho", "discord", "read", "", ""),
    ("divu ke instagram messages padh do", "instagram", "read", "divu", ""),
    ("Discord pe Aman ko call karo", "discord", "call", "Aman", ""),
    ("Discord call utha lo", "discord", "answer", "", ""),
    ('Send to aman on discord saying Meet me on campus', "discord", "send", "aman", "Meet me on campus"),
    ('Send "hello" to aman on discord', "discord", "send", "aman", "hello"),
    ('read messages from Aman on discord', "discord", "read", "Aman", ""),
])
def test_explicit_social_platform(query, platform, action, recipient, message):
    result = parse_social_command(query)
    assert result["platform"] == platform
    assert result["action"] == action
    assert result["recipient"] == recipient
    assert result.get("message_text", "") == message
    assert classify_intent(query)["tool"] == "social_chat"


@pytest.mark.parametrize("query,target", [("WhatsApp kholo", "whatsapp"), ("Discord kholna", "discord"), ("Insta kholo na", "insta"), ("Jarvis open Chrome", "Chrome")])
def test_application_language(query, target):
    result = classify_intent(query)
    assert result["tool"] == "open_app"
    assert result["target"].casefold() == target.casefold()


@pytest.mark.parametrize("query,date,time,message", [
    ("10 minute baad paani peena yaad dilana", "2026-09-30", "14:10:00", "paani peena"),
    ("Remind me in 2 hours to submit assignment", "2026-09-30", "16:00:00", "submit assignment"),
    ("kal 9 am reminder laga assignment submit", "2026-10-01", "09:00:00", "assignment submit"),
    ("Set timer for 30 seconds", "2026-09-30", "14:00:30", "Timer complete"),
    ("remind me tomorrow at 9:30 pm to call home", "2026-10-01", "21:30:00", "call home"),
])
def test_reminder_times(query, date, time, message):
    parsed = parse_reminder_query(query, now=datetime(2026, 9, 30, 14))
    assert parsed == {"date": date, "time": time, "message": message}


@pytest.mark.parametrize("query", ["remind me to study", "aaj 9 am reminder laga", "kal 9 baje yaad dilana", "set timer 0 minutes", "remind me at 25:70"])
def test_unclear_reminder_never_schedules(query):
    with pytest.raises(ValueError):
        parse_reminder_query(query, now=datetime(2026, 9, 30, 14))


def test_reminder_registered_and_failure_preserved():
    from core.register_tools import initialize_all_tools, default_tool_registry
    initialize_all_tools()
    assert default_tool_registry.has_tool("reminder")
    result = default_tool_registry.execute_tool("reminder", {"query": "remind me to study"})
    assert not result.success
    assert "Time batao" in result.message


def test_environment_local_override(monkeypatch):
    monkeypatch.setenv("JARVIS_CLOUD_AI", "false")
    assert not is_cloud_ai_allowed()
    monkeypatch.setenv("JARVIS_CLOUD_AI", "true")
    assert is_cloud_ai_allowed()


def test_gemini_key_not_returned_as_openrouter(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    with patch("config.get_config", return_value={}):
        assert get_api_key("openrouter_api_key") == ""


def test_action_failure_runs_once():
    count = []
    def broken(params):
        count.append(params)
        raise TypeError("failed after action started")
    result = Tool("broken", "", {}, execute_func=broken).execute({"target": "test"})
    assert not result.success
    assert len(count) == 1


def test_lazy_action_failure_runs_once():
    from core.register_tools import _lazy_tool, _LOADED_FUNCS
    count = []
    def broken(parameters, player=None):
        count.append(parameters)
        raise AttributeError("failed after action started")
    with patch.dict(_LOADED_FUNCS, {"test:broken": broken}):
        result = Tool("broken", "", {}, execute_func=_lazy_tool("test", "broken")).execute({})
    assert not result.success
    assert len(count) == 1


def test_failure_and_unverified_result_remain_truthful():
    result = Tool("fail", "", {}, execute_func=lambda params: {"success": False, "verified": False, "message": "Login required"}).execute({})
    assert not result.success and result.message == "Login required"
    result = Tool("attempt", "", {}, execute_func=lambda params: {"success": True, "verified": False, "message": "Requested; status unknown"}).execute({})
    assert result.success and not result.verification["verified"]


def test_social_command_does_not_use_whatsapp():
    from core.command_pipeline import process_user_command
    reply = ToolResult(success=False, tool="social_chat", message="Login required", verification={"verified": False})
    with patch("core.command_pipeline._tools_initialized", True), patch("core.command_pipeline.default_tool_registry.execute_tool", return_value=reply) as run:
        result = process_user_command("Aman ko discord pe hello bhej", source="voice")
    assert run.call_count == 1
    assert run.call_args.args[0] == "social_chat"
    assert result["message"] == "Login required"


def test_typed_and_voice_failures_are_spoken():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live._command_lock = threading.RLock()
    live._check_barge_in = MagicMock(return_value=False)
    live.ui = MagicMock()
    live.speak = MagicMock()
    with patch("core.command_pipeline.process_user_command", return_value={"success": False, "message": "Could not open"}) as process:
        live._on_text_command("Jarvis, Open Chrome", "voice")
    process.assert_called_once_with("Jarvis, Open Chrome", source="voice")
    live.speak.assert_called_once_with("Could not open")


def test_live_tool_repeated_in_one_turn_executes_once():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live._command_lock = threading.RLock()
    live._turn_command_results = {}
    command = SimpleNamespace(name="assistant_command", args={"query": "WhatsApp kholo"}, id="call-1")
    async def run():
        await live._execute_tool(command)
        command.id = "call-2"
        return await live._execute_tool(command)
    with patch("core.command_pipeline.process_user_command", return_value={"success": True, "verified": True, "message": "Opened", "data": {"object": object()}}) as process:
        response = asyncio.run(run())
    assert process.call_count == 1
    json.dumps(response.response)


def test_login_read_never_returns_sample_messages():
    page = SimpleNamespace(url="https://discord.com/login")
    result = asyncio.run(execute_social_chat(page, "discord", "read"))
    assert not result["success"]
    assert result["status"] == "LOGIN_REQUIRED"
    assert "messages" not in result


def test_cloud_failure_has_local_fallback():
    from core.ai_multitier_engine import MultiTierAIEngine
    engine = MultiTierAIEngine()
    engine.prefer_cloud = True
    engine.gemini_api_key = "test-only"
    engine.openrouter_api_key = ""
    with patch.dict(os.environ, {"JARVIS_CLOUD_AI": "true"}), patch("google.genai.Client", side_effect=RuntimeError("offline")), patch("core.ollama_provider.is_ollama_available", return_value=True), patch("core.ollama_provider.generate_ollama_response", return_value={"success": True, "text": "Local answer"}):
        result = engine.generate_response("Hello", system_override="Be concise")
    assert result["success"] and result["text"] == "Local answer"
    assert result["tier"] == "TIER_1_OLLAMA"


@pytest.mark.parametrize("local,barge,speaking,tail,tts,expected", [
    (True, False, True, False, False, False),
    (False, False, True, False, False, False),
    (False, False, False, True, False, False),
    (False, False, False, False, True, False),
    (False, False, False, False, False, True),
    (False, True, True, False, False, True),
])
def test_microphone_echo_guard(local, barge, speaking, tail, tts, expected):
    import time
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = SimpleNamespace(muted=False)
    live.tts_engine = MagicMock()
    live.tts_engine.is_speaking.return_value = tts
    live._local_voice_active = local
    live._voice_barge_in = barge
    live._is_speaking = speaking
    live._last_speech_end = time.monotonic() if tail else 0
    live._echo_guard_seconds = 0.5
    with patch("actions.mic_control.get_jarvis_mic_enabled", return_value=True):
        assert live._mic_accepts_audio() is expected


def test_reminder_text_is_escaped_and_jobs_do_not_collide(tmp_path):
    import ast
    from actions.reminder import reminder
    from xml.etree import ElementTree as ET
    calls = []
    def fake_scheduler(args, **kwargs):
        xml_path = args[args.index("/XML") + 1]
        document = ET.parse(xml_path)
        calls.append(args[args.index("/TN") + 1])
        assert "<script>" in document.find(".//{*}Description").text
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    with patch.dict(os.environ, {"TEMP": str(tmp_path)}), patch("actions.reminder.subprocess.run", side_effect=fake_scheduler):
        for _ in range(2):
            result = reminder({"date": "2099-01-01", "time": "09:00", "message": 'quote " <script> & newline\nsecond line'})
            assert result["success"]
    assert len(set(calls)) == 2
    for script in tmp_path.glob("*.pyw"):
        ast.parse(script.read_text(encoding="utf-8"))


def test_live_config_supplies_only_real_command_tools():
    from main import JarvisLive
    config = JarvisLive.__new__(JarvisLive)._build_config()
    names = [tool.name for tool in config.tools[0].function_declarations]
    assert "assistant_command" in names
    assert "open_app" not in names
