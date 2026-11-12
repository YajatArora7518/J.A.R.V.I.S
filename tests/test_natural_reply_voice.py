"""Natural reply playback without any external requests or device output."""
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


@pytest.mark.parametrize('audio,error,stopped,expected', [
    (False, False, False, False), (False, True, False, False),
    (True, False, False, True), (True, True, False, True),
    (False, False, True, True),
])
def test_natural_reply_falls_back_only_before_any_playback(audio, error, stopped, expected):
    from core.tts_engine import UniversalTTSEngine
    engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
    engine._cloud_retry_after = 0.0
    engine._stop_requested = threading.Event()
    if stopped:
        engine._stop_requested.set()
    class Session:
        send_client_content = AsyncMock()
        async def receive(self):
            yield SimpleNamespace(data=b'\x00\x00' if audio else None,
                                  server_content=SimpleNamespace(turn_complete=not error))
            if error:
                raise OSError('fixture disconnected')
    session = Session()
    client = MagicMock()
    client.aio.live.connect.return_value.__aenter__.return_value = session
    client.aio.aclose = AsyncMock()
    with patch('config.get_runtime_config', return_value={'natural_chat_voice': True, 'voice_name': 'Charon'}), patch('config.get_api_key', return_value='fixture'), patch('config.get_live_model_name', return_value='fixture-model'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('google.genai.Client', return_value=client), patch('sounddevice.RawOutputStream') as output:
        assert engine._speak_natural('Haan, bolo.') is expected
    if stopped:
        client.aio.live.connect.assert_not_called()
        output.assert_not_called()
        return
    setup = client.aio.live.connect.call_args.kwargs['config']
    assert not setup.tools and not setup.input_audio_transcription
    assert setup.speech_config.voice_config.prebuilt_voice_config.voice_name == 'Charon'
    assert session.send_client_content.await_args.kwargs['turns'].parts[0].text == 'Haan, bolo.'
    if stopped:
        output.return_value.__enter__.return_value.write.assert_not_called()
    elif audio:
        output.return_value.__enter__.return_value.write.assert_called_once_with(b'\x00\x00')
    client.aio.aclose.assert_awaited_once()
    assert engine._cloud_speech_loop is None and engine._cloud_speech_task is None


@pytest.mark.parametrize('opt_in,policy', [(False, True), (True, False)])
def test_natural_reply_requires_opt_in_and_cloud_policy(opt_in, policy):
    from core.tts_engine import UniversalTTSEngine
    engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
    with patch('config.get_runtime_config', return_value={'natural_chat_voice': opt_in}), patch('core.ai_policy.is_cloud_ai_allowed', return_value=policy), patch('google.genai.Client') as client:
        assert not engine._speak_natural('Fixture')
    client.assert_not_called()


def test_natural_reply_stop_cancels_waiting_audio():
    from core.tts_engine import UniversalTTSEngine
    engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
    engine._lock = threading.Lock()
    engine._stop_requested = threading.Event()
    engine._speech_queue = __import__('queue').Queue()
    engine._sapi_voice = None
    engine._cloud_speech_loop = MagicMock()
    engine._cloud_speech_loop.is_closed.return_value = False
    engine._cloud_speech_task = MagicMock()
    engine.stop()
    engine._cloud_speech_loop.call_soon_threadsafe.assert_called_once_with(engine._cloud_speech_task.cancel)
