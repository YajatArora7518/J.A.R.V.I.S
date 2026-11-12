"""Isolated acceptance regressions: no real messages, calls or engagements."""
import asyncio
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def aggregator(monkeypatch):
    from actions.notification_engine import NotificationAggregator
    monkeypatch.setattr(NotificationAggregator, "_instance", None)
    return NotificationAggregator()


def test_notification_reads_never_open_a_chat_or_invent_unread_messages(aggregator):
    with patch("actions.whatsapp_automation.whatsapp_read_messages") as read:
        result = aggregator.get_summary()
    read.assert_not_called()
    assert not result["success"] and not result["verified"]


def test_notification_dedup_is_atomic_and_read_events_are_filtered(aggregator):
    def add(_):
        return aggregator.add_notification("whatsapp", "WhatsApp", "Fixture", "Message", "same event")
    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(add, range(60)))
    assert len(aggregator._notifications) == 1 and len({id(event) for event in events}) == 1
    events[0].is_read = True
    assert not aggregator.fetch_recent_notifications()


def test_notification_growth_is_bounded(aggregator):
    for index in range(240):
        aggregator.add_notification("discord", "Discord", "Fixture", "Message", str(index))
    assert len(aggregator._notifications) == 200


@pytest.mark.parametrize("method", ["read_call_log", "read_sms_messages"])
def test_disconnected_phone_does_not_claim_an_empty_inbox(method):
    from actions import universal_calls_sms
    with patch("actions.universal_calls_sms.shutil.which", return_value=None):
        result = getattr(universal_calls_sms, method)()
    assert not result["success"] and not result["verified"]


def test_sms_draft_quotes_remote_shell_and_does_not_claim_delivery():
    from actions.universal_calls_sms import send_sms_message
    message = 'नमस्ते; echo bad $(whoami) "quote"'
    with patch("actions.universal_calls_sms.shutil.which", return_value="adb.exe"), patch("actions.universal_calls_sms.subprocess.run", return_value=SimpleNamespace(returncode=0)) as run:
        result = send_sms_message("+1 202 555 0123", message)
    command = run.call_args.args[0]
    assert command[:2] == ["adb.exe", "shell"]
    assert shlex.split(command[2])[-1] == message
    assert run.call_args.kwargs["shell"] is False
    assert result["status"] == "SMS_DRAFT_REQUESTED" and not result["verified"]


