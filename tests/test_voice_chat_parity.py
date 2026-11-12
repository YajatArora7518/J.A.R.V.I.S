"""Voice/chat acceptance without microphones or real account actions."""
import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


@pytest.fixture(autouse=True)
def isolated_context():
    from core.command_pipeline import reset_conversation_context
    reset_conversation_context()
    yield
    reset_conversation_context()


@pytest.mark.parametrize("source", ["chat", "voice"])
@pytest.mark.parametrize("platform", ["whatsapp", "discord", "instagram"])
def test_voice_and_chat_use_recent_verified_contact_and_preserve_reply(source, platform):
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    output = ToolResult(tool="fixture", success=True, message="fixture", verification={"verified": True})
    with patch("core.command_pipeline.default_tool_registry.execute_tool", return_value=output) as execute:
        first = process_user_command(f"Hey Jarvis, please {platform} Fixture ke messages padho", source=source)
        assert first["verified"]
        # Switching between input modes must retain the same contact context.
        other = "voice" if source == "chat" else "chat"
        second = process_user_command("ab usko message bhejo Please USKO mat bolna 👋", source=other)
        assert second["verified"]
    args = execute.call_args.args[1]
    if platform == "whatsapp":
        assert args == {"contact": "Fixture", "message": "Please USKO mat bolna 👋", "force_send": True}
    else:
        assert args == {"platform": platform, "recipient": "Fixture", "action": "send", "message_text": "Please USKO mat bolna 👋"}
    assert execute.call_count == 2


@pytest.mark.parametrize("query,action,payload", [
    ("uske messages padho", "read", None),
    ("uski chat kholo", "open_chat", None),
    ("usse bolo On My Way", "send", "On My Way"),
    ("reply kar Meet at 6 👋", "send", "Meet at 6 👋"),
    ("WhatsApp pe usko msg bhejo Exact Reply", "send", "Exact Reply"),
])
def test_natural_followups_resolve_exact_whatsapp_contact(query, action, payload):
    from core.command_pipeline import _remember_social_target, _resolve_social_follow_up
    _remember_social_target({"platform": "whatsapp", "recipient": "Fixture", "action": "read"}, True, True)
    result, error = _resolve_social_follow_up(query)
    assert error is None and result["recipient"] == "Fixture" and result["action"] == action
    if payload:
        assert result["message_text"] == payload


@pytest.mark.parametrize("reason", ["missing", "expired", "failed", "unverified", "different_platform"])
def test_ambiguous_or_stale_contact_never_dispatches_a_message(reason):
    from core.command_pipeline import process_user_command, _remember_social_target
    from core import command_pipeline
    if reason != "missing":
        _remember_social_target({"platform": "whatsapp", "recipient": "Fixture", "action": "read"}, reason != "failed", reason != "unverified")
    if reason == "expired":
        command_pipeline._CONVERSATION_CONTEXT["last_social_target"]["time"] -= 121
    query = "Instagram usko message bhejo hello" if reason == "different_platform" else "usko message bhejo hello"
    with patch("core.command_pipeline.default_tool_registry.execute_tool") as execute:
        result = process_user_command(query)
    assert result["status"] == "CONTACT_CONTEXT_REQUIRED" and not result["verified"]
    execute.assert_not_called()


def test_failed_new_contact_invalidates_previous_recipient():
    from core.command_pipeline import _remember_social_target, _resolve_social_follow_up
    _remember_social_target({"platform": "discord", "recipient": "First", "action": "read"}, True, True)
    _remember_social_target({"platform": "discord", "recipient": "Second", "action": "read"}, False, False)
    result, error = _resolve_social_follow_up("reply hello")
    assert result is None and error["status"] == "CONTACT_CONTEXT_REQUIRED"


@pytest.mark.parametrize("query", ["uska matlab kya hai", "uske baare mein batao"])
def test_normal_conversation_is_not_mistaken_for_a_contact_action(query):
    from core.command_pipeline import _resolve_social_follow_up
    command, error = _resolve_social_follow_up(query)
    assert command is None and error is None


def test_reply_does_not_infer_platform_from_words_in_the_message():
    from core.command_pipeline import _remember_social_target, _resolve_social_follow_up
    _remember_social_target({"platform": "discord", "recipient": "Fixture", "action": "read"}, True, True)
    result, error = _resolve_social_follow_up("reply WhatsApp pe message bhejo mat")
    assert error is None and result["platform"] == "discord"
    assert result["message_text"] == "WhatsApp pe message bhejo mat"


