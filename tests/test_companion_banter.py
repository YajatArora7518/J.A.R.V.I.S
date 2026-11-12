"""Saved tone, live/chat parity and camera observations; no real camera or sends."""
import json
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from core import conversation_style as style


@pytest.fixture
def preferences(tmp_path, monkeypatch):
    path = tmp_path / 'conversation.json'
    monkeypatch.setattr(style, '_PREFERENCES_PATH', path)
    return path


@pytest.mark.parametrize('command', ['unfiltered mode on', 'Jarvis, unfiltered mode chalu karo', 'unfiltered', 'unfiltered mode bna d'])
def test_explicit_banter_enable_is_saved_and_shared(command, preferences):
    from core.command_pipeline import process_user_command
    with patch('core.command_pipeline._tools_initialized', True), patch('core.command_pipeline.default_tool_registry.execute_tool') as execute:
        result = process_user_command(command, source='voice')
    assert result['verified'] and result['authoritative_response']
    assert style.get_banter_mode() == 'unfiltered'
    assert json.loads(preferences.read_text())['banter'] == 'unfiltered'
    assert 'consented friendly rough banter' in style.get_conversation_style()
    execute.assert_not_called()


@pytest.mark.parametrize('command', ['gaali band karo', 'gali band', 'gaali mat de', 'गाली मत दो', 'unfiltered mode off', 'normal tone', 'bhai mujhe gaali mat de', 'gaali dena band karo', 'भाई मुझे गाली मत दो'])
def test_stop_banter_persists_across_chat_and_voice(command, preferences):
    from core.command_pipeline import process_user_command
    preferences.write_text('{"banter":"unfiltered","other":"keep"}')
    with patch('core.command_pipeline._tools_initialized', True):
        result = process_user_command(command, source='chat')
    assert result['verified'] and style.get_banter_mode() == 'respectful'
    assert json.loads(preferences.read_text())['other'] == 'keep'
    assert 'no gaali or insults' in style.get_conversation_style()


@pytest.mark.parametrize('command', ['write an email about unfiltered mode on', 'WhatsApp par Test ko "gaali band karo" bhejo', 'explain unfiltered mode', 'unfiltered mode on and shutdown laptop'])
def test_payloads_and_ambiguous_requests_cannot_toggle_tone(command, preferences):
    assert style.handle_banter_command(command) is None
    assert not preferences.exists()


def test_corrupt_preferences_are_preserved_and_not_claimed_saved(preferences):
    preferences.write_text('{broken')
    result = style.handle_banter_command('unfiltered mode on')
    assert not result['success'] and not result['verified']
    assert style.get_banter_mode() == 'respectful'
    assert preferences.read_text() == '{broken'


def test_live_cannot_use_stale_rough_tone_after_stop(preferences):
    from main import JarvisLive
    preferences.write_text('{"banter":"unfiltered"}')
    live = JarvisLive.__new__(JarvisLive)
    config = live._build_config()
    assert 'consented friendly rough banter' in config.system_instruction
    style.handle_banter_command('gaali band karo')
    assert live._voice_requires_pipeline('aur example do')
    assert not live._voice_requires_pipeline('Jarvis')
    assert live._voice_requires_pipeline('unfiltered mode on')
    config = live._build_config()
    assert 'no gaali or insults' in config.system_instruction
    assert not live._voice_requires_pipeline('aur example do')


def test_draft_uses_recipient_tone_not_companion_roast(preferences):
    from core.command_pipeline import process_user_command
    preferences.write_text('{"banter":"unfiltered"}')
    brain = MagicMock()
    brain.generate_response.return_value = {'success': True, 'text': 'Dear Professor, could we meet tomorrow?'}
    with patch('core.ai_multitier_engine.get_ai_engine', return_value=brain), patch('core.command_pipeline._tools_initialized', True):
        result = process_user_command('write an email to my professor asking for a meeting')
    assert result['draft_only'] and result['verified']
    assert 'intended recipient' in brain.generate_response.call_args.kwargs['system_override']


def test_old_live_session_cannot_rephrase_current_polite_tool_reply(preferences):
    from main import JarvisLive
    live = JarvisLive.__new__(JarvisLive)
    live.ui = MagicMock()
    live._command_lock = threading.RLock()
    live._turn_command_results = {}
    live._update_proactive_state = MagicMock()
    live._live_banter_mode = 'unfiltered'
    style.handle_banter_command('gaali band karo')
    call = SimpleNamespace(name='assistant_command', id='fixture', args={'query': 'aur example do'})
    with patch('core.command_pipeline.process_user_command', return_value={'success': True, 'verified': True, 'message': 'Yeh ek aur example hai.'}):
        result = asyncio.run(live._execute_tool(call)).response
    assert result['message'] == 'Yeh ek aur example hai.'
    assert result['authoritative_response']
    assert live._live_banter_mode == 'unfiltered'  # Actual session instructions are still stale.


@pytest.mark.parametrize('query', ['camera dekh mera mood kaisa hai', 'कैमरा देखकर बताओ मैं उदास हूं?', 'cam dekh am I stressed?'])
def test_camera_mood_request_asks_without_capture(query):
    from actions.screen_processor import analyze_screen_vision
    from core.intent_router import classify_intent
    intent = classify_intent(query)
    assert intent['angle'] == 'camera'
    with patch('actions.screen_processor._capture_camera') as capture, patch('actions.screen_processor._get_cached_genai_client') as cloud:
        result = analyze_screen_vision(query, angle=intent['angle'])
    assert result['authoritative_response'] and not result['screenshot_available']
    assert not result['mood_inference'] and 'Sab theek hai?' in result['message']
    capture.assert_not_called()
    cloud.assert_not_called()


@pytest.mark.parametrize('observation,verified', [('Table par ek blue bottle hai.', True), ('You look sad and tired.', False), ('Tum gussa lag rahe ho.', False), ('चेहरे से लगता है तुम उदास हो।', False)])
def test_camera_provider_output_cannot_establish_mood(observation, verified):
    from actions.screen_processor import analyze_screen_vision
    client = MagicMock()
    client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({'view': 'other', 'readable': True, 'claims': [{'text': observation, 'quote': ''}]}))
    with patch('actions.screen_processor._capture_camera', return_value=b'synthetic-frame'), patch('actions.screen_processor._get_cached_genai_client', return_value=client), patch('core.ai_policy.is_cloud_ai_allowed', return_value=True), patch('core.ai_policy.assert_cloud_ai_allowed'):
        result = analyze_screen_vision('camera dekh kya dikh raha hai?', angle='camera')
    assert result['verified'] is verified
    assert result['authoritative_response']
    if not verified:
        assert observation not in result['message']
    prompt = client.models.generate_content.call_args.kwargs['contents'][1]
    assert "Never infer a person's mood" in prompt


def test_self_reported_mood_off_softens_banter():
    from agent.emotional_context import EmotionalContext
    emotional = EmotionalContext()
    assert emotional.detect_state('bhai mood off hai') == 'sad'
    assert 'no roasting' in emotional.get_response_modifier()
