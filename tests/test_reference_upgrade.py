"""Video upgrade acceptance: no real sends, shutdowns, or cloud requests."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def isolated_context():
    from core import command_pipeline as pipeline
    pipeline.reset_conversation_context()
    with patch.object(pipeline, '_tools_initialized', True):
        yield
    pipeline.reset_conversation_context()


@pytest.mark.parametrize('text', [
    'write an email asking IT to restart the laptop',
    'Jarvis professor ko mail likho leave ke liye',
    'draft a WhatsApp message to Fixture saying restart my laptop',
])
@pytest.mark.parametrize('source', ['voice', 'chat'])
def test_writing_produces_complete_draft_without_typing_sending_or_power(text, source):
    from core.command_pipeline import process_user_command
    from core.intent_router import classify_intent
    body = 'Subject: Leave request\n\nDear Professor,\nCould I take leave tomorrow?\n\nThank you.'
    assert classify_intent(text)['intent'] == 'DRAFT_TEXT'
    brain = MagicMock()
    brain.generate_response.return_value = {'success': True, 'text': body}
    with patch('core.ai_multitier_engine.get_ai_engine', return_value=brain), patch('core.command_pipeline.default_tool_registry.execute_tool') as execute, patch('actions.windows_system_controller.execute_system_capability') as power:
        result = process_user_command(text, source=source)
    assert result['message'] == body and result['draft_only']
    assert result['status'] == 'DRAFT_READY'
    execute.assert_not_called()
    power.assert_not_called()
    assert brain.generate_response.call_args.kwargs['response_tokens'] == 1200


@pytest.mark.parametrize('text,action', [
    ('Jarvis laptop band kar do', 'shutdown'), ('restart my laptop', 'restart'),
    ('laptop restart kar de', 'restart'), ('लैपटॉप बंद करो', 'shutdown'),
])
def test_explicit_power_requests_parse(text, action):
    from core.command_pipeline import _parse_power_request
    assert _parse_power_request(text) == {'action': action, 'target_device': 'pc'}


@pytest.mark.parametrize('text', ['Discord band kar', 'restart Discord', 'write a mail about shutdown',
                                       'how do I restart my laptop', 'do not shutdown my laptop', 'band',
                                       'shutdown my laptop and delete files'])
def test_other_commands_and_discussion_do_not_become_power_requests(text):
    from core.command_pipeline import _parse_power_request
    assert _parse_power_request(text) is None


@pytest.mark.parametrize('first,second', [('chat', 'voice'), ('voice', 'chat')])
def test_confirmed_power_dispatches_once_across_input_modes(first, second):
    from core.command_pipeline import process_user_command, _handle_power_request
    response = {'success': True, 'verified': False, 'status': 'POWER_REQUEST_ACCEPTED', 'message': 'OS accepted request'}
    with patch('actions.windows_system_controller.execute_system_capability', return_value=response) as execute:
        prompt = process_user_command('restart my laptop', source=first)
        assert prompt['requires_confirmation']
        execute.assert_not_called()
        result = process_user_command('haan kar do', source=second)
        assert result['success'] and not result['verified']
        assert _handle_power_request('yes', first, 'fixture') is None
    execute.assert_called_once_with('restart', {'confirmed': True})


@pytest.mark.parametrize('reply', ['book a cab', 'okay I need help', 'cancel', 'calculate 13 * 17'])
def test_unrelated_sentence_or_cancel_cannot_confirm_power(reply):
    from core.command_pipeline import _handle_power_request
    with patch('actions.windows_system_controller.execute_system_capability') as execute:
        _handle_power_request('shutdown my laptop', 'chat', 'one')
        result = _handle_power_request(reply, 'voice', 'two')
        assert result is None or result['status'] == 'POWER_CANCELLED'
        assert _handle_power_request('yes', 'chat', 'three') is None
    execute.assert_not_called()


def test_expired_confirmation_requires_new_command():
    from core import command_pipeline as pipeline
    pipeline._handle_power_request('restart my laptop', 'voice', 'one')
    pipeline._CONVERSATION_CONTEXT['pending_power_action']['expires_at'] = 0
    with patch('actions.windows_system_controller.execute_system_capability') as execute:
        assert pipeline._handle_power_request('yes', 'chat', 'two')['status'] == 'CONFIRMATION_EXPIRED'
    execute.assert_not_called()


def test_pending_power_allows_only_confirmation_voice_without_repeating_wake_name():
    from main import JarvisLive
    from core import command_pipeline as pipeline
    live = JarvisLive.__new__(JarvisLive)
    pipeline._handle_power_request('restart my laptop', 'chat', 'one')
    assert live._voice_is_addressed('haan kar do')
    assert live._voice_is_addressed('cancel')
    assert not live._voice_is_addressed('okay I need help')
    assert not live._voice_is_addressed('open WhatsApp')
    pipeline._CONVERSATION_CONTEXT['pending_power_action']['expires_at'] = 0
    assert not live._voice_is_addressed('haan kar do')


def test_stop_speech_also_cancels_a_pending_power_request():
    from main import JarvisLive
    from core import command_pipeline as pipeline
    live = JarvisLive.__new__(JarvisLive)
    live.tts_engine = MagicMock()
    live.audio_in_queue = None
    live.set_speaking = MagicMock()
    pipeline._handle_power_request('restart my laptop', 'chat', 'one')
    assert live._check_barge_in('stop')
    assert pipeline._CONVERSATION_CONTEXT['pending_power_action'] is None
    assert not live._voice_is_addressed('yes')


def test_observed_jervis_spelling_is_an_address_without_modifying_payload():
    from main import JarvisLive
    from core.intent_router import normalize_command_prefix
    live = JarvisLive.__new__(JarvisLive)
    assert live._voice_is_addressed('Jervis')
    assert live._voice_is_addressed('Jervis, WhatsApp kholo')
    assert not live._voice_is_addressed('I spoke to Jervis')
    assert not live._voice_is_addressed('jueves')
    assert normalize_command_prefix('Jervis, WhatsApp Fixture ko message bhejo Jervis, Keep EXACT') == 'WhatsApp Fixture ko message bhejo Jervis, Keep EXACT'


@pytest.mark.parametrize('code', [0, 5])
def test_native_power_adapter_reports_actual_os_result_without_fake_verification(code):
    from actions.computer_settings import _run_power_action
    with patch('actions.computer_settings._OS', 'Windows'), patch('actions.computer_settings.subprocess.run', return_value=SimpleNamespace(returncode=code, stdout='', stderr='denied')) as execute:
        result = _run_power_action('shutdown')
    assert result['success'] is (code == 0) and not result['verified']
    assert execute.call_args.args[0] == ['shutdown', '/s', '/t', '10']
    assert '/f' not in execute.call_args.args[0]


def test_registry_risk_cannot_downgrade_destructive_parameters():
    from core.security import SecurityManager, RiskLevel
    security = SecurityManager()
    assert not security.validate_and_authorize('file_controller', {'action': 'delete', 'path': 'fixture.txt'}, risk_level=RiskLevel.MEDIUM)[0]
    callback = MagicMock(return_value=True)
    security.set_confirmation_callback(callback)
    assert security.validate_and_authorize('file_controller', {'action': 'delete', 'path': 'fixture.txt'}, risk_level=RiskLevel.MEDIUM)[0]
    callback.assert_called_once()


def test_prefixed_followup_uses_only_recent_verified_contact():
    from core.command_pipeline import _remember_social_target, _resolve_social_follow_up
    _remember_social_target({'platform': 'whatsapp', 'recipient': 'Fixture', 'action': 'read'}, True, True)
    result, error = _resolve_social_follow_up('Ab usko bol Main 10 minute mein aaunga')
    assert error is None
    assert result['recipient'] == 'Fixture' and result['message_text'] == 'Main 10 minute mein aaunga'


@pytest.mark.parametrize('muted', [False, True])
def test_explicit_talk_button_starts_continuous_voice_input_and_respects_mute(muted):
    from main import JarvisLive
    from ui import HoloBridge
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live.ui.muted = muted
    window = SimpleNamespace(on_voice_wake=live._request_voice_followup)
    with patch('actions.mic_control.get_jarvis_mic_enabled', return_value=True), patch('main.time.monotonic', return_value=100):
        HoloBridge(window).listenNow()
        assert live._voice_is_addressed('calculate 13 times 17') is (not muted)
        assert not live._voice_is_addressed('')
    with patch('main.time.monotonic', return_value=116):
        assert live._voice_is_addressed('calculate 13 times 17') is (not muted)
        live._apply_conversation_control('ab wait kar')
        assert not live._voice_is_addressed('calculate 13 times 17')


def test_long_draft_budget_survives_cloud_to_local_fallback(tmp_path):
    import os
    from core.ai_multitier_engine import MultiTierAIEngine
    brain = MultiTierAIEngine()
    brain.memory_path = tmp_path / 'no-personal-memory.json'
    brain.prefer_cloud = True
    brain.gemini_api_key = 'test-only'
    brain.openrouter_api_key = ''
    with patch.object(brain, 'add_turn'), patch.dict(os.environ, {'JARVIS_CLOUD_AI':'true'}), patch('google.genai.Client', side_effect=RuntimeError('offline')), patch('core.ollama_provider.is_ollama_available', return_value=True), patch('core.ollama_provider.generate_ollama_response', return_value={'success': True, 'text': 'Complete fixture draft'}) as local:
        result = brain.generate_response('write an email', system_override='Fixture style', response_tokens=1200)
    assert result['success']
    assert local.call_args.kwargs['num_predict'] == 1200


def test_unresolved_plan_and_unverified_tool_never_claim_completed():
    from agent.task_planner import TaskPlanner, PlanStep
    from core.tool_registry import ToolResult
    planner = TaskPlanner()
    step = PlanStep(1, 'REPORT', 'Unresolved request', {'status': 'unresolved'})
    assert not planner._dispatch_action(step)[0]
    step = PlanStep(1, 'TOOL_ACTION', 'fixture', {'tool_name': 'fixture'})
    result = ToolResult(success=True, tool='fixture', message='Accepted', verification={'verified': False})
    with patch('core.tool_registry.default_tool_registry.execute_tool', return_value=result):
        ok, step.execution_result, error = planner._dispatch_action(step)
    assert ok and not planner._verify_action(step)['verified']


@pytest.mark.parametrize('text', ['assign Meta ads review to Fixture', 'Fixture ko Meta ads review assign karo',
                                  'Jarvis assign Meta ads review to Fixture'])
def test_assignment_routes_and_persists_owner_without_external_notification(tmp_path, text):
    from agent.task_manager import UnifiedTaskManager
    from core.command_pipeline import process_user_command
    from core.intent_router import classify_intent
    manager = UnifiedTaskManager(tmp_path / 'tasks.json')
    assert classify_intent(text)['intent'] == 'TASK_MANAGER'
    with patch('agent.task_manager.default_task_manager', manager), patch('core.command_pipeline.default_tool_registry.execute_tool') as execute:
        result = process_user_command(text, source='chat')
    task = manager._load_tasks()[0]
    assert task.title == 'Meta ads review' and task.assignee == 'Fixture'
    assert result['verified'] and 'notification abhi nahi' in result['message']
    assert UnifiedTaskManager(manager.store_path)._load_tasks()[0].assignee == 'Fixture'
    execute.assert_not_called()


def test_unclear_completion_does_not_mark_first_pending_task(tmp_path):
    from agent.task_manager import UnifiedTaskManager
    manager = UnifiedTaskManager(tmp_path / 'tasks.json')
    manager.add_task('Prepare report')
    assert 'exact title' in manager.handle_natural_command('is task ko complete mark karo')
    assert manager._load_tasks()[0].status == 'PENDING'


def test_assignment_does_not_overwrite_a_different_longer_task(tmp_path):
    from agent.task_manager import UnifiedTaskManager
    from core.intent_router import classify_intent
    manager = UnifiedTaskManager(tmp_path / 'tasks.json')
    manager.add_task('Review launch report')
    manager.handle_natural_command('assign Review launch to Fixture')
    tasks = manager._load_tasks()
    assert len(tasks) == 2
    assert tasks[0].assignee is None and tasks[1].assignee == 'Fixture'
    assert classify_intent('assign Write email to Fixture')['intent'] == 'TASK_MANAGER'


def test_board_renders_literal_titles_and_limits_visible_rows():
    from playwright.async_api import async_playwright
    from actions.chrome_profile import get_chrome_executable
    html = (ROOT / 'assets/jarvis_holographic_ui.html').read_text(encoding='utf-8')
    api = html[html.index('window.JARVIS3DCore = {'):html.index('// Initial default populate of tools grid')]
    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                page = await browser.new_page()
                await page.set_content('<div id="task-board"></div>')
                await page.add_script_tag(content=api)
                payload = '<img src=x onerror="window.injected=true">'
                await page.evaluate('(title)=>JARVIS3DCore.setTasks(Array.from({length:30},()=>({title,assignee:"Fixture",priority:"HIGH"})))', payload)
                assert await page.locator('.task-row').count() == 12
                assert payload in await page.locator('#task-board').inner_text()
                assert not await page.locator('img').count()
                assert not await page.evaluate('!!window.injected')
                await page.evaluate('JARVIS3DCore.setTasks([])')
                assert 'No pending tasks' in await page.locator('#task-board').inner_text()
            finally:
                await browser.close()
    asyncio.run(run())