@pytest.mark.parametrize('query,payload', [
    ("open WhatsApp and send the message 'On My Way' to Fixture", 'On My Way'),
    ('WhatsApp kholo aur Fixture ko message bhejo On My Way', 'On My Way'),
    ('send whastapp ms tu Fixture of kkrh?', 'kkrh?'),
    ('send msf of kkrh? to Fixture on whastapp', 'kkrh?'),
])
def test_actual_compound_and_short_chat_message_grammar_preserves_payload(query, payload):
    from actions.social_chat import parse_social_command
    assert parse_social_command(query, include_whatsapp=True) == {
        'platform': 'whatsapp', 'action': 'send', 'recipient': 'Fixture', 'message_text': payload}


def test_live_rephrased_message_executes_once_without_changing_payload():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live._turn_command_results = {}
    live._command_lock = threading.RLock()
    live._update_proactive_state = MagicMock()
    result = {'success': True, 'verified': True, 'message': 'fixture'}
    first = SimpleNamespace(name='assistant_command', id='first', args={'query': "open WhatsApp and send the message 'On My Way' to Fixture"})
    second = SimpleNamespace(name='assistant_command', id='second', args={'query': 'send a WhatsApp message to Fixture saying On My Way'})
    async def run():
        await live._execute_tool(first)
        await live._execute_tool(second)
    with patch('core.command_pipeline.process_user_command', return_value=result) as execute:
        asyncio.run(run())
    execute.assert_called_once_with(first.args['query'], source='voice')


def test_send_details_are_collected_across_chat_and_voice_without_ai_guesses():
    from core.command_pipeline import process_user_command
    from core.tool_registry import ToolResult
    output = ToolResult(tool='fixture', success=True, message='fixture', verification={'verified': True})
    with patch('core.command_pipeline.default_tool_registry.execute_tool', return_value=output) as execute:
        first = process_user_command('WhatsApp message bhejo')
        second = process_user_command('Fixture ko bhjna hai')
        third = process_user_command('Jarvis, kkrh?', source='voice')
    assert first['status'] == second['status'] == 'SEND_DETAILS_REQUIRED'
    assert third['verified']
    execute.assert_called_once_with('whatsapp_send_message', {'contact': 'Fixture', 'message': 'kkrh?', 'force_send': True})


@pytest.mark.parametrize('reply,expired', [('haan', False), ('cancel', False), ('kkrh?', True), ('open Chrome', False)])
def test_unfinished_send_never_sends_confirmation_expired_text_or_new_actions(reply, expired):
    from core import command_pipeline
    command_pipeline._CONVERSATION_CONTEXT['pending_send_details'] = {
        'platform': 'whatsapp', 'action': 'send', 'recipient': 'Fixture', 'message_text': '',
        'time': __import__('time').monotonic() - (121 if expired else 0)}
    command, error = command_pipeline._collect_send_details(reply, None)
    assert command is None
    if reply == 'haan':
        assert error['status'] == 'SEND_DETAILS_REQUIRED'
    else:
        assert command_pipeline._CONVERSATION_CONTEXT['pending_send_details'] is None


def test_explicit_new_send_replaces_previous_pending_recipient():
    from core import command_pipeline
    command_pipeline._CONVERSATION_CONTEXT['pending_send_details'] = {
        'platform': 'whatsapp', 'action': 'send', 'recipient': 'OldFixture', 'message_text': '', 'time': __import__('time').monotonic()}
    new = {'platform': 'discord', 'action': 'send', 'recipient': 'NewFixture', 'message_text': 'Exact Payload'}
    assert command_pipeline._collect_send_details('explicit new request', new) == (new, None)
    assert command_pipeline._CONVERSATION_CONTEXT['pending_send_details'] is None


@pytest.mark.parametrize("source", ["chat", "voice"])
def test_explicit_native_call_reaches_exact_recipient_once(source):
    from core.command_pipeline import process_user_command
    with patch("actions.whatsapp.whatsapp", return_value={"success": False, "verified": False, "message": "fixture", "status": "CALL_UNVERIFIED"}) as call:
        result = process_user_command("Jarvis, WhatsApp par Fixture ko call karo", source=source)
    assert not result["verified"]
    call.assert_called_once_with(action="call", contact="Fixture", confirm_call=True)


