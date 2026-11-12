"""No real frames/accounts: verified camera lifecycle and honest access status."""
import json
import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def permissions(tmp_path, monkeypatch):
    import agent.awareness.permissions as module
    path = tmp_path / 'awareness.json'
    path.write_text('{"camera":false,"sleep_time":"22:30","custom":"keep"}')
    monkeypatch.setattr(module, 'CONFIG_FILE', path)
    manager = module.PermissionManager()
    monkeypatch.setattr('actions.camera_control.permission_manager', manager)
    monkeypatch.setattr(module, 'permission_manager', manager)
    with patch.object(module.privacy_mode_manager, 'is_privacy_mode_active', return_value=False):
        yield manager, path


def test_camera_enable_checks_hardware_and_preserves_settings(permissions):
    from actions.camera_control import camera_control
    manager, path = permissions
    ui = MagicMock()
    with patch('actions.screen_processor._capture_camera', return_value=b'frame') as capture, patch('agent.awareness.camera_provider.camera_provider.enable') as continuous, patch('actions.screen_processor._get_cached_genai_client') as cloud:
        result = camera_control({'action':'on'}, player=ui)
    assert result['verified'] and result['camera_ready']
    assert not result['continuous_capture'] and not result['cloud_upload']
    assert manager.is_granted('CAMERA_ACCESS')
    assert json.loads(path.read_text())['sleep_time'] == '22:30'
    assert json.loads(path.read_text())['custom'] == 'keep'
    capture.assert_called_once()
    continuous.assert_not_called()
    cloud.assert_not_called()
    ui.set_camera_active.assert_called_once_with(True)


def test_camera_failure_never_claims_active(permissions):
    from actions.camera_control import camera_control
    ui = MagicMock()
    with patch('actions.screen_processor._capture_camera', side_effect=RuntimeError('device unavailable')):
        result = camera_control({'action':'on'}, player=ui)
    assert not result['success'] and not result['verified']
    assert not permissions[0].is_granted('CAMERA_ACCESS')
    ui.set_camera_active.assert_called_once_with(False)


def test_camera_off_disables_provider_and_persists(permissions):
    from actions.camera_control import camera_control
    manager, path = permissions
    manager.set_permission('CAMERA_ACCESS', True)
    with patch('agent.awareness.camera_provider.camera_provider.disable') as disable, patch('actions.screen_processor._capture_camera') as capture:
        result = camera_control({'action':'off'})
    assert result['verified'] and not manager.is_granted('CAMERA_ACCESS')
    assert json.loads(path.read_text())['camera'] is False
    disable.assert_called_once()
    capture.assert_not_called()


def test_analysis_returns_actual_result_not_pretend_acknowledgement(permissions):
    from actions.camera_control import camera_control
    observation = {'success':False, 'verified':False, 'message':'No visible evidence', 'authoritative_response':True}
    with patch('actions.screen_processor.screen_process', return_value=observation) as observe:
        result = camera_control({'action':'analyze','query':'camera dekh'})
    assert result is observation
    assert observe.call_args.args[0] == {'angle':'camera','text':'camera dekh'}


def test_corrupt_permission_file_is_preserved_with_rollback(permissions):
    manager, path = permissions
    path.write_text('{broken')
    assert not manager.set_permission('CAMERA_ACCESS', True)
    assert not manager.is_granted('CAMERA_ACCESS')
    assert path.read_text() == '{broken'


@pytest.mark.parametrize('query,action', [('Jarvis camera on','on'), ('cam band karo','off'), ('कैमरा चालू करो','on'), ('camera status','status')])
def test_camera_controls_route_through_shared_pipeline(query,action):
    from core.intent_router import classify_intent
    intent = classify_intent(query)
    assert intent['tool'] == 'camera_control' and intent['action'] == action


def test_camera_button_dispatches_without_pretending_hardware_success():
    from ui import MainWindow
    ui = SimpleNamespace(_dispatch_command=MagicMock(), _cam_active=False)
    MainWindow._act_camera(ui)
    ui._dispatch_command.assert_called_once_with('camera on')
    assert ui._cam_active is False


