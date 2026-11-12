"""Continuation/context/playback probes; all power and communication are isolated."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def clean_context():
    from core.command_pipeline import reset_conversation_context
    reset_conversation_context()
    yield
    reset_conversation_context()


@pytest.mark.parametrize('first,second', [('chat','voice'), ('voice','chat')])
def test_verified_confirmation_continues_only_remaining_steps(first,second):
    from core.command_pipeline import process_user_command, get_conversation_context
    with patch('actions.windows_system_controller.execute_system_capability',return_value={'success':True,'verified':True,'message':'fixture power verified'}) as power:
        paused=process_user_command('calculate 2 * 3 then restart my laptop then calculate 3 * 4',source=first)
        assert paused['requires_confirmation']
        assert [s['step'] for s in paused['steps']]==[1,2]
        assert get_conversation_context()['pending_sequence']['confirmation_id']==paused['confirmation_id']
        power.assert_not_called()
        result=process_user_command('haan',source=second)
    power.assert_called_once_with('restart',{'confirmed':True})
    assert result['verified'] and result['status']=='COMPLETED'
    assert [s['step'] for s in result['steps']]==[1,2,3]
    assert '6' in result['steps'][0]['result']['message']
    assert '12' in result['steps'][2]['result']['message']
    assert get_conversation_context()['pending_sequence'] is None


@pytest.mark.parametrize('resolution', ['cancel','expired','new_command','unverified','failed','mismatched_id'])
def test_pending_sequence_never_continues_on_uncertain_or_wrong_confirmation(resolution):
    from core.command_pipeline import process_user_command, _CONVERSATION_CONTEXT
    with patch('actions.windows_system_controller.execute_system_capability',return_value={'success':resolution!='failed','verified':resolution not in {'failed','unverified'},'message':'fixture result'}) as power:
        process_user_command('calculate 2 * 3 then restart my laptop then calculate 3 * 4',source='chat')
        if resolution=='expired':
            _CONVERSATION_CONTEXT['pending_power_action']['expires_at']=0
            _CONVERSATION_CONTEXT['pending_sequence']['expires_at']=0
        elif resolution=='new_command':
            process_user_command('calculate 9 * 9',source='chat')
        elif resolution=='mismatched_id':
            _CONVERSATION_CONTEXT['pending_sequence']['confirmation_id']='different request'
        result=process_user_command('cancel' if resolution=='cancel' else 'haan',source='voice')
    assert result.get('status')!='COMPLETED'
    assert not any(s.get('step')==3 for s in result.get('steps',[]))
    assert _CONVERSATION_CONTEXT['pending_sequence'] is None
    if resolution in {'cancel','expired','new_command'}: power.assert_not_called()
    else: assert power.call_count==1


def test_chat_context_makes_next_voice_answer_use_shared_pipeline_without_replaying_chat():
    from tests.test_runtime_glitches import live_fixture, packet, run_packets
    live=live_fixture()
    with patch('core.ai_multitier_engine.get_ai_engine',return_value=MagicMock()):
        live._record_conversation_turn('Explain C arrays','An array stores elements.',source='chat')
    assert live._typed_context_revision==1
    assert not live._voice_requires_pipeline('Jarvis')
    dispatches=run_packets(live,[packet(text='Jarvis, aur example do',output='stale answer',data=b'stale',complete=True)])
    assert len(dispatches)==1 and live.audio_in_queue.empty()
    assert dispatches[0].kwargs['args'][0]=='Jarvis, example do'


def test_live_tool_answer_consumes_context_revision_only_when_verified():
    from main import JarvisLive
    live=JarvisLive.__new__(JarvisLive)
    live.ui=MagicMock(muted=False)
    live._command_lock=threading.RLock()
    live._turn_command_results={}
    live._typed_context_revision=2
    live._live_context_revision=0
    live._update_proactive_state=MagicMock()
    call=SimpleNamespace(name='assistant_command',id='fixture',args={'query':'aur example do'})
    with patch('core.command_pipeline.process_user_command',return_value={'success':True,'verified':True,'message':'Shared C array example.'}) as pipeline:
        result=asyncio.run(live._execute_tool(call))
    pipeline.assert_called_once_with('aur example do',source='voice')
    assert result.response['message']=='Shared C array example.'
    assert live._live_context_revision==2
    assert not live._voice_requires_pipeline('aur example do')


@pytest.mark.parametrize('playing,tail,expected', [(False,False,True),(True,False,False),(False,True,False)])
def test_mic_listens_during_generation_but_preserves_playback_echo_guard(playing,tail,expected):
    from main import JarvisLive
    live=JarvisLive.__new__(JarvisLive)
    live.ui=SimpleNamespace(muted=False)
    live.tts_engine=SimpleNamespace(is_speaking=lambda:True,is_playing=lambda:playing)
    live._last_speech_end=99.9 if tail else 0
    live._echo_guard_seconds=.5
    live._local_voice_active=False
    live._voice_barge_in=False
    live._is_speaking=True
    with patch('actions.mic_control.get_jarvis_mic_enabled',return_value=True),patch('main.time.monotonic',return_value=100):
        assert live._mic_accepts_audio() is expected


def test_new_addressed_input_cancels_synthesis_that_has_not_played():
    from tests.test_runtime_glitches import live_fixture,packet,run_packets
    live=live_fixture()
    tts=MagicMock()
    tts.is_speaking.return_value=True
    tts.is_playing.return_value=False
    tts.stop.side_effect=lambda:setattr(tts.is_speaking,'return_value',False)
    live.tts_engine=tts
    run_packets(live,[packet(text='Jarvis, explain loops',output='Fresh reply.',data=b'fresh',complete=True)])
    tts.stop.assert_called_once()
    assert any(c.kwargs.get('force') is True for c in live.set_speaking.call_args_list)


def test_cancel_pending_action_takes_priority_over_stopping_speech():
    from core.command_pipeline import process_user_command
    from main import JarvisLive
    process_user_command('restart my laptop',source='chat')
    live=JarvisLive.__new__(JarvisLive)
    live.tts_engine=MagicMock()
    assert live._apply_conversation_control('cancel') is None
    live.tts_engine.stop.assert_not_called()


def test_tts_playback_flag_only_covers_real_audio_writes_and_clears_afterward():
    import base64
    from unittest.mock import AsyncMock
    from tests.test_runtime_glitches import speech_fixture
    engine=speech_fixture()
    reply=MagicMock()
    reply.json.return_value={'steps':[{'type':'model_output','content':[{'type':'audio','mime_type':'audio/l16',
        'data':base64.b64encode(b'\x01\x00'*240).decode()}]}]}
    client=MagicMock()
    async def post(*args,**kwargs):
        assert not engine.is_playing()
        return reply
    client.post=AsyncMock(side_effect=post)
    context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock()
    with patch('httpx.AsyncClient',return_value=context),patch('core.ai_policy.assert_cloud_ai_allowed'),patch('sounddevice.RawOutputStream') as device:
        def write(chunk): assert engine.is_playing()
        device.return_value.__enter__.return_value.write.side_effect=write
        assert engine._speak_generated('Fixture reply.','fixture',('fixture-model','Charon','Fixture reply.'))
    device.return_value.__enter__.return_value.write.assert_called_once()
    assert not engine.is_playing()