@pytest.mark.parametrize("source", ["chat", "voice"])
def test_chat_and_voice_workers_return_and_display_the_same_result(source):
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live._command_lock = threading.RLock()
    live._check_barge_in = MagicMock(return_value=False)
    live._update_proactive_state = MagicMock()
    live.speak = MagicMock()
    output = {"success": True, "verified": True, "message": "The answer is 21."}
    with patch("core.command_pipeline.process_user_command", return_value=output) as execute:
        result = live._on_text_command("[CID:fixture] Jarvis, calculate 3 * 7", source=source)
    assert result == output
    execute.assert_called_once_with("Jarvis, calculate 3 * 7", source=source)
    live.ui.write_log.assert_called_once_with("JARVIS: Iska jawab 21 hai, bhai.")
    live.speak.assert_called_once_with("Iska jawab 21 hai, bhai.")


def test_typed_stop_with_bridge_id_interrupts_without_waiting_for_action_lock():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock(muted=False)
    live.tts_engine = MagicMock()
    live.set_speaking = MagicMock()
    live.audio_in_queue = asyncio.Queue()
    live.audio_in_queue.put_nowait(b"queued speech")
    with patch("core.command_pipeline.process_user_command") as execute:
        result = live._on_text_command("[CID:fixture] Jarvis, stop!")
    execute.assert_not_called()
    live.tts_engine.barge_in_stop.assert_called_once()
    assert live.audio_in_queue.empty() and result["barge_in"]
    live.ui.write_log.assert_called_once_with("JARVIS: Bolna rok diya.")
    live.ui.set_state.assert_called_once_with("LISTENING")


@pytest.mark.parametrize("input_id", ["cmd-input", "chat-input"])
def test_actual_dashboard_submit_sends_one_command_and_watchdog_never_invents_success(input_id):
    from playwright.async_api import async_playwright
    from actions.chrome_profile import get_chrome_executable
    html = (Path(__file__).resolve().parent.parent/"assets"/"jarvis_holographic_ui.html").read_text(encoding="utf-8")
    function = html[html.index("function submitTextCommand("):html.index("\nfunction sendCmdInput(")]
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                page = await browser.new_page()
                await page.set_content('<input id="cmd-input"><input id="chat-input"><div id="resp-text"></div>')
                await page.evaluate('''()=>{window._cmdWatchdogTimer=null;
                window.setTimeout=fn=>{window.watchdog=fn;return 1;};
                window.callBridge=(name,payload)=>{window.sent=(window.sent||[]).concat([{name,payload}]);return true;};
                window.JARVIS3DCore={appendChat:()=>{},addAction:()=>{},setResponse:text=>document.querySelector('#resp-text').textContent=text};}''')
                await page.add_script_tag(content=function)
                await page.locator('#'+input_id).fill("calculate 3 * 7")
                await page.evaluate("id=>submitTextCommand(id)", input_id)
                sent = await page.evaluate("window.sent")
                assert len(sent) == 1 and sent[0]["name"] == "sendCommand"
                assert sent[0]["payload"].endswith("] calculate 3 * 7")
                assert await page.locator('#'+input_id).input_value() == ""
                await page.evaluate("window.watchdog()")
                assert "final result nahi mila" in await page.locator('#resp-text').inner_text()
                assert "completed" not in await page.locator('#resp-text').inner_text()
            finally:
                await browser.close()
    asyncio.run(run())


def test_empty_worker_result_does_not_claim_completion():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.speak = MagicMock()
    with patch("core.command_pipeline.process_user_command", return_value=None):
        result = live._execute_text_command("fixture")
    assert not result["success"] and not result["verified"]
    assert "result nahi mila" in result["message"]


def test_realtime_microphone_uses_dedicated_audio_input():
    from main import JarvisLive

    async def run():
        live = JarvisLive.__new__(JarvisLive)
        live.out_queue = asyncio.Queue()
        await live.out_queue.put({"data": b"\x01\x00" * 1600, "mime_type": "audio/pcm;rate=16000"})
        await live.out_queue.put(b"\x00\x00" * 1600)
        send = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        live.session = SimpleNamespace(send_realtime_input=send)
        live._mic_stats = {"frames_sent": 0, "last_audio_ts": 0, "send_errors": 0}
        with pytest.raises(asyncio.CancelledError):
            await live._send_realtime()
        first = send.await_args_list[0].kwargs
        assert set(first) == {"audio"}
        assert first["audio"].data == b"\x01\x00" * 1600
        assert first["audio"].mime_type == "audio/pcm;rate=16000"
        assert live._mic_stats["frames_sent"] == 1
        assert live._mic_stats["last_audio_ts"] > 0
        assert live._mic_stats["send_errors"] == 0

    asyncio.run(run())