def test_camera_pipeline_updates_registered_ui_when_no_player_is_passed(permissions):
    from actions.camera_control import camera_control
    ui = MagicMock()
    with patch('actions.screen_processor._SCREEN_UI', ui), patch('actions.screen_processor._capture_camera', return_value=b'frame'):
        result = camera_control({'action':'on'})
    assert result['verified']
    ui.set_camera_active.assert_called_once_with(True)


def test_existing_hand_tracking_is_explicit_and_can_stop(permissions):
    from ui import MainWindow
    manager, _ = permissions
    ui = SimpleNamespace(_hand_worker=None, _start_hand_tracker=MagicMock(), _on_log_received=MagicMock())
    MainWindow._act_hand_tracking(ui)
    ui._start_hand_tracker.assert_not_called()
    manager.set_permission('CAMERA_ACCESS', True)
    MainWindow._act_hand_tracking(ui)
    ui._start_hand_tracker.assert_called_once()
    ui._hand_worker = MagicMock()
    ui._hand_worker.isRunning.return_value = True
    MainWindow._act_hand_tracking(ui)
    ui._hand_worker.stop.assert_called_once()


def test_privacy_pause_blocks_direct_camera_observation_without_capture(permissions):
    from actions.screen_processor import analyze_screen_vision
    with patch('agent.awareness.permissions.privacy_mode_manager.is_privacy_mode_active', return_value=True), patch('actions.screen_processor._capture_camera') as capture:
        result = analyze_screen_vision('camera dekh kya dikh raha hai', angle='camera')
    assert result['error'] == 'PRIVACY_PAUSED' and not result['screenshot_available']
    capture.assert_not_called()


@pytest.mark.parametrize('failure', ['open','read'])
def test_camera_hardware_is_released_even_on_failure(failure):
    from actions.screen_processor import _capture_camera
    cap = MagicMock()
    cap.isOpened.return_value = failure != 'open'
    cap.read.side_effect = RuntimeError('read failed')
    with patch('actions.screen_processor._get_camera_index', return_value=0), patch('actions.screen_processor.cv2.VideoCapture', return_value=cap):
        with pytest.raises(RuntimeError):
            _capture_camera()
    cap.release.assert_called_once()


def test_access_status_lists_registered_tools_without_granting_or_probing(permissions):
    from actions.assistant_access import assistant_access
    manager, _ = permissions
    with patch('core.tool_registry.default_tool_registry.list_tools', return_value=['web_search','open_app']), patch.object(manager,'set_permission') as grant:
        result = assistant_access()
    assert result['verified'] and result['data']['registered_tools'] == ['web_search','open_app']
    assert result['data']['account_authentication'] == 'not_probed'
    assert result['data']['disruptive_confirmation_required']
    grant.assert_not_called()


def test_camera_detection_works_on_legacy_console_and_keeps_credentials_untouched(tmp_path):
    from actions.screen_processor import _get_camera_index
    credentials = tmp_path / 'api_keys.json'
    original = '{"private_setting":"fixture"}'
    credentials.write_text(original)
    runtime = tmp_path / 'runtime.json'
    runtime.write_text('{"voice_name":"Charon"}')
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.read.return_value = (True, SimpleNamespace(size=10))
    output = io.TextIOWrapper(io.BytesIO(), encoding='ascii')
    with patch('actions.screen_processor.API_CONFIG_PATH', credentials), patch('config.get_runtime_config', return_value={}), patch('actions.screen_processor.cv2.VideoCapture', return_value=cap), patch('sys.stdout', output):
        assert _get_camera_index() == 0
    assert credentials.read_text() == original
    assert json.loads(runtime.read_text()) == {'voice_name':'Charon','camera_index':0}
    cap.release.assert_called_once()


def test_missing_camera_never_saves_guessed_index(tmp_path):
    from actions.screen_processor import _get_camera_index
    cap = MagicMock()
    cap.isOpened.return_value = False
    with patch('actions.screen_processor.API_CONFIG_PATH', tmp_path/'api_keys.json'), patch('config.get_runtime_config', return_value={}), patch('actions.screen_processor.cv2.VideoCapture', return_value=cap):
        with pytest.raises(RuntimeError, match='No camera'):
            _get_camera_index()
    assert cap.release.call_count == 6
    assert not (tmp_path/'runtime.json').exists()
