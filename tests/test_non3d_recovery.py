"""Failure injection only: no real microphone, messages, calls or desktop actions."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from tests.test_runtime_glitches import live_fixture, packet, speech_fixture
from tests.test_source_grounding import page, search_data, model_claim, audit_ok


@pytest.mark.parametrize('failure', ['receive', 'send', 'closed', 'after_complete', 'after_audio'])
def test_completed_voice_command_survives_disconnect_without_reexecution(failure):
    live = live_fixture()
    result = {'success': True, 'verified': True, 'message': 'Iska jawab 42 hai, bhai.',
              'authoritative_response': failure != 'after_audio'}
    live._execute_tool = AsyncMock(return_value=SimpleNamespace(response=result))
    call = SimpleNamespace(name='assistant_command', id='fixture', args={'query':'calculate 7 * 6'})
    class Session:
        send_tool_response = AsyncMock(side_effect=OSError('Synthetic send disconnect') if failure == 'send' else None)
        async def receive(self):
            yield packet(text='Jarvis, calculate 7 * 6', tool=call)
            if failure == 'after_complete':
                yield packet(complete=True)
            elif failure == 'after_audio':
                yield packet(data=b'accepted voice audio')
            raise OSError('Synthetic receive disconnect')
    live.session = Session()
    with patch('main._is_session_active', return_value=failure != 'closed'), patch('main.traceback.print_exc'), patch('main.threading.Thread') as threads:
        with pytest.raises(Exception):
            asyncio.run(live._receive_audio())
    live._execute_tool.assert_awaited_once_with(call)
    assert not any(c.kwargs.get('target') == live._dispatch_voice_to_pipeline for c in threads.call_args_list)
    if failure == 'after_audio':
        live.speak.assert_not_called()
    else:
        live.speak.assert_called_once_with(result['message'])


def test_unexpected_speech_failure_finishes_queue_item_and_allows_next_reply():
    engine = speech_fixture()
    engine._speak_natural = MagicMock(side_effect=[RuntimeError('Synthetic synthesis crash'), True])
    engine.speak('First reply')
    engine.speak('Second reply')
    engine._speech_queue.put(None)
    engine._worker_loop()
    assert engine._speech_queue.unfinished_tasks == 0
    assert [c.args[0] for c in engine._speak_natural.call_args_list] == ['First reply', 'Second reply']
    assert not engine.is_speaking() and not engine.is_playing()
    assert engine._on_end_cb.call_count == 2


@pytest.mark.parametrize('failure', ['synthesis_exception', 'check_exception', 'null_response', 'null_claim_text', 'null_check', 'null_quote'])
def test_web_reasoning_failures_keep_answer_unverified(failure):
    from actions.web_research import answer_from_pages
    quote = 'Virat Kohli brought up his 55th ODI century in the match.'
    valid = model_claim('Kohli ke 55 ODI centuries hain.', quote)
    brain = MagicMock()
    answers = {
        'synthesis_exception': [RuntimeError('Synthetic provider down')],
        'check_exception': [valid, RuntimeError('Synthetic checker down')],
        'null_response': [None],
        'null_check': [valid, None],
        'null_quote': [model_claim('Kohli ke 55 ODI centuries hain.', None), audit_ok()],
        'null_claim_text': [{'success': True, 'text': json.dumps({'supported': True, 'claims':[
            {'text':None, 'source':1, 'quote':quote}]})}, audit_ok()],
    }
    brain.generate_response.side_effect = answers[failure]
    with patch('actions.web_research.fetch_webpage', return_value=page(quote)), patch('core.ai_multitier_engine.get_ai_engine', return_value=brain):
        result = answer_from_pages('Virat Kohli ODI centuries', search_data(), current=True)
    assert not result['success'] and not result['verified']
    assert result['status'] == 'WEB_ANSWER_UNVERIFIED' and result['authoritative_response']


@pytest.mark.parametrize('failure', ['http_error', 'stream_error'])
def test_failed_webpage_read_closes_the_response(failure):
    from actions.fetch_webpage import fetch_webpage
    response = MagicMock(status_code=200, encoding='utf-8', headers={})
    if failure == 'http_error':
        response.raise_for_status.side_effect = requests.HTTPError('Synthetic HTTP failure')
    else:
        response.iter_content.side_effect = OSError('Synthetic stream failure')
    with patch('actions.fetch_webpage._check_public_url'), patch('actions.fetch_webpage._session_get', return_value=response):
        result = fetch_webpage('https://fixture.example/article')
    assert not result['success']
    response.close.assert_called_once()


@pytest.mark.parametrize('ending', ['cancelled', 'interrupted', 'silent'])
def test_disconnect_fallback_respects_silence_and_user_interruption(ending):
    live = live_fixture()
    result = {'success': True, 'verified': True, 'message': 'Actual result',
              'silent': ending == 'silent', 'authoritative_response': True}
    live._execute_tool = AsyncMock(return_value=SimpleNamespace(response=result))
    call = SimpleNamespace(name='assistant_command', id='fixture', args={})
    class Session:
        send_tool_response = AsyncMock()
        async def receive(self):
            yield packet(text='Jarvis, calculate 7 * 6', tool=call)
            if ending == 'interrupted':
                event = packet()
                event.server_content.interrupted = True
                yield event
            if ending == 'cancelled':
                raise asyncio.CancelledError()
            raise OSError('Synthetic disconnect')
    live.session = Session()
    with patch('main._is_session_active', return_value=True), patch('main.traceback.print_exc'):
        with pytest.raises(asyncio.CancelledError if ending == 'cancelled' else OSError):
            asyncio.run(live._receive_audio())
    live._execute_tool.assert_awaited_once_with(call)
    live.speak.assert_not_called()