@pytest.mark.parametrize("text,expected", [
    ("Jarvis, Chrome kholo", True), ("Hey Jarvis calculate 3 * 7", True),
    ("जार्विस क्रोम खोलो", True), ("okay, Jarvis! stop", True),
    ("video mein Jarvis bola", False), ("set reminder for 7:30", False),
    ("Jarvislike movie", False), ("", False),
])
def test_voice_requires_current_direct_address(text, expected):
    from main import JarvisLive
    assert JarvisLive.__new__(JarvisLive)._voice_is_addressed(text) == expected


def test_wake_followup_expires_and_never_addresses_empty_audio():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live._voice_followup_deadline = 115.0
    with patch('main.time.monotonic', return_value=100.0):
        assert live._voice_is_addressed('WhatsApp kholo')
        assert not live._voice_is_addressed('')
    with patch('main.time.monotonic', return_value=116.0):
        assert not live._voice_is_addressed('WhatsApp kholo')
        assert live._voice_is_addressed('Jarvis, WhatsApp kholo')


def test_standalone_wake_keeps_following_commands_addressed():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.audio_in_queue = asyncio.Queue()
    live._mic_stats = {'transcript_events': 0, 'speech_segments': 0}
    live._turn_had_tool_call = live._turn_received_audio = False
    live._turn_command_results = {}
    live.set_speaking = MagicMock()
    live._check_barge_in = MagicMock()
    live._execute_tool = AsyncMock(return_value='verified calculator result')
    command = SimpleNamespace(name='assistant_command', args={'query': 'calculate 13 * 17'}, id='fixture')
    def packet(text=None, output=None, tool=False):
        return SimpleNamespace(data=None, tool_call=SimpleNamespace(function_calls=[command]) if tool else None,
            server_content=SimpleNamespace(interrupted=False, turn_complete=True,
                input_transcription=SimpleNamespace(text=text) if text else None,
                output_transcription=SimpleNamespace(text=output) if output else None))
    class Session:
        async def receive(self):
            for item in [packet('Jarvis', 'Haan, bolo'), packet('calculate 13 * 17', tool=True),
                         packet(output='221'), packet('send a message', tool=True)]:
                yield item
            raise asyncio.CancelledError()
        send_tool_response = AsyncMock()
    live.session = Session()
    with patch('main._is_session_active', return_value=True), patch('main.threading.Thread'), patch('main.time.monotonic', return_value=100.0):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._receive_audio())
    assert live._execute_tool.await_count == 2
    assert live._voice_followup_deadline == 0.0
    assert live._voice_conversation_active
    assert live._voice_is_addressed('aur bata')


@pytest.mark.parametrize("command", ["Jarvis, set a reminder for 7:30", "set an alarm for 7:30", "create a timer for 10 minutes"])
def test_spoken_reminder_articles_use_real_reminder_controls(command):
    from core.intent_router import classify_intent
    assert classify_intent(command)["intent"] == "REMINDER"


@pytest.mark.parametrize("text,action", [("Increase volume", "volume_up"), ("Decrease volume", "volume_down")])
def test_actual_dashboard_volume_commands_use_settings_tool(text, action):
    from core.intent_router import classify_intent
    result = classify_intent(text)
    assert result["intent"] == "COMPUTER_SETTINGS" and result["action"] == action


@pytest.mark.parametrize('value,ambiguous', [('Search or start a new chat', False), ('divyansh', False), ('divyansh', True)])
def test_whatsapp_search_handles_existing_query_and_rejects_ambiguous_controls(value, ambiguous):
    from actions.whatsapp_desktop_visual import WhatsAppObservation
    def line(text, y):
        return {'text': text, 'words': [{'x': 100, 'y': y, 'width': 160, 'height': 20}]}
    state = WhatsAppObservation.__new__(WhatsAppObservation)
    state.chat_left = 430
    search = line(value, 120)
    state.lines = [line('Chats', 60), search, line('All Unread 20 Favourites', 160)]
    if ambiguous:
        state.lines.append(line('Other control', 124))
    assert state.search_control() == (None if ambiguous else search)


