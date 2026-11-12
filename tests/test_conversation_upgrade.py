import asyncio
import base64
from collections import OrderedDict
from types import SimpleNamespace
import threading
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


def test_conversation_continues_until_explicit_pause_and_stop_keeps_it_open():
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock(muted=False)
    live.tts_engine = MagicMock()
    with patch('actions.mic_control.get_jarvis_mic_enabled', return_value=True):
        live._request_voice_followup()
    live._voice_followup_deadline = 0
    assert live._voice_is_addressed('aur bata')
    assert not live._voice_is_addressed('')
    live._apply_conversation_control('ruk')
    assert live._voice_is_addressed('calculate 13 * 17')
    live._apply_conversation_control('ab wait kar')
    assert not live._voice_is_addressed('open Discord')
    assert live._voice_is_addressed('Jarvis, open Discord')
    live._apply_conversation_control('baat karte hain')
    assert live._voice_is_addressed('sun raha hai')
    assert live._apply_conversation_control('explain why I should wait') is None


def test_only_verified_app_results_are_rephrased():
    from core.voice_conversation import natural_action_reply
    assert natural_action_reply({'success':True,'verified':True,'message':'Opened Discord.'}) == 'Discord khol diya, bhai.'
    assert natural_action_reply({'success':True,'verified':False,'message':'Opened Discord.'}) == 'Opened Discord.'
    assert natural_action_reply({'success':True,'verified':True,'message':'Message: Opened Discord.'}) == 'Message: Opened Discord.'


@pytest.mark.parametrize('status', ['failed','unverified','confirmation','okay'])
def test_sequence_steps_verify_and_stop_without_retry(status):
    from core.command_sequence import execute_sequence
    first = {'success': status!='failed', 'verified': status in {'confirmation','okay'},
             'requires_confirmation': status=='confirmation', 'message': 'actual result'}
    execute = MagicMock(side_effect=[first, {'success': True,'verified':True,'message':'42'}])
    result = execute_sequence('open Discord then calculate 6 * 7', 'chat', execute)
    assert execute.call_count == (2 if status=='okay' else 1)
    assert result['verified'] == (status=='okay')
    if status!='okay': assert result['remaining_commands'] == ['calculate 6 * 7']


def test_sequence_preserves_quoted_message_and_requires_unambiguous_payload():
    from core.command_sequence import split_sequence, execute_sequence
    text = 'WhatsApp par Fixture ko message bhejo "open Discord then calculate 6 * 7" then open Discord'
    parts = split_sequence(text)
    assert parts and len(parts)==2 and 'then calculate' in parts[0]
    execute = MagicMock(return_value={'success': True,'verified':True,'message':'okay'})
    assert execute_sequence(text,'voice',execute)['verified']
    execute.reset_mock()
    result = execute_sequence('WhatsApp par Fixture ko message bhejo hello then open Discord','voice',execute)
    assert result['status']=='SEQUENCE_DETAILS_REQUIRED'
    execute.assert_not_called()
    result = execute_sequence('WhatsApp kholo aur Mumma ko hello bhej','chat',execute)
    assert result['status']=='SEQUENCE_DETAILS_REQUIRED'
    execute.assert_not_called()
    assert split_sequence('explain arrays and pointers') is None


def test_dedicated_tts_has_no_tools_context_and_supports_cache():
    from core.tts_engine import UniversalTTSEngine
    engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
    engine._stop_requested = threading.Event()
    engine._cloud_retry_after=0
    engine._audio_cache=OrderedDict();engine._audio_cache_bytes=0
    response=MagicMock()
    response.json.return_value={'steps':[{'type':'model_output','content':[{'type':'audio','mime_type':'audio/l16','data':base64.b64encode(b'\x01\x00'*120).decode()}]}]}
    client=MagicMock()
    client.post=AsyncMock(return_value=response)
    context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock()
    with patch('httpx.AsyncClient',return_value=context), patch('core.ai_policy.assert_cloud_ai_allowed'), patch('core.ai_policy.is_cloud_ai_allowed',return_value=True), patch('config.get_api_key',return_value='fixture'), patch('config.get_runtime_config',return_value={'natural_chat_voice':True,'natural_voice_backend':'gemini_tts','voice_name':'Charon'}), patch('sounddevice.RawOutputStream'):
        assert engine._speak_natural('Haan, bolo.')
        assert engine._speak_natural('Haan, bolo.')
    client.post.assert_awaited_once()
    body=client.post.await_args.kwargs['json']
    assert body['input'][0]['content'][0]['text']=='Haan, bolo.'
    assert body['generation_config']['speech_config']==[{'voice':'Charon'}]
    assert not any(k in body for k in ('tools','memory','system_instruction'))


def test_explicit_memory_inspect_save_forget_uses_existing_store(tmp_path):
    import memory.memory_manager as memory
    from core.memory_commands import handle_memory_command
    with patch.object(memory,'MEMORY_PATH',tmp_path/'memory.json'), patch.object(memory,'_cached_memory_data',None), patch.object(memory,'_cached_memory_mtime',None):
        result=handle_memory_command('yaad rakh: fixture subject: C programming')
        assert result['verified']
        assert 'C programming' in handle_memory_command('memory dikhao')['message']
        assert handle_memory_command('bhool ja: fixture subject')['verified']
        assert 'fixture_subject' not in memory.load_memory().get('notes',{})
        assert handle_memory_command('explain what remember means') is None


def test_live_three_conversation_turns_accept_one_initial_wake():
    from tests.test_runtime_glitches import live_fixture, packet, run_packets
    live = live_fixture()
    assert run_packets(live, [packet(text='Jarvis, explain loops', output='Pehle example dekho.', data=b'one', complete=True),
                               packet(text='aur example do', output='Ye doosra example hai.', data=b'two', complete=True),
                               packet(text='samajh gaya', output='Achha, ab try karo.', data=b'three', complete=True)]) == []
    assert live.audio_in_queue.qsize() == 3
    assert live._voice_conversation_active


def test_recent_voice_and_chat_dialogue_share_bounded_history():
    from main import JarvisLive
    live=JarvisLive.__new__(JarvisLive)
    engine=MagicMock()
    with patch('core.ai_multitier_engine.get_ai_engine',return_value=engine):
        live._record_conversation_turn('aur example do','Ye example dekho.')
    assert [c.args for c in engine.add_turn.call_args_list] == [('user','aur example do'),('assistant','Ye example dekho.')]


def test_memory_deletion_does_not_trigger_new_fact_extraction():
    from main import _update_memory_async
    with patch('main.should_extract_memory') as extract:
        _update_memory_async('Jarvis, bhool ja: study subject','Hata diya.')
    extract.assert_not_called()


def test_natural_voice_failure_does_not_silently_switch_to_windows():
    from tests.test_runtime_glitches import speech_fixture
    engine=speech_fixture()
    engine._on_notice_cb=MagicMock()
    engine._speak_natural=MagicMock(return_value=False)
    engine._speech_queue.put(('Haan, bolo.',False,0))
    engine._speech_queue.put(None)
    with patch('config.get_runtime_config',return_value={'natural_chat_voice':True,'allow_robotic_voice_fallback':False}):
        engine._worker_loop()
    engine._sapi_voice.Speak.assert_not_called()
    engine._on_notice_cb.assert_called_once()
    assert engine._speech_queue.unfinished_tasks==0
