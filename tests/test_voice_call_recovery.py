"""Quota and delayed-popup regressions: no real audio, calls or contacts."""
import asyncio
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def quota_error(status=429, headers=None, body=None):
    response = httpx.Response(status, headers=headers, json=body or {},
                              request=httpx.Request('POST', 'https://fixture.invalid/tts'))
    return httpx.HTTPStatusError('fixture', request=response.request, response=response)


@pytest.mark.parametrize('headers,body,expected', [
    ({'Retry-After': '3600'}, {}, 3600),
    ({}, {'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '90.5s'}]}}, 90.5),
    ({}, {'error': {'message': 'Please retry in 17h27m55s or upgrade.'}}, 62875),
    ({'Retry-After': 'Infinity'}, {'error': {'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '-2s'}]}}, 30),
    ({'Retry-After': '999999'}, {}, 86400),
    ({'Retry-After': 'not a date'}, {'error': 'malformed'}, 30),
])
def test_quota_respects_server_delay_without_trusting_malformed_values(headers, body, expected):
    from core.tts_engine import _voice_retry_seconds
    assert _voice_retry_seconds(quota_error(headers=headers, body=body)) == expected


def test_quota_http_date_and_exponential_fallback_are_bounded():
    from core.tts_engine import _voice_retry_seconds
    header = format_datetime(datetime.now(timezone.utc) + timedelta(minutes=15), usegmt=True)
    assert 898 <= _voice_retry_seconds(quota_error(headers={'Retry-After': header})) <= 900
    assert _voice_retry_seconds(quota_error(), failures=2) == 60
    assert _voice_retry_seconds(quota_error(), failures=1000) == 300
    assert _voice_retry_seconds(quota_error(status=400, headers={'Retry-After': '3600'})) == 30


def test_quota_blocks_repeat_provider_requests_and_explains_wait_without_robot_voice():
    from tests.test_runtime_glitches import speech_fixture
    engine = speech_fixture()
    engine._on_notice_cb = MagicMock()
    client = MagicMock()
    client.post = AsyncMock(side_effect=quota_error(headers={'Retry-After': '3600'}))
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    prefs = {'natural_chat_voice': True, 'natural_voice_backend': 'gemini_tts',
             'voice_name': 'Charon', 'allow_robotic_voice_fallback': False}
    with patch('httpx.AsyncClient', return_value=context), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('config.get_api_key', return_value='fixture'), patch('config.get_runtime_config', return_value=prefs):
        assert not engine._speak_natural('First reply')
        assert not engine._speak_natural('Second reply')
        engine.speak('Third reply')
        engine._speech_queue.put(None)
        engine._worker_loop()
    client.post.assert_awaited_once()
    engine._sapi_voice.Speak.assert_not_called()
    assert 'rate limit' in engine._on_notice_cb.call_args.args[0]
    assert '60 minute' in engine._on_notice_cb.call_args.args[0]
    assert engine._speech_queue.unfinished_tasks == 0


@pytest.mark.parametrize('observations,verified', [
    ([(123, ['Fixture', '17:47']), (456, ['Fixture', 'Calling...'])], True),
    ([(456, ['Other Person', '00:10'])] * 4, False),
    ([(123, ['Fixture', 'Calling...'])] * 4, False),
    ([(123, ['Fixture', '17:47'])] * 4, False),
])
def test_delayed_call_popup_is_observed_without_second_click(observations, verified):
    from actions.whatsapp_desktop_icons import execute_icon_call
    state = SimpleNamespace(rect=(0, 0, 900, 600), chat_header_matches=lambda recipient: True)
    frames = iter(observations)
    def read_text(hwnd):
        return next(frames)[1]
    # Before-click guard and then each current snapshot's own hwnd.
    foreground = iter([123] + [frame[0] for frame in observations])
    with patch('actions.whatsapp_desktop_visual.execute_visual', return_value={'success': True, 'verified': True}), patch('actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd', return_value=123), patch('actions.whatsapp_desktop_visual.WhatsAppObservation', return_value=state), patch('actions.whatsapp_desktop_icons.find_voice_icon', return_value={'x': 800, 'y': 70}), patch('win32gui.GetForegroundWindow', side_effect=lambda: next(foreground)), patch('win32gui.GetWindowRect', return_value=state.rect), patch('actions.whatsapp_desktop_icons._call_text', side_effect=read_text) as observe, patch('actions.whatsapp_desktop_icons.time.sleep'), patch('pyautogui.click') as click:
        result = execute_icon_call('voice_call', 'Fixture')
    click.assert_called_once_with(800, 70)
    assert result['verified'] is verified
    assert observe.call_count == len(observations)
    assert result['status'] == ('CALL_UI_ACTIVE' if verified else 'CALL_UNVERIFIED')


def test_youtube_card_whitespace_does_not_pollute_speech():
    from actions.youtube_browser import search_videos
    card, link, channel = MagicMock(), MagicMock(), MagicMock()
    link.get_attribute = AsyncMock(return_value='/watch?v=abcdefghijk')
    link.inner_text = AsyncMock(return_value=' KTG\n & THERMO   revision ')
    channel.count = AsyncMock(return_value=1)
    channel.inner_text = AsyncMock(return_value=' \n\n    JEE Wallah  ')
    card.locator.side_effect = lambda selector: SimpleNamespace(first=link if selector == 'a#video-title' else channel)
    cards = MagicMock()
    cards.first.wait_for = AsyncMock()
    cards.count = AsyncMock(return_value=1)
    cards.nth.return_value = card
    page = MagicMock()
    page.goto = AsyncMock()
    page.locator.return_value = cards
    with patch('actions.browser_automation.browser_automation_engine.get_or_open_page', new=AsyncMock(return_value=page)):
        _, items = asyncio.run(search_videos('thermo ktg'))
    assert items[0]['title'] == 'KTG & THERMO revision'
    assert items[0]['channel'] == 'JEE Wallah'


@pytest.mark.parametrize('primary_spoke', [True, False])
def test_charon_live_backup_uses_reply_only_and_never_repeats_partial_tts(primary_spoke):
    from tests.test_runtime_glitches import speech_fixture
    engine = speech_fixture()
    prefs = {'natural_chat_voice': True, 'natural_voice_backend': 'gemini_tts',
             'natural_voice_live_fallback': True, 'voice_name': 'Charon'}
    class Session:
        send_client_content = AsyncMock()
        async def receive(self):
            yield SimpleNamespace(data=b'\0\0', server_content=SimpleNamespace(turn_complete=True))
    session = Session()
    client = MagicMock()
    client.aio.live.connect.return_value.__aenter__.return_value = session
    client.aio.aclose = AsyncMock()
    def limited(*args):
        engine._voice_rate_limited = True
        engine._tts_retry_after = __import__('time').monotonic() + 3600
        return primary_spoke
    with patch.object(engine, '_speak_generated', side_effect=limited) as primary, patch('config.get_runtime_config', return_value=prefs), patch('config.get_api_key', return_value='fixture'), patch('config.get_live_model_name', return_value='live-fixture'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('google.genai.Client', return_value=client) as factory, patch('sounddevice.RawOutputStream'):
        assert engine._speak_natural('Haan, bolo.')
        if primary_spoke:
            factory.assert_not_called()
            return
        # During TTS cooldown the next identical reply uses the Live audio cache.
        assert engine._speak_natural('Haan, bolo.')
    primary.assert_called_once()
    factory.assert_called_once()
    setup = client.aio.live.connect.call_args.kwargs['config']
    assert setup.speech_config.voice_config.prebuilt_voice_config.voice_name == 'Charon'
    assert not setup.tools and not setup.input_audio_transcription
    assert session.send_client_content.await_args.kwargs['turns'].parts[0].text == 'Haan, bolo.'


def test_live_backup_failure_gets_its_own_cooldown_and_does_not_loop():
    from tests.test_runtime_glitches import speech_fixture
    engine = speech_fixture()
    engine._voice_rate_limited = True
    engine._tts_retry_after = __import__('time').monotonic() + 3600
    client = MagicMock()
    client.aio.live.connect.return_value.__aenter__.side_effect = OSError('fixture')
    client.aio.aclose = AsyncMock()
    prefs = {'natural_chat_voice': True, 'natural_voice_backend': 'gemini_tts',
             'natural_voice_live_fallback': True, 'voice_name': 'Charon'}
    with patch.object(engine, '_speak_generated') as primary, patch('config.get_runtime_config', return_value=prefs), patch('config.get_api_key', return_value='fixture'), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('google.genai.Client', return_value=client) as factory:
        assert not engine._speak_natural('Haan, bolo.')
        assert not engine._speak_natural('Doosra reply')
    primary.assert_not_called()
    factory.assert_called_once()