@pytest.mark.parametrize('fails', [False, True])
def test_whatsapp_pixel_context_is_restored_even_when_observation_fails(fails):
    from actions.whatsapp_desktop_visual import execute_visual
    with patch('ctypes.windll.user32.SetThreadDpiAwarenessContext', return_value=123) as dpi, patch('actions.whatsapp_desktop_visual._execute_visual', side_effect=RuntimeError('fixture') if fails else None, return_value={'fixture': True}) as execute:
        if fails:
            with pytest.raises(RuntimeError, match='fixture'):
                execute_visual('open_chat', 'Fixture')
        else:
            assert execute_visual('open_chat', 'Fixture') == {'fixture': True}
    execute.assert_called_once_with('open_chat', 'Fixture', '', 5)
    assert dpi.call_count == 2 and dpi.call_args.args[0] == 123


def test_whatsapp_populated_search_ignores_only_right_hand_clear_icon():
    from actions.whatsapp_desktop_visual import WhatsAppObservation
    def line(text, x, y, width=65):
        return {'text': text, 'words': [{'x': x, 'y': y, 'width': width, 'height': 14}]}
    state = WhatsAppObservation.__new__(WhatsAppObservation)
    state.chat_left = 455
    query = line('DivyansN', 142, 116)
    state.lines = [line('Chats', 94, 61), query, line('x', 400, 119, 12), line('o', 44, 89, 12), line('All', 106, 164)]
    assert state.search_control() is query
    state.lines.append(line('Other control', 200, 118))
    assert state.search_control() is None


@pytest.mark.parametrize('copied,foreground,expected', [('Fixture', 42, True), ('Chats Fixture Yesterday', 42, False), ('', 42, False), ('Fixture', 99, False)])
def test_whatsapp_search_verifies_exact_editable_text_and_restores_clipboard(copied, foreground, expected):
    from actions.whatsapp_desktop_visual import _search_query_matches
    with patch('win32gui.GetForegroundWindow', side_effect=[42, foreground]), patch('pyperclip.paste', side_effect=['user clipboard', copied]), patch('pyperclip.copy') as copy, patch('pyautogui.hotkey') as hotkey, patch('actions.whatsapp_desktop_visual.time.sleep'):
        assert _search_query_matches('Fixture', 42) is expected
    assert copy.call_args.args == ('user clipboard',)
    assert hotkey.call_args_list == [call('ctrl', 'a'), call('ctrl', 'c')]


@pytest.mark.parametrize('eventual_match', [True, False])
def test_whatsapp_contact_open_waits_for_header_without_sending(eventual_match):
    from actions.whatsapp_desktop_visual import _execute_visual
    initial, search_results, loading, final = [MagicMock() for _ in range(4)]
    initial.chat_header_matches.return_value = False
    search_results.chat_left = 455
    contact = {'text': 'Fixture Yesterday', 'words': [{'x': 150, 'y': 265, 'width': 65, 'height': 15}]}
    search_results.lines = [contact]
    loading.chat_header_matches.return_value = False
    final.chat_header_matches.return_value = eventual_match
    with patch('actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop', return_value=(True, 'fixture')), patch('actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd', return_value=42), patch('actions.whatsapp_desktop_visual.WhatsAppObservation', side_effect=[initial, search_results, loading, final]), patch('actions.whatsapp_desktop_visual._paste'), patch('actions.whatsapp_desktop_visual._search_query_matches', return_value=True), patch('actions.whatsapp_desktop_visual.time.sleep'), patch('pyautogui.hotkey'), patch('pyautogui.press') as press:
        result = _execute_visual('open_chat', 'Fixture')
    assert result['success'] is eventual_match
    assert result['verified'] is eventual_match
    search_results.click_line.assert_called_once_with(contact)
    press.assert_not_called()


def test_unaddressed_local_voice_does_not_execute_or_speak():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    with patch("core.command_pipeline.process_user_command") as execute:
        result = live._on_text_command("set reminder for 7:30", source="voice")
    assert result["status"] == "VOICE_NOT_ADDRESSED"
    execute.assert_not_called()


