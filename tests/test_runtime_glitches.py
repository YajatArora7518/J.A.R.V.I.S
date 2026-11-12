"""Regression probes for phantom voice actions, speech ownership and cancellation.

Synthetic Live packets and fake audio sinks only; no desktop/account/power actions.
"""
import asyncio
from collections import OrderedDict
import queue
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_voice_user_transcript_reaches_chat_without_overwriting_assistant_reply():
    from ui import MainWindow
    window = SimpleNamespace(_log=MagicMock(), hud=MagicMock(), chat_panel=MagicMock())
    MainWindow._on_log_received(window, 'You: Jarvis, open Discord')
    window.hud.appendChat.assert_called_once_with('You', 'Jarvis, open Discord')
    window.chat_panel.append_message.assert_called_once_with('You', 'Jarvis, open Discord')
    window.hud.setResponse.assert_not_called()


def health_fixture():
    from core.ollama_health_manager import OllamaHealthManager, STATUS_UNAVAILABLE
    manager = OllamaHealthManager.__new__(OllamaHealthManager)
    manager._lock = threading.Lock()
    manager._is_recovering = False
    manager._next_recovery_at = 0.0
    manager._recovery_cooldown_sec = 300.0
    manager._last_status = STATUS_UNAVAILABLE
    manager._cached_health = {'ready': False}
    manager._latencies = []
    manager._consecutive_failures = 1
    manager.base_url = 'http://fixture.invalid'
    return manager


def test_unavailable_local_provider_recovery_is_rate_limited_and_reserved_before_spawn():
    manager = health_fixture()
    with patch('core.ollama_health_manager.threading.Thread') as worker, patch('core.ollama_health_manager.time.monotonic', return_value=10):
        manager._trigger_recovery()
        manager._trigger_recovery()
        worker.assert_called_once()
        assert manager._is_recovering
        with patch('core.ollama_health_manager.auto_start_ollama', return_value=False):
            worker.call_args.kwargs['target']()
        assert not manager._is_recovering
        manager._trigger_recovery()
        worker.assert_called_once()
    with patch('core.ollama_health_manager.threading.Thread') as worker, patch('core.ollama_health_manager.time.monotonic', return_value=311):
        manager._trigger_recovery()
        worker.assert_called_once()


def test_local_provider_health_recovers_without_waiting_for_recovery_cooldown():
    manager = health_fixture()
    manager._next_recovery_at = 300
    with patch('core.ollama_health_manager.check_ollama_health', return_value={'ready': True, 'models': []}):
        manager._run_check()
    assert manager._next_recovery_at == 0
    assert manager.is_healthy()
    manager._cached_health = {'ready': False}
    assert not manager.is_healthy()
    assert not manager.get_hud_status()['is_online']


def live_fixture():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock(muted=False)
    live.audio_in_queue = asyncio.Queue()
    live._mic_stats = {'transcript_events': 0, 'speech_segments': 0}
    live._turn_had_tool_call = live._turn_received_audio = False
    live._turn_command_results = {}
    live.set_speaking = MagicMock()
    live._check_barge_in = MagicMock()
    live._observe_companion_turn = MagicMock()
    live._dispatch_voice_to_pipeline = MagicMock()
    live.speak = MagicMock()
    return live


def packet(text=None, output=None, data=None, tool=None, complete=False):
    return SimpleNamespace(data=data, tool_call=SimpleNamespace(function_calls=[tool]) if tool else None,
        server_content=SimpleNamespace(interrupted=False, turn_complete=complete,
            input_transcription=SimpleNamespace(text=text) if text else None,
            output_transcription=SimpleNamespace(text=output) if output else None))


def run_packets(live, packets):
    class Session:
        async def receive(self):
            for item in packets:
                yield item
            raise asyncio.CancelledError()
        send_tool_response = AsyncMock()
    live.session = Session()
    with patch('main._is_session_active', return_value=True), patch('main.threading.Thread') as thread:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._receive_audio())
    return [call for call in thread.call_args_list if call.kwargs.get('target') == live._dispatch_voice_to_pipeline]


@pytest.mark.parametrize('command', ['open Discord', 'WhatsApp par Fixture ko message bhejo Hello',
                                    'screen pe kya hai', 'restart my laptop', 'calculate 7 * 6'])
def test_spoken_action_claim_without_tool_is_suppressed_and_routed_once(command):
    live = live_fixture()
    dispatches = run_packets(live, [packet(text='Jarvis, '+command, output='Already done!', data=b'phantom', complete=True)])
    assert len(dispatches) == 1
    assert dispatches[0].kwargs['args'][0] == 'Jarvis, '+command
    assert live.audio_in_queue.empty()
    assert all('Already done!' not in str(call) for call in live.ui.write_log.call_args_list)
    live.speak.assert_not_called()


