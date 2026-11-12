"""Local daily companion acceptance; fake clock, fixtures, no live microphone/cloud."""
from datetime import datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.daily_planner import DailyPlanner, parse_timetable
from agent.task_manager import UnifiedTaskManager


@pytest.fixture
def planner(tmp_path):
    return DailyPlanner(tmp_path / 'planner.json', UnifiedTaskManager(tmp_path / 'tasks.json'))


def active(planner, now):
    planner.start_session((now - timedelta(hours=1)).timestamp())


def test_daily_goals_and_exact_completion_survive_restart(planner):
    now = datetime(2026, 10, 7, 10)
    result = planner.handle_command('aaj ka plan: C loops practice, Gym', now=now)
    assert result['verified'] and '0/2 complete' in result['message']
    assert 'exact task nahi' in planner.handle_command('done: loops', now=now)['message']
    assert '1/2 complete' in planner.handle_command('done: C loops practice', now=now)['message']
    other = DailyPlanner(planner.path, planner.tasks)
    assert '1/2 complete' in other.handle_command('aaj ka plan', now=now)['message']
    assert other.tasks._load_tasks()[0].category == 'daily'


def test_plan_reply_collects_real_priorities_but_never_turns_an_action_into_goal(planner):
    now = datetime(2026, 10, 7, 10)
    planner.handle_command('aaj ka plan', now=now)
    assert planner.handle_command('open WhatsApp', intent='WINDOWS_APPLICATION', now=now) is None
    assert planner.handle_command('what is a loop?', intent='INFORMATION', now=now) is None
    assert planner.handle_command('क्या पढ़ना चाहिए', now=now) is None
    assert planner.tasks._load_tasks() == []
    result = planner.handle_command('C practice, revise arrays', now=now)
    assert '0/2 complete' in result['message']


def test_tired_reply_is_not_saved_as_a_task(planner):
    now = datetime(2026, 10, 7, 10)
    planner.handle_command('aaj ka plan', now=now)
    assert 'plan ko abhi side' in planner.handle_command('thak gaya hun', now=now)['message']
    assert planner.tasks._load_tasks() == []
    assert planner.state['paused_until'] > now.timestamp()


def test_assignment_substring_does_not_replace_daily_title(planner):
    now = datetime(2026, 10, 7, 10)
    planner.tasks.add_task('Review launch report')
    result = planner.handle_command('aaj ka plan: Review launch', now=now)
    assert 'Review launch\n' in result['message']
    assert len(planner.tasks._load_tasks()) == 2


def test_no_fake_return_question_without_a_recorded_absence(planner):
    now = datetime(2026, 10, 7, 10)
    active(planner, now)
    event = planner.next_check_in(now, 30)
    assert event['kind'] == 'plan'


def test_recorded_offline_gap_prompts_and_return_reply_is_saved(planner):
    now = datetime(2026, 10, 7, 10)
    planner.state['last_seen'] = (now - timedelta(days=2)).timestamp()
    active(planner, now)
    event = planner.next_check_in(now, 30)
    assert event['kind'] == 'return' and 'busy' in event['message'].lower()
    planner.mark_delivered(event, now)
    result = planner.handle_command('paper ki tayari mein busy tha', now=now)
    assert '2–3 main kaam' in result['message']
    assert planner._day(now)['notes'][0]['text'] == 'paper ki tayari mein busy tha'


def test_absence_uses_real_interaction_gap_even_when_background_runtime_was_active(planner):
    now = datetime(2026, 10, 7, 10)
    planner.state['last_user_at'] = (now - timedelta(days=1)).timestamp()
    planner.state['last_seen'] = (now - timedelta(minutes=2)).timestamp()
    active(planner, now)
    assert planner.next_check_in(now, 30)['kind'] == 'return'


@pytest.mark.parametrize('idle', [None, 0, 10, 301, 3600])
def test_check_ins_wait_for_a_free_present_user(planner, idle):
    now = datetime(2026, 10, 7, 10)
    active(planner, now)
    assert planner.next_check_in(now, idle) is None


def test_one_casual_check_in_and_dedup_survive_restart(planner):
    now = datetime(2026, 10, 7, 15)
    active(planner, now)
    planner.handle_command('aaj ka plan: C practice', now=now)
    event = planner.next_check_in(now, 30)
    assert event['kind'] == 'casual'
    planner.mark_delivered(event, now)
    later = now + timedelta(hours=1)
    assert planner.next_check_in(later, 30) is None
    other = DailyPlanner(planner.path, planner.tasks)
    other.start_session((later - timedelta(minutes=2)).timestamp())
    assert other.next_check_in(later, 30) is None


