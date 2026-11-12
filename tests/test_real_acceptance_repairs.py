"""Failures discovered through real UI, isolated from real contacts/actions."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.parametrize('matches', [False, True])
def test_caret_ocr_does_not_replace_exact_focused_draft_verification(matches):
    from actions.whatsapp_desktop_visual import _execute_visual
    initial, typed, sent = MagicMock(), MagicMock(), MagicMock()
    initial.chat_header_matches.return_value = True
    initial.composer_placeholder.return_value = {'fixture':True}
    initial.matching_outgoing.return_value = []
    typed.chat_header_matches.return_value = True
    typed.lines = [{'text':'match dekh leI', 'words':[{'y':700}]}]
    sent.matching_outgoing.return_value = [{'text':'match dekh le'}]
    sent.composer_placeholder.return_value = {'fixture':True}
    sent.chat_header_matches.return_value = True
    with patch('actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop',return_value=(True,'fixture')), patch('actions.windows_whatsapp_desktop_executor.win32_find_whatsapp_hwnd',return_value=42), patch('actions.whatsapp_desktop_visual.WhatsAppObservation',side_effect=[initial,typed,sent]), patch('actions.whatsapp_desktop_visual._paste'), patch('actions.whatsapp_desktop_visual._focused_text_matches',return_value=matches) as verify, patch('win32gui.GetForegroundWindow',return_value=42), patch('pyautogui.press') as press, patch('actions.whatsapp_desktop_visual.time.sleep'):
        result = _execute_visual('send','Divyansh','match dekh le')
    verify.assert_called_once_with('match dekh le',42)
    if matches:
        press.assert_called_once_with('enter')
        assert result['verified'] and result['status'] == 'SUBMITTED_UI_VERIFIED'
    else:
        press.assert_not_called()
        assert not result['verified'] and result['status'] == 'DRAFT_UNVERIFIED'


def test_local_export_validation_failure_is_not_misreported_as_login_failure():
    from actions.google_contacts_browser import sync_contacts_in_browser
    def failure(coro, **kwargs):
        coro.close()
        raise ValueError('Google export count match nahi hua; purane contacts safe hain.')
    with patch('actions.browser_automation.browser_automation_engine.run',side_effect=failure):
        result = sync_contacts_in_browser()
    assert not result['verified'] and result['status'] == 'GOOGLE_EXPORT_INVALID'
    assert 'count match' in result['message']


def test_stalled_readonly_scan_has_a_deadline_and_no_second_worker(monkeypatch):
    import threading
    import time
    import actions.whatsapp_desktop_accessibility as module
    started, release = threading.Event(), threading.Event()
    calls = []
    def stalled():
        calls.append('read only')
        started.set()
        release.wait(4)
        return [{'fixture':True}]
    monkeypatch.setattr(module, '_inventory_thread', None)
    with patch.object(module, '_collect_inventory',side_effect=stalled):
        try:
            assert module._inventory() == []
            assert started.is_set()
            before = time.monotonic()
            assert module._inventory() == []
            assert time.monotonic() - before < .5
            assert calls == ['read only']
        finally:
            release.set()
            module._inventory_thread.join(timeout=2)