@pytest.mark.parametrize('success,verified', [(False, False), (True, False), (True, True)])
def test_attempted_action_never_retries_and_failed_result_replaces_model_claim(success, verified):
    live = live_fixture()
    fc = SimpleNamespace(name='assistant_command', id='fixture', args={'query':'open Discord'})
    result = {'success': success, 'verified': verified, 'message': 'Actual tool result'}
    live._execute_tool = AsyncMock(return_value=SimpleNamespace(response=result))
    dispatches = run_packets(live, [packet(text='Jarvis, open Discord', tool=fc),
                                   packet(output='Opened Discord', data=b'model', complete=True)])
    assert dispatches == []
    live._execute_tool.assert_awaited_once_with(fc)
    if success and verified:
        assert live.audio_in_queue.get_nowait() == b'model'
        live.speak.assert_not_called()
    else:
        assert live.audio_in_queue.empty()
        live.speak.assert_called_once_with('Actual tool result')
        assert all('Opened Discord' not in str(call) for call in live.ui.write_log.call_args_list)


def test_save_memory_does_not_count_as_opening_an_app():
    live = live_fixture()
    fc = SimpleNamespace(name='save_memory', id='fixture', args={})
    live._execute_tool = AsyncMock(return_value=SimpleNamespace(response={'result':'ok'}))
    dispatches = run_packets(live, [packet(text='Jarvis, open Discord', tool=fc),
                                   packet(output='Done!', data=b'phantom', complete=True)])
    assert len(dispatches) == 1 and live.audio_in_queue.empty()


def test_conversation_audio_does_not_create_laptop_action():
    live = live_fixture()
    assert run_packets(live, [packet(text='Jarvis, explain loops', output='A loop repeats steps.', data=b'lesson', complete=True)]) == []
    assert live.audio_in_queue.get_nowait() == b'lesson'


def test_audio_packets_do_not_reclassify_the_same_command():
    live = live_fixture()
    live._voice_requires_pipeline = MagicMock(return_value=False)
    run_packets(live, [packet(text='Jarvis, explain loops'), packet(data=b'one'),
                       packet(data=b'two'), packet(output='A loop repeats.', complete=True)])
    live._voice_requires_pipeline.assert_called_once_with('Jarvis, explain loops')


@pytest.mark.parametrize('title,owner,expected', [('Discord Updater',7,False), ('Discord Setup',7,False),
                                               ('Friends - Discord',7,True), ('Friends - Discord',22,False)])
def test_updater_and_unrelated_windows_cannot_verify_the_app(title, owner, expected):
    from actions.application_launch_executor import ApplicationLaunchExecutor
    descriptor = SimpleNamespace(process_names=['Discord.exe'], display_name='Discord')
    process = SimpleNamespace(info={'pid':7,'name':'Discord.exe'})
    with patch('actions.application_launch_executor.platform.system', return_value='Windows'), patch('actions.application_launch_executor.psutil.process_iter', return_value=[process]), patch('win32gui.EnumWindows', side_effect=lambda cb, arg: cb(10,arg)), patch('win32gui.IsWindowVisible', return_value=True), patch('win32gui.GetWindowText', return_value=title), patch('win32process.GetWindowThreadProcessId', return_value=(1,owner)), patch('win32gui.GetForegroundWindow', return_value=10), patch('win32gui.IsIconic', return_value=False), patch('win32gui.SetForegroundWindow') as focus:
        executor = ApplicationLaunchExecutor()
        assert executor._verify_application_launched(descriptor)['verified'] is expected
        assert executor._try_focus_existing(descriptor) is expected
    if not expected:
        focus.assert_not_called()


def test_startup_window_does_not_trigger_duplicate_launch_or_fake_completion():
    from actions.application_launch_executor import ApplicationLaunchExecutor
    executor = ApplicationLaunchExecutor()
    descriptor = SimpleNamespace(display_name='Discord', launch_type='WIN32_EXECUTABLE')
    with patch.object(executor, '_try_focus_existing', return_value=False), patch.object(executor, '_execute_launch_strategy', return_value=True) as launch, patch.object(executor, '_verify_application_launched', return_value={'verified':False,'startup_pending':True}), patch('actions.application_launch_executor.time.sleep'):
        result = executor.launch_application('Discord', descriptor)
    launch.assert_called_once()
    assert not result.verification_passed and result.failure_reason == 'startup_pending'
    assert 'Opened' not in result.message and 'ready nahi' in result.message


