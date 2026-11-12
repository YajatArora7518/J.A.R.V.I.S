"""No real messages/calls: regression checks for actual action evidence."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from unittest.mock import AsyncMock
import asyncio
import threading
import pytest


@pytest.mark.parametrize("query,contact,message", [
    ("WhatsApp p Divyansh ko msg kr match dekh le", "Divyansh", "match dekh le"),
    ("WhatsApp pe Divyansh ko message bhejo Match DEKH le", "Divyansh", "Match DEKH le"),
    ('Send "Meet me on campus" to Divyansh on WhatsApp', "Divyansh", "Meet me on campus"),
])
def test_whatsapp_message_preserves_exact_payload(query, contact, message):
    from actions.whatsapp_automation import parse_whatsapp_command
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    assert parse_whatsapp_command(query) == {"contact": contact, "message": message}
    result = ToolResult(tool="whatsapp_send_message", success=True, message="fixture", verification={"verified": True})
    with patch("core.command_pipeline.default_tool_registry.execute_tool", return_value=result) as execute:
        process_user_command(query, source="voice")
    execute.assert_called_once_with("whatsapp_send_message", {"contact": contact, "message": message, "force_send": True})


def test_named_whatsapp_read_does_not_read_wrong_chat():
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    with patch("core.command_pipeline.default_tool_registry.execute_tool", return_value=ToolResult(tool="whatsapp_read_messages", success=False, message="not found", verification={"verified": False})) as execute:
        result = process_user_command("Divyansh ka WhatsApp message batao")
    execute.assert_called_once_with("whatsapp_read_messages", {"contact": "Divyansh"})
    assert not result["success"]


def test_send_wrapper_preserves_failure():
    from actions.send_message import send_message
    failure = {"success": False, "verified": False, "message": "Recipient not resolved"}
    with patch("actions.universal_messaging.send_universal_message", return_value=failure):
        assert send_message({"receiver": "Divyansh", "message_text": "hi"}) == failure


def test_native_dedup_protects_uncertain_attempt_without_claiming_success():
    from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor, _SENT_MESSAGES_DEDUP_CACHE
    _SENT_MESSAGES_DEDUP_CACHE.clear()
    with patch("actions.whatsapp_desktop_dom.desktop_action", return_value={"success": False, "verified": False, "status": "SEND_UNVERIFIED", "message": "uncertain"}) as action:
        first = windows_whatsapp_desktop_executor.execute_send_message("Unique Fixture Contact", "one message")
        second = windows_whatsapp_desktop_executor.execute_send_message("Unique Fixture Contact", "one message")
    assert action.call_count == 1
    assert not first["success"] and not second["success"] and second["duplicate_prevented"]
    _SENT_MESSAGES_DEDUP_CACHE.clear()


@pytest.mark.parametrize("method", ["execute_answer_call", "execute_decline_call", "execute_end_call"])
def test_call_state_is_not_fabricated(method):
    from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor, call_state_machine, STATE_INCOMING
    call_state_machine.transition_to(STATE_INCOMING, "Fixture Caller")
    with patch("actions.whatsapp_desktop_dom.desktop_action", return_value={"success": False, "verified": False, "message": "no control"}):
        result = getattr(windows_whatsapp_desktop_executor, method)()
    assert not result["success"] and call_state_machine.state == STATE_INCOMING
    call_state_machine.transition_to("NO_CALL")


@pytest.mark.parametrize("when,expected", [(-2, False), (0.5, True), (3, False), (None, False)])
def test_due_soon_uses_real_deadline(when, expected):
    from agent.proactive_engine import ProactiveDecisionEngine
    due = (datetime.now() + timedelta(days=when)).isoformat() if when is not None else None
    task = SimpleNamespace(title="Fixture assignment", category="assignment", priority="HIGH", due_at=due)
    engine = ProactiveDecisionEngine()
    with patch("agent.proactive_engine.permission_manager.is_granted", return_value=True), patch("agent.proactive_engine.privacy_mode_manager.is_privacy_mode_active", return_value=False), patch("agent.task_manager.default_task_manager.get_pending_tasks", return_value=[task]):
        event = engine.evaluate_proactive_speech(context={}, current_hour=12)
    assert bool(event and event["type"] == "ASSIGNMENT_DUE_SOON") == expected


def test_ocr_never_fuzzily_resolves_a_contact():
    from actions.whatsapp_desktop_visual import WhatsAppObservation
    state = WhatsAppObservation.__new__(WhatsAppObservation)
    state.chat_left = 420
    state.lines = [{"text": "Dwyansh", "words": [{"x": 523, "y": 53}]}]
    assert not state.chat_header_matches("Divyansh")
    state.lines[0]["text"] = "Divyansh"
    assert state.chat_header_matches("Divyansh")


def test_visual_send_preserves_existing_draft():
    from actions.whatsapp_desktop_visual import execute_visual
    state = MagicMock()
    state.chat_header_matches.return_value = True
    state.composer_placeholder.return_value = None
    with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "fixture")), patch("actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd", return_value=123), patch("actions.whatsapp_desktop_visual.WhatsAppObservation", return_value=state), patch("actions.whatsapp_desktop_visual._paste") as paste:
        result = execute_visual("send", "Divyansh", "hi")
    assert result["status"] == "COMPOSER_NOT_EMPTY"
    paste.assert_not_called()


def test_visual_send_checks_recipient_and_draft_before_pressing_enter():
    from actions.whatsapp_desktop_visual import execute_visual
    before, after_typing = MagicMock(), MagicMock()
    before.chat_header_matches.return_value = True
    before.composer_placeholder.return_value = {"text": "Type a message"}
    before.matching_outgoing.return_value = []
    after_typing.height = 745
    after_typing.lines = [{"text": "hi", "words": [{"y": 697}]}]
    after_typing.chat_header_matches.return_value = False
    with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "fixture")), patch("actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd", return_value=123), patch("actions.whatsapp_desktop_visual.WhatsAppObservation", side_effect=[before, after_typing]), patch("actions.whatsapp_desktop_visual._paste"), patch("pyautogui.press") as press:
        result = execute_visual("send", "Divyansh", "hi")
    assert result["status"] == "DRAFT_UNVERIFIED"
    press.assert_not_called()


@pytest.mark.parametrize("service", ["gmail", "calendar", "instagram", "discord", "whatsapp"])
def test_background_auth_never_opens_or_focuses_tabs(service):
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    context = SimpleNamespace(pages=[], new_page=AsyncMock())
    engine._get_cdp_browser = AsyncMock(return_value=SimpleNamespace(contexts=[context]))
    with patch("actions.browser_automation.is_cdp_active", return_value=True):
        result = asyncio.run(engine._check_service_auth_async(service))
    assert result["status"] == "TAB_NOT_OPEN"
    engine._get_cdp_browser.assert_awaited_once_with(allow_launch=False)
    context.new_page.assert_not_awaited()


@pytest.mark.parametrize("service,domain", [("calendar", "calendar.google.com"), ("instagram", "instagram.com")])
def test_service_url_without_signed_in_controls_is_not_authenticated(service, domain):
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    page = SimpleNamespace(url="https://" + domain + "/", query_selector=AsyncMock(return_value=None), bring_to_front=AsyncMock())
    engine._get_cdp_browser = AsyncMock(return_value=SimpleNamespace(contexts=[SimpleNamespace(pages=[page])]))
    with patch("actions.browser_automation.is_cdp_active", return_value=True):
        result = asyncio.run(engine._check_service_auth_async(service))
    assert not result["authenticated"]
    page.bring_to_front.assert_not_awaited()


def test_service_redirect_reuses_existing_tab_and_ignores_url_query_spoof():
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    unrelated = SimpleNamespace(url="https://example.test/?redirect=mail.google.com", bring_to_front=AsyncMock())
    previous = SimpleNamespace(url="https://accounts.google.com/login", is_closed=lambda: False, goto=AsyncMock(), bring_to_front=AsyncMock())
    engine._service_pages["mail.google.com"] = previous
    context = SimpleNamespace(pages=[unrelated, previous], new_page=AsyncMock())
    engine._get_cdp_browser = AsyncMock(return_value=SimpleNamespace(contexts=[context]))
    result = asyncio.run(engine.get_or_open_page("mail.google.com", "https://mail.google.com/"))
    assert result is previous
    context.new_page.assert_not_awaited()
    unrelated.bring_to_front.assert_not_awaited()


def test_live_empty_tool_completion_keeps_execution_ledger():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live._command_lock = threading.RLock()
    live._turn_command_results = {}
    live._turn_had_tool_call = False
    live._turn_received_audio = False
    live._mic_stats = {"speech_segments": 0, "transcript_events": 0}
    live.set_speaking = MagicMock()
    live._update_proactive_state = MagicMock()
    live._dispatch_voice_to_pipeline = MagicMock()
    command = SimpleNamespace(name="assistant_command", args={"query": "open fixture"}, id="one")
    sc = SimpleNamespace(interrupted=False, output_transcription=None, input_transcription=SimpleNamespace(text="Jarvis, open fixture"), turn_complete=True)
    first = SimpleNamespace(tool_call=SimpleNamespace(function_calls=[command]), data=None, server_content=sc)
    second = SimpleNamespace(tool_call=SimpleNamespace(function_calls=[command]), data=None, server_content=None)
    class Session:
        async def receive(self):
            yield first
            yield second
            raise asyncio.CancelledError()
        send_tool_response = AsyncMock()
    live.session = Session()
    with patch("main._is_session_active", return_value=True), patch("core.command_pipeline.process_user_command", return_value={"success": True, "verified": True, "message": "fixture"}) as execute:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._receive_audio())
    assert execute.call_count == 1
    live._dispatch_voice_to_pipeline.assert_not_called()


def test_pipeline_does_not_promote_an_unverified_call_to_verified():
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    attempted = ToolResult(tool="discord_disconnect_voice", success=True, message="attempted", verification={"verified": False})
    with patch("core.command_pipeline.classify_intent", return_value={"intent": "DISCORD_DISCONNECT"}), patch("core.command_pipeline.default_tool_registry.execute_tool", return_value=attempted):
        result = process_user_command("disconnect discord")
    assert result["success"] and not result["verified"]


@pytest.mark.parametrize("target", ["Divyansh", "123 & echo fixture", "123;whoami"])
def test_phone_call_requires_resolved_number_before_dispatch(target):
    from actions.universal_calls_sms import make_call
    with patch("actions.universal_calls_sms.subprocess.run") as dispatch, patch("actions.universal_calls_sms.os.startfile") as launch:
        result = make_call(target, confirm_call=True)
    assert not result["success"] and not result["verified"]
    dispatch.assert_not_called()
    launch.assert_not_called()


def test_phone_intent_is_not_claimed_as_a_connected_call():
    from actions.universal_calls_sms import make_call
    with patch("actions.universal_calls_sms.shutil.which", return_value="adb.exe"), patch("actions.universal_calls_sms.subprocess.run", return_value=SimpleNamespace(returncode=0)) as dispatch:
        result = make_call("+1 202 555 0123", confirm_call=True)
    assert result["success"] and not result["verified"]
    assert dispatch.call_args.kwargs["shell"] is False
    assert dispatch.call_args.args[0][-1] == "tel:+12025550123"


def test_instagram_login_query_on_signed_in_inbox_is_not_a_login_page():
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    page = SimpleNamespace(url="https://www.instagram.com/direct/inbox/?__coig_login=1", query_selector=AsyncMock(return_value=object()))
    engine._get_cdp_browser = AsyncMock(return_value=SimpleNamespace(contexts=[SimpleNamespace(pages=[page])]))
    with patch("actions.browser_automation.is_cdp_active", return_value=True):
        result = asyncio.run(engine._check_service_auth_async("instagram"))
    assert result["authenticated"]