def test_evening_review_uses_actual_goal_status_and_records_report(planner):
    now = datetime(2026, 10, 7, 21, 15)
    active(planner, now)
    planner.handle_command('aaj ka plan: C practice', now=now)
    event = planner.next_check_in(now, 30)
    assert event['kind'] == 'review'
    planner.mark_delivered(event, now)
    planner.handle_command('2 ghante padha, loops samajh aaye', now=now)
    assert planner._day(now)['notes'][-1]['kind'] == 'review'
    # A reported number of study hours does not automatically complete a task.
    assert planner._goals(now)[0].status == 'PENDING'


def test_busy_and_daily_pause_resume_are_persistent(planner):
    now = datetime(2026, 10, 7, 10)
    active(planner, now)
    planner.handle_command('abhi nahi', now=now)
    assert planner.next_check_in(now + timedelta(minutes=20), 30) is None
    assert planner.next_check_in(now + timedelta(minutes=61), 30)
    planner.handle_command('aaj mat pooch', now=now)
    assert DailyPlanner(planner.path, planner.tasks).state['paused_until'] > now.timestamp()
    assert planner.next_check_in(now + timedelta(hours=2), 30) is None
    planner.handle_command('resume check-ins', now=now)
    assert planner.next_check_in(now, 30)


@pytest.mark.parametrize('hour', [0, 2, 6, 23])
def test_quiet_hours_suppress_daily_prompts(planner, hour):
    now = datetime(2026, 10, 7, hour)
    active(planner, now)
    assert planner.next_check_in(now, 30) is None


def test_timetable_parses_clock_variants_and_sorts_saved_classes():
    rows = parse_timetable('Monday 9am-10am C programming; Tuesday 14:00-15:00 Maths')
    assert rows[0]['start'] == '09:00' and rows[1]['day'] == 'Tuesday'


@pytest.mark.parametrize('text', ['Monday 10:00-09:00 C', 'Monday 09:00-10:00 C; junk',
                                     'Monday 09:00-10:00 C; Monday 09:30-10:30 Maths',
                                     'Monday 25:00-26:00 C', ''])
def test_invalid_timetable_cannot_partially_overwrite_real_data(planner, text):
    with patch('actions.college_mode.save_college_config') as save:
        result = planner.handle_command('save timetable: ' + text, now=datetime(2026, 10, 7, 10))
    assert result is None or not result['verified']
    save.assert_not_called()


def test_explicit_timetable_save_preserves_other_college_data(planner):
    config = {'assignments': [{'title':'Fixture'}], 'timetable': {'Monday':[]}}
    with patch('actions.college_mode.load_college_config', return_value=config), patch('actions.college_mode.save_college_config', return_value=True) as save, patch('actions.college_schedule.schedule_query_engine.store.reload') as reload:
        result = planner.handle_command('remember timetable: Monday 09:00-10:00 C programming', now=datetime(2026, 10, 7, 10))
    assert result['verified']
    saved = save.call_args.args[0]
    assert saved['timetable_confirmed_by_user'] and saved['assignments'] == [{'title':'Fixture'}]
    reload.assert_called_once()


@pytest.mark.parametrize('confirmed', [False, True])
def test_class_question_requires_user_timetable_and_never_asserts_absence(planner, confirmed):
    now = datetime(2026, 10, 7, 11, 5)
    active(planner, now)
    planner.handle_command('aaj ka plan: Practice', now=now)
    planner.mark_delivered({'key':'casual','kind':'casual'}, now - timedelta(hours=1))
    config = {'timetable_confirmed_by_user': confirmed, 'timetable': {'Wednesday': [{'time':'11:00 - 12:00','course':'C programming'}]}}
    with patch('actions.college_mode.load_college_config', return_value=config):
        event = planner.next_check_in(now, 30)
    if confirmed:
        assert event['kind'] == 'class' and event['message'].endswith('?')
        assert 'class miss kar di' not in event['message']
        planner.mark_delivered(event, now)
        planner.handle_command('online hun', now=now)
        saved = DailyPlanner(planner.path, planner.tasks)._day(now)['notes'][-1]
        assert saved['question'] == event['message'] and saved['text'] == 'online hun'
    else:
        assert event is None


def test_corrupt_planner_file_is_preserved_without_breaking_assistant(tmp_path):
    path = tmp_path / 'planner.json'
    path.write_text('{broken', encoding='utf-8')
    planner = DailyPlanner(path, UnifiedTaskManager(tmp_path / 'tasks.json'))
    planner.start_session()
    assert not planner.handle_command('aaj ka plan')['success']
    assert path.read_text(encoding='utf-8') == '{broken'