def test_fast_ready_app_finishes_without_fixed_startup_sleep():
    from actions.application_launch_executor import ApplicationLaunchExecutor
    executor = ApplicationLaunchExecutor()
    descriptor = SimpleNamespace(display_name='Fixture', launch_type='WIN32_EXECUTABLE')
    with patch.object(executor, '_try_focus_existing', side_effect=[False,True]), patch.object(executor, '_execute_launch_strategy', return_value=True), patch.object(executor, '_verify_application_launched', return_value={'verified':True}), patch('actions.application_launch_executor.time.sleep') as sleep:
        result = executor.launch_application('Fixture', descriptor)
    assert result.verification_passed
    sleep.assert_not_called()


@pytest.mark.parametrize('survives_third_session,expected_attempts', [(False,3),(True,5)])
def test_immediately_failing_connections_are_bounded_and_stable_sessions_reset_retry_budget(survives_third_session, expected_attempts):
    live = live_fixture()
    live._build_config = MagicMock()
    live._flush_out_queue = MagicMock()
    live._send_realtime = AsyncMock(side_effect=RuntimeError('Synthetic provider 1011'))
    live._listen_audio = AsyncMock()
    live._receive_audio = AsyncMock()
    live._play_audio = AsyncMock()
    live._local_stt_loop = AsyncMock()
    client = MagicMock()
    times = [100,100,100,100,100,140,140,140,140,140] if survives_third_session else [100]*6
    # Replace the module reference, not time.monotonic globally: asyncio uses
    # the real monotonic clock for scheduling and shutdown.
    clock = SimpleNamespace(monotonic=MagicMock(side_effect=times))
    with patch('main.genai.Client', return_value=client), patch('main._get_api_key', return_value='fixture'), patch('main.get_runtime_config', return_value={'live_fallback_models':[]}), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('main.time', clock), patch('main.asyncio.sleep', new_callable=AsyncMock):
        asyncio.run(live.run())
    assert client.aio.live.connect.call_count == expected_attempts
    assert live._mic_stats['reconnect_count'] == expected_attempts
    live._local_stt_loop.assert_awaited_once()
    assert live._local_voice_active


@pytest.mark.parametrize('owner', ['tts', 'playback', 'queue', 'none'])
def test_watchdog_only_recovers_a_truly_idle_speech_state(owner):
    live = live_fixture()
    live._speaking_lock = threading.Lock()
    live._is_speaking = True
    live._last_audio_chunk_time = 50.0
    live._last_speaking_time = 20.0
    live._playback_active = owner == 'playback'
    live.tts_engine = MagicMock()
    live.tts_engine.is_speaking.return_value = owner == 'tts'
    live._update_proactive_state = MagicMock()
    if owner == 'queue':
        live.audio_in_queue.put_nowait(b'pending')
    with patch('main.time.time', return_value=100.0):
        live._voice_watchdog_tick()
    if owner == 'none':
        live.set_speaking.assert_called_once_with(False)
    else:
        live.set_speaking.assert_not_called()


@pytest.mark.parametrize('muted,busy,state', [(False,True,'SPEAKING'),(False,False,'LISTENING'),(True,False,'IDLE')])
def test_connection_status_does_not_show_listening_over_active_speech(muted,busy,state):
    live = live_fixture()
    live.ui.muted = muted
    live.tts_engine = MagicMock()
    live.tts_engine.is_speaking.return_value = busy
    live._show_ready_voice_state()
    live.ui.set_state.assert_called_once_with(state)


@pytest.mark.parametrize('owner', ['tts', 'playback', 'queue'])
def test_turn_complete_cannot_unmute_before_audio_finishes(owner):
    from main import JarvisLive
    live = live_fixture()
    live._speaking_lock = threading.Lock()
    live._is_speaking = True
    live._playback_active = owner == 'playback'
    live._flush_out_queue = MagicMock()
    live._update_proactive_state = MagicMock()
    live.tts_engine = MagicMock()
    live.tts_engine.is_speaking.return_value = owner == 'tts'
    if owner == 'queue':
        live.audio_in_queue.put_nowait(b'pending')
    JarvisLive.set_speaking(live, False)
    assert live._is_speaking and not live._flush_out_queue.called
    JarvisLive.set_speaking(live, False, force=True)
    assert not live._is_speaking