@pytest.mark.parametrize("background_complete", [True, False])
def test_live_background_audio_cannot_speak_execute_or_pollute_memory(background_complete):
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.audio_in_queue = asyncio.Queue()
    live.audio_in_queue.put_nowait = MagicMock(wraps=live.audio_in_queue.put_nowait)
    live._mic_stats = {"transcript_events": 0, "speech_segments": 0}
    live._turn_had_tool_call = False
    live._turn_received_audio = False
    live._turn_command_results = {}
    live.set_speaking = MagicMock()
    live._check_barge_in = MagicMock()
    live._dispatch_voice_to_pipeline = MagicMock()
    live._execute_tool = AsyncMock(return_value="verified calculator response")
    command = SimpleNamespace(name="assistant_command", args={"query": "calculate 13 * 17"}, id="fixture")

    def packet(text=None, output=None, data=None, tool=False, complete=False, interrupted=False):
        sc = SimpleNamespace(interrupted=interrupted, input_transcription=SimpleNamespace(text=text) if text else None,
                             output_transcription=SimpleNamespace(text=output) if output else None, turn_complete=complete)
        return SimpleNamespace(server_content=sc, data=data,
                               tool_call=SimpleNamespace(function_calls=[command]) if tool else None)

    packets = [
        packet(text="30 पे ऐड कर लिया", tool=True),
        packet(output="Reminder set", data=b"background", complete=background_complete),
        packet(text="Hey"), packet(text="Jarvis, calculate 13 * 17", tool=True),
        packet(complete=True),  # Empty tool completion must retain the address.
        packet(output="The answer is 221.", data=b"calculator", complete=True),
        packet(text="Jarvis, explain this"),
        packet(text="set reminder for 7:30", tool=True, interrupted=True),
        packet(output="Reminder set", data=b"background", complete=True),
    ]
    class Session:
        async def receive(self):
            for item in packets:
                if item.server_content.interrupted:
                    live._apply_conversation_control('ab wait kar')
                yield item
            raise asyncio.CancelledError()
        send_tool_response = AsyncMock()
    live.session = Session()
    with patch("main._is_session_active", return_value=True), patch("main.threading.Thread") as thread:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._receive_audio())
    live._execute_tool.assert_awaited_once_with(command)
    live.audio_in_queue.put_nowait.assert_called_once_with(b"calculator")
    assert live.audio_in_queue.empty()
    assert live.session.send_tool_response.await_count == 3
    for index in (0, 2):
        rejected = live.session.send_tool_response.await_args_list[index].kwargs["function_responses"][0]
        assert rejected.response["status"] == "VOICE_NOT_ADDRESSED"
    assert thread.call_count == 1  # Only addressed conversation may update memory.
    assert all("Reminder set" not in str(call) for call in live.ui.write_log.call_args_list)
    live._dispatch_voice_to_pipeline.assert_not_called()


def test_mic_native_interfaces_are_retained_after_startup_check():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    mic, interface, volume = MagicMock(), MagicMock(), MagicMock()
    mic.Activate.return_value = interface
    volume.GetMute.return_value = 0
    volume.GetMasterVolumeLevelScalar.return_value = 1.0
    with patch("pythoncom.CoInitialize") as initialize, patch("pycaw.pycaw.AudioUtilities.GetMicrophone", return_value=mic), patch("ctypes.cast", return_value=volume):
        live._ensure_windows_mic_unmuted()
    initialize.assert_called_once()
    assert live._mic_com_refs == (mic, interface, volume)


def test_voice_health_reports_capture_and_transport_without_recording_audio(tmp_path):
    import json
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live._mic_stats = {"frames_captured": 100, "frames_accepted": 90,
                       "frames_sent": 89, "send_errors": 1, "last_rms": 42.0,
                       "last_transcript_addressed": False}
    live.ui = SimpleNamespace(muted=False)
    live.session = object()
    live._mic_accepts_audio = MagicMock(return_value=True)
    with patch("main.BASE_DIR", tmp_path), patch("main.sd.query_devices", return_value={"name": "Fixture mic"}), patch("actions.mic_control.get_jarvis_mic_enabled", return_value=True):
        live._publish_voice_health()
    path = tmp_path / "scratch" / "voice_health.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["frames_captured"] == 100 and report["frames_sent"] == 89
    assert report["capture_enabled"] and report["session_connected"]
    assert report["input_device"] == "Fixture mic"
    assert not any(key in report for key in ("audio", "transcript", "data"))
    assert not path.with_suffix(".tmp").exists()


def test_social_chat_open_checks_the_actual_conversation_page():
    from actions.social_chat import execute_social_chat
    from actions.chrome_profile import get_chrome_executable
    from playwright.async_api import async_playwright
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                context = await browser.new_context()
                await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body='<h1>Fixture</h1>'))
                page = await context.new_page()
                await page.goto("https://discord.com/channels/@me/123")
                assert (await execute_social_chat(page, "discord", "open_chat", "Fixture"))["status"] == "CHAT_OPEN_VERIFIED"
                assert (await execute_social_chat(page, "discord", "open_chat", "Missing"))["status"] == "RECIPIENT_NOT_RESOLVED"
            finally:
                await browser.close()
    asyncio.run(run())