def test_voice_and_chat_planner_share_the_same_local_goals(planner):
    from core.command_pipeline import process_user_command, reset_conversation_context
    reset_conversation_context()
    with patch('agent.daily_planner.get_daily_planner', return_value=planner), patch('core.command_pipeline._tools_initialized', True), patch('core.command_pipeline.default_tool_registry.execute_tool') as execute:
        first = process_user_command('aaj ka plan: Study C', source='voice')
        second = process_user_command('done: Study C', source='chat')
    assert first['verified'] and '1/1 complete' in second['message']
    execute.assert_not_called()


def test_mood_keywords_use_word_boundaries_not_substrings():
    from agent.emotional_context import EmotionalContext
    context = EmotionalContext()
    assert context.detect_state('explain basic C functions') == 'neutral'
    assert not context._dismissed
    assert context.detect_state('I missed a class') != 'sad'
    assert context.detect_state('bahut tension hai') == 'stressed'
    assert 'avoid roasting' in context.get_response_modifier()


def test_teacher_and_friend_rules_are_present_in_real_live_config(planner):
    from main import JarvisLive
    from core.conversation_style import CONVERSATION_STYLE
    with patch('agent.daily_planner.get_daily_planner', return_value=planner):
        config = JarvisLive.__new__(JarvisLive)._build_config()
    assert CONVERSATION_STYLE in config.system_instruction
    assert 'one useful diagnostic question' in config.system_instruction
    assert 'saved banter preference' in config.system_instruction
    assert 'respect the user' in config.system_instruction


def test_proactive_delivery_logs_chat_and_arms_reply_only_after_speech():
    import threading
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.ui.muted = False
    live.tts_engine = MagicMock()
    live.tts_engine.is_speaking.return_value = False
    live._is_speaking = False
    live._speaking_lock = threading.Lock()
    live.speak = MagicMock()
    live._flush_out_queue = MagicMock()
    live._update_proactive_state = MagicMock()
    assert live._deliver_check_in('Aaj kya karoge?')
    live.ui.write_log.assert_called_once_with('JARVIS: Aaj kya karoge?')
    assert not live._voice_is_addressed('Study C')
    live.set_speaking(True)
    live.set_speaking(False)
    assert live._voice_is_addressed('Study C')


def test_declined_delivery_does_not_consume_daily_check_in(planner):
    from agent.ambient_orchestrator import AmbientOrchestrator
    from agent.proactive_engine import ProactiveDecisionEngine
    engine = ProactiveDecisionEngine()
    event = {'key':'casual','kind':'casual','message':'Fixture check-in'}
    runner = AmbientOrchestrator(speak_callback=lambda text: False)
    with patch('agent.daily_planner.get_daily_planner', return_value=planner), patch('agent.daily_planner.desktop_idle_seconds', return_value=30), patch.object(planner, 'next_check_in', return_value=event), patch('agent.ambient_orchestrator.context_engine.get_current_context', return_value={}), patch('agent.ambient_orchestrator.proactive_decision_engine', engine), patch('agent.proactive_engine.permission_manager.is_granted', return_value=True), patch('agent.proactive_engine.privacy_mode_manager.is_privacy_mode_active', return_value=False), patch.object(engine, 'is_in_quiet_hours', return_value=False):
        assert runner.tick() is None
    assert engine.history_dedup == {}
    assert planner.state['days'] == {}


@pytest.mark.parametrize('response_kind', ['none', 'audio', 'text'])
def test_live_reply_is_recorded_once_without_consuming_pipeline_fallback(response_kind):
    import asyncio
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.audio_in_queue = asyncio.Queue()
    live._mic_stats = {'transcript_events': 0, 'speech_segments': 0}
    live._turn_had_tool_call = live._turn_received_audio = False
    live._turn_command_results = {}
    live.set_speaking = MagicMock()
    live._check_barge_in = MagicMock()
    live._observe_companion_turn = MagicMock()
    sc = SimpleNamespace(interrupted=False, turn_complete=True,
                         input_transcription=SimpleNamespace(text='Jarvis, aaj ka plan: Study C'),
                         output_transcription=SimpleNamespace(text='Plan save ho gaya') if response_kind == 'text' else None)
    class Session:
        async def receive(self):
            yield SimpleNamespace(server_content=sc, tool_call=None, data=b'fixture' if response_kind == 'audio' else None)
            raise asyncio.CancelledError()
    live.session = Session()
    with patch('main.threading.Thread') as thread:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(live._receive_audio())
    dispatches = [call for call in thread.call_args_list if call.kwargs.get('target') == live._dispatch_voice_to_pipeline]
    if response_kind == 'none':
        assert len(dispatches) == 1
        live._observe_companion_turn.assert_not_called()
    else:
        assert dispatches == []
        live._observe_companion_turn.assert_called_once_with('Jarvis, aaj ka plan: Study C', handled_by_tool=False)