def test_named_sms_read_uses_exact_phone_filter():
    from actions.universal_calls_sms import read_sms_messages
    with patch("actions.universal_calls_sms.shutil.which", return_value="adb.exe"), patch("actions.universal_calls_sms.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout="Row: 0 address=+12025550123, body=fixture")) as run:
        result = read_sms_messages("+1 202 555 0123")
    assert result["verified"]
    assert shlex.split(run.call_args.args[0][2])[-1] == "address='+12025550123'"


def test_browser_connection_is_reused():
    from actions.browser_automation import BrowserAutomationEngine
    engine = BrowserAutomationEngine()
    browser = MagicMock()
    browser.is_connected.return_value = True
    connect = AsyncMock(return_value=browser)
    engine._playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
    async def run():
        await engine._get_cdp_browser(allow_launch=False)
        await engine._get_cdp_browser(allow_launch=False)
    with patch("actions.browser_automation.is_cdp_active", return_value=True):
        asyncio.run(run())
    connect.assert_awaited_once()


def test_service_discovery_does_not_invent_logins_or_phone_connection():
    from actions.service_discovery import UniversalServiceRegistry
    from actions.universal_app_resolver import default_app_resolver
    with patch.object(default_app_resolver.catalog, "get_catalog", return_value={}), patch("actions.browser_automation.browser_automation_engine.check_service_auth_sync", return_value={"authenticated": False}), patch("actions.service_discovery.shutil.which", return_value="adb.exe"), patch("actions.mobile_pc_gateway.mobile_pc_gateway.is_android_online", return_value=False):
        services = UniversalServiceRegistry().discover_services()
    assert not any(service.logged_in for service in services.values())
    assert "phone" not in services and "sms" not in services
    assert not services["instagram"].send_supported


def test_discord_provider_has_real_call_dispatch_and_confirmation():
    from actions.discord_automation import discord_provider
    with patch("actions.social_chat.social_chat", return_value={"success": True, "verified": True}) as call:
        assert not discord_provider.call("Fixture")["success"]
        assert discord_provider.call("Fixture", confirm_call=True)["verified"]
    call.assert_called_once_with({"platform": "discord", "action": "call", "recipient": "Fixture", "call_type": "voice"})


@pytest.mark.parametrize("status", ["CALL_UNVERIFIED", "CALL_ALREADY_ACTIVE", "RECIPIENT_UNVERIFIED"])
def test_native_call_failures_never_retry_through_browser(status):
    from actions.whatsapp_desktop_dom import desktop_action
    with patch("actions.whatsapp_desktop_dom.desktop_connection_ready", return_value=False), patch("actions.whatsapp_desktop_accessibility.execute_accessible_call", return_value={"success": False, "verified": False, "status": status}), patch("actions.whatsapp_desktop_dom.browser_call_fallback") as fallback:
        result = desktop_action("voice_call", "Fixture")
    assert not result["success"]
    fallback.assert_not_called()


def test_uncertain_icon_call_does_not_fall_back_to_browser():
    from actions.whatsapp_desktop_dom import desktop_action
    with patch("actions.whatsapp_desktop_dom.desktop_connection_ready", return_value=False), patch("actions.whatsapp_desktop_accessibility.execute_accessible_call", return_value={"status": "ACCESSIBILITY_CONTROL_UNAVAILABLE"}), patch("actions.whatsapp_desktop_icons.execute_icon_call", return_value={"success": False, "verified": False, "status": "CALL_UNVERIFIED"}), patch("actions.whatsapp_desktop_dom.browser_call_fallback") as fallback:
        assert not desktop_action("voice_call", "Fixture")["success"]
    fallback.assert_not_called()


@pytest.mark.parametrize("duplicates", [0, 1, 2])
def test_native_phone_glyph_requires_one_match(duplicates):
    from actions.whatsapp_desktop_icons import find_voice_icon
    root = Path(__file__).resolve().parent.parent
    image = Image.new("RGB", (900, 550), (20, 24, 27))
    with Image.open(root / "assets" / "whatsapp_voice_call.png") as glyph:
        for index in range(duplicates):
            image.paste(glyph, (580+index*150, 60))
    result = find_voice_icon(SimpleNamespace(image=image, chat_left=420))
    assert bool(result) == (duplicates == 1)


@pytest.mark.parametrize("color", ["red", "green"])
def test_native_call_color_control_is_unique_and_in_toolbar(color):
    from actions.whatsapp_desktop_icons import color_call_button
    image = Image.new("RGB", (600, 400), (20, 24, 27))
    rgb = (212, 50, 50) if color == "red" else (0, 171, 101)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((420, 330, 492, 374), 20, fill=rgb)
    assert color_call_button(image, color) is not None
    draw.rounded_rectangle((280, 330, 352, 374), 20, fill=rgb)
    assert color_call_button(image, color) is None


def test_native_icon_call_checks_recipient_again_before_click():
    from actions.whatsapp_desktop_icons import execute_icon_call
    state = MagicMock()
    state.chat_header_matches.return_value = False
    with patch("actions.whatsapp_desktop_visual.execute_visual", return_value={"success": True, "verified": True}), patch("actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd", return_value=123), patch("actions.whatsapp_desktop_visual.WhatsAppObservation", return_value=state), patch("actions.whatsapp_desktop_icons.find_voice_icon", return_value={"x": 800, "y": 70}), patch("pyautogui.click") as click:
        result = execute_icon_call("voice_call", "Fixture")
    assert result["status"] == "RECIPIENT_UNVERIFIED"
    click.assert_not_called()


def test_social_actions_without_implementation_fail_honestly():
    from actions.social_actions import execute_social_action
    assert not execute_social_action("instagram", "comment", content="fixture")["verified"]
    assert not execute_social_action("youtube", "play_media", "unresolved title")["success"]


@pytest.mark.parametrize("action,flag", [("reply", "force_send"), ("call", "confirm_call")])
def test_whatsapp_string_flags_do_not_authorize_communications(action, flag):
    from actions.whatsapp import whatsapp
    assert whatsapp(action=action, **{flag: "false"})["requires_confirmation"]


def test_whatsapp_reply_dispatches_once_with_authorized_exact_payload():
    from actions.whatsapp import whatsapp_reply_tool
    from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
    with patch("actions.whatsapp_automation.resolve_contact", return_value={}), patch("actions.windows_whatsapp_desktop_executor.resolve_contact_ambiguity", return_value={}), patch.object(windows_whatsapp_desktop_executor, "execute_send_message", return_value={"success": True, "verified": True}) as send:
        assert whatsapp_reply_tool(contact="Fixture", message="Exact Reply", force_send=True)["verified"]
    send.assert_called_once_with(recipient="Fixture", message="Exact Reply")


@pytest.mark.parametrize("name,wrapper,flag", [("whatsapp_send_message", "whatsapp_send_message_tool", "force_send"), ("whatsapp_voice_call", "whatsapp_voice_call_tool", "confirm_call"), ("whatsapp_video_call", "whatsapp_video_call_tool", "confirm_call")])
def test_registry_wrappers_preserve_confirmation_without_bypassing_security(name, wrapper, flag):
    from core.register_tools import initialize_all_tools
    from core.tool_registry import default_tool_registry
    initialize_all_tools()
    tool = default_tool_registry.get_tool(name)
    with patch("actions.whatsapp."+wrapper, return_value={"success": True, "verified": True}) as handler:
        tool.execute({"contact": "Fixture", "message": "Exact Text", flag: True})
    assert handler.call_args.kwargs[flag] is True
    assert handler.call_args.kwargs["contact"] == "Fixture"
    if flag == "confirm_call":
        from core.security import RiskLevel
        assert tool.risk_level == RiskLevel.HIGH


def test_broken_live_audio_exits_for_reconnect_after_one_failed_frame():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.session = SimpleNamespace(send_realtime_input=AsyncMock(side_effect=ConnectionError("stream closed")))
    live._mic_stats = {"send_errors": 0}
    async def run():
        live.out_queue = asyncio.Queue()
        for _ in range(3):
            live.out_queue.put_nowait({"data": b"audio"})
        with pytest.raises(ConnectionError, match="stream closed"):
            await asyncio.wait_for(live._send_realtime(), timeout=2)
        assert live.out_queue.qsize() == 2
    asyncio.run(run())
    live.session.send_realtime_input.assert_awaited_once()
    assert live._mic_stats["send_errors"] == 1


def test_explicit_message_reaches_native_executor_once_with_exact_text():
    from core.command_pipeline import process_user_command
    from actions.windows_whatsapp_desktop_executor import windows_whatsapp_desktop_executor
    with patch("actions.whatsapp_automation.resolve_contact", return_value={}), patch("actions.windows_whatsapp_desktop_executor.resolve_contact_ambiguity", return_value={}), patch.object(windows_whatsapp_desktop_executor, "execute_send_message", return_value={"success": True, "verified": True, "message": "fixture"}) as send:
        result = process_user_command("WhatsApp pe Fixture ko message bhejo Exact नमस्ते")
    assert result["success"] and result["verified"]
    send.assert_called_once_with(recipient="Fixture", message="Exact नमस्ते")


@pytest.mark.parametrize("still_active", [False, True])
def test_native_end_requires_call_to_be_inactive_after_click(still_active):
    from actions.whatsapp_desktop_icons import execute_call_control
    first = {"hwnd": 123, "rect": (0, 0, 600, 400), "incoming": False, "active": True, "red": (460, 355), "green": None}
    after = {**first, "red": None, "active": still_active}
    with patch("win32gui.EnumWindows", side_effect=lambda collect, arg: collect(123, arg)), patch("win32gui.IsWindowVisible", return_value=True), patch("win32gui.IsIconic", return_value=False), patch("actions.whatsapp_desktop_icons._owned_window", return_value=True), patch("actions.windows_whatsapp_desktop_executor.win32_activate_hwnd", return_value=True), patch("actions.whatsapp_desktop_icons._capture_call", side_effect=[first, after]), patch("win32gui.GetForegroundWindow", return_value=123), patch("win32gui.GetWindowRect", return_value=first["rect"]), patch("win32gui.IsWindow", return_value=True), patch("pyautogui.click") as click, patch("actions.whatsapp_desktop_icons.time.sleep"):
        result = execute_call_control("end_call")
    click.assert_called_once_with(460, 355)
    assert result["verified"] is (not still_active)


@pytest.mark.parametrize("popup_fails", [False, True])
def test_generated_reminder_finishes_speech_and_never_waits_on_an_indefinite_dialog(tmp_path, popup_fails):
    import sys
    from actions.reminder import reminder
    voice, shell = MagicMock(), MagicMock()
    if popup_fails:
        shell.Popup.side_effect = RuntimeError("notification unavailable")
    with patch.dict("os.environ", {"TEMP": str(tmp_path)}), patch("actions.reminder.subprocess.run", return_value=SimpleNamespace(returncode=0)):
        assert reminder({"date": "2099-01-01", "time": "09:00", "message": "Fixture reminder"})["success"]
    script = next(tmp_path.glob("JARVISReminder_*.pyw"))
    code = script.read_text(encoding="utf-8")
    with patch("win32com.client.Dispatch", side_effect=lambda name: voice if name == "SAPI.SpVoice" else shell), patch("winsound.Beep"), patch("time.sleep"), patch.object(sys, "path", list(sys.path)):
        exec(compile(code, str(script), "exec"), {"__file__": str(script)})
    voice.Speak.assert_called_once_with("Reminder. Fixture reminder", 0)
    shell.Popup.assert_called_once_with("Fixture reminder", 15, "JARVIS Reminder", 0x40)
    assert not script.exists()


@pytest.mark.parametrize("action", ["answer", "end_call"])
def test_accessibility_does_not_invent_success_when_controls_or_inventory_are_uncertain(action):
    from actions.whatsapp_desktop_accessibility import execute_accessible_call
    answer = MagicMock()
    answer.window_text.return_value = "Answer call"
    end = MagicMock()
    end.window_text.return_value = "End call"
    before = [{"window": MagicMock(), "buttons": [answer, end]}]
    after = before if action == "answer" else []
    with patch("actions.whatsapp_desktop_accessibility._inventory", side_effect=[before, before] + [after]*12), patch("actions.whatsapp_desktop_accessibility.time.sleep"):
        result = execute_accessible_call(action)
    assert result["status"] == "CALL_UNVERIFIED" and not result["verified"]
    (answer if action == "answer" else end).invoke.assert_called_once()