def speech_fixture():
    from core.tts_engine import UniversalTTSEngine
    engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
    engine._speech_queue = queue.Queue()
    engine._lock = threading.Lock()
    engine._stop_requested = threading.Event()
    engine._running = True
    engine._is_speaking = False
    engine._speech_generation = 0
    engine._last_spoken_text = ''
    engine._last_spoken_time = 0.0
    engine._dedup_window_sec = 2.0
    engine._sapi_init_failed = False
    engine._sapi_voice = MagicMock()
    engine._init_sapi = MagicMock(return_value=engine._sapi_voice)
    engine._on_start_cb = MagicMock()
    engine._on_end_cb = MagicMock()
    engine._cloud_speech_loop = engine._cloud_speech_task = None
    engine._cloud_retry_after = 0.0
    engine._audio_cache = OrderedDict()
    engine._audio_cache_bytes = 0
    return engine


def test_stop_cancels_dequeued_old_generation_before_speech_starts():
    engine = speech_fixture()
    engine._speech_queue.put(('Old reply', False, 0))
    engine._speech_generation = 1  # stop happened after dequeue, before activation
    engine._speech_queue.put(None)
    engine._speak_natural = MagicMock(return_value=False)
    engine._worker_loop()
    engine._speak_natural.assert_not_called()
    engine._sapi_voice.Speak.assert_not_called()
    engine._on_start_cb.assert_not_called()
    assert engine._speech_queue.unfinished_tasks == 0


def test_stop_at_cloud_fallback_boundary_does_not_speak_cancelled_text():
    engine = speech_fixture()
    engine.speak('Old reply')
    def cancelled(text):
        engine.stop()
        engine._speech_queue.put(None)
        return False
    engine._speak_natural = MagicMock(side_effect=cancelled)
    engine._worker_loop()
    assert not any(call.args and call.args[0] == 'Old reply' for call in engine._sapi_voice.Speak.call_args_list)
    assert engine._speech_queue.unfinished_tasks == 0


def test_new_identical_reply_after_stop_is_accepted_as_new_request():
    engine = speech_fixture()
    assert engine.speak('Haan, bolo.')
    old_generation = engine._speech_queue.queue[0][2]
    engine.stop()
    assert engine.speak('Haan, bolo.')
    assert engine._speech_queue.get_nowait()[2] > old_generation


def test_large_cached_audio_packet_can_stop_after_one_small_write():
    engine = speech_fixture()
    engine._audio_cache[('fixture', 'Charon', 'Haan, bolo.')] = (b'\0' * 48000,)
    with patch('config.get_runtime_config', return_value={'natural_chat_voice': True, 'voice_name':'Charon'}), patch('config.get_api_key', return_value='fixture'), patch('config.get_live_model_name', return_value='fixture'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('google.genai.Client') as factory, patch('sounddevice.RawOutputStream') as output:
        sink = output.return_value.__enter__.return_value
        sink.write.side_effect = lambda audio: engine.stop()
        assert engine._speak_natural('Haan, bolo.')
    factory.assert_not_called()
    assert sink.write.call_count == 1 and len(sink.write.call_args.args[0]) == 2400


def test_large_live_audio_packet_does_not_continue_after_cancel_generation():
    live = live_fixture()
    live._live_speech_generation = 0
    class AudioQueue:
        calls = 0
        async def get(self):
            self.calls += 1
            if self.calls == 1:
                return b'\0' * 48000
            raise asyncio.CancelledError()
        def empty(self):
            return self.calls > 0
    live.audio_in_queue = AudioQueue()
    with patch('main.sd.RawOutputStream') as output:
        sink = output.return_value
        sink.write.side_effect = lambda audio: setattr(live, '_live_speech_generation', 1)
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._play_audio())
    assert sink.write.call_count == 1 and len(sink.write.call_args.args[0]) == 2400
    assert live._playback_active is False


@pytest.mark.parametrize('complete', [True, False])
def test_only_complete_natural_reply_is_cached_without_repeat_cloud_request(complete):
    engine = speech_fixture()
    class Session:
        send_client_content = AsyncMock()
        async def receive(self):
            yield SimpleNamespace(data=b'\0\0', server_content=SimpleNamespace(turn_complete=complete))
            if not complete:
                raise OSError('Synthetic disconnect')
    client = MagicMock()
    client.aio.live.connect.return_value.__aenter__.return_value = Session()
    client.aio.aclose = AsyncMock()
    with patch('config.get_runtime_config', return_value={'natural_chat_voice': True, 'voice_name':'Charon'}), patch('config.get_api_key', return_value='fixture'), patch('config.get_live_model_name', return_value='fixture'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('google.genai.Client', return_value=client) as factory, patch('sounddevice.RawOutputStream'):
        assert engine._speak_natural('Haan, bolo.')
        if complete:
            assert engine._speak_natural('Haan, bolo.')
            factory.assert_called_once()
            assert engine._audio_cache_bytes == 2
        else:
            assert not engine._audio_cache and engine._audio_cache_bytes == 0
