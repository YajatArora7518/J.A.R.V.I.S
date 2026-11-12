"""Behavioral acceptance for the actual chat bridge and safe literal rendering."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('owner,foreground,minimized,expected', [
    (22, 10, False, False), (7, 99, False, False),
    (7, 10, True, False), (7, 10, False, True),
])
def test_open_app_requires_foreground_owned_window(owner, foreground, minimized, expected):
    from actions.application_launch_executor import ApplicationLaunchExecutor
    descriptor = SimpleNamespace(process_names=['Discord.exe'], display_name='Discord')
    process = SimpleNamespace(info={'pid': 7, 'name': 'Discord.exe'})
    with patch('actions.application_launch_executor.platform.system', return_value='Windows'), patch('actions.application_launch_executor.psutil.process_iter', return_value=[process]), patch('win32gui.EnumWindows', side_effect=lambda callback, arg: callback(10, arg)), patch('win32gui.IsWindowVisible', return_value=True), patch('win32gui.GetWindowText', return_value='Discord'), patch('win32process.GetWindowThreadProcessId', return_value=(1, owner)), patch('win32gui.ShowWindow'), patch('win32gui.SetForegroundWindow'), patch('win32gui.GetForegroundWindow', return_value=foreground), patch('win32gui.IsIconic', return_value=minimized), patch('win32com.client.Dispatch') as shell, patch('actions.application_launch_executor.time.sleep'):
        shell.return_value.AppActivate.return_value = True
        assert ApplicationLaunchExecutor()._try_focus_existing(descriptor) == expected


def test_running_app_cannot_claim_opened_when_os_rejects_focus():
    from actions.application_launch_executor import ApplicationLaunchExecutor
    executor = ApplicationLaunchExecutor()
    descriptor = SimpleNamespace(display_name='Discord', launch_type='WIN32_EXECUTABLE')
    with patch.object(executor, '_try_focus_existing', return_value=False), patch.object(executor, '_execute_launch_strategy', return_value=True), patch.object(executor, '_verify_application_launched', return_value={'verified': True}), patch('actions.application_launch_executor.time.sleep'):
        result = executor.launch_application('Discord', descriptor)
    assert result.status == 'FAILED' and not result.verification_passed
    assert 'Opened' not in result.message


@pytest.mark.skipif(os.name != "nt", reason="Actual Windows Qt dashboard acceptance")
def test_actual_qt_webchannel_executes_each_chat_input_once():
    run = subprocess.run([sys.executable, "scripts/verify_dashboard_bridge.py"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
    assert run.returncode == 0, (run.stdout + run.stderr)[-2200:]
    report = json.loads((ROOT/"scratch"/"dashboard_bridge_check.json").read_text(encoding="utf-8"))
    assert report["verified"]


def test_dashboard_displays_message_html_as_literal_text_and_bounds_history():
    from playwright.async_api import async_playwright
    from actions.chrome_profile import get_chrome_executable
    html = (ROOT/"assets"/"jarvis_holographic_ui.html").read_text(encoding="utf-8")
    api = html[html.index("window.JARVIS3DCore = {"):html.index("// Initial default populate of tools grid")]
    payload = '<img src="invalid" onerror="window.injected=true"> & Keep EXACT text'

    async def run():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=get_chrome_executable(), headless=True)
            try:
                page = await browser.new_page()
                await page.set_content('<div id="chat-display"></div><div id="event-stream"></div><div id="console-logs"></div>')
                await page.add_script_tag(content=api)
                await page.evaluate("text=>{JARVIS3DCore.appendChat('You',text);JARVIS3DCore.addAction(text);}", payload)
                assert payload in await page.locator('#chat-display').inner_text()
                assert await page.locator('.timeline-desc').inner_text() == payload
                assert await page.locator('img').count() == 0
                assert not await page.evaluate("!!window.injected")
                await page.evaluate("()=>{for(let i=0;i<300;i++){JARVIS3DCore.appendChat('You','message '+i);JARVIS3DCore.addAction('action '+i);JARVIS3DCore.appendLog('log '+i);}}")
                assert await page.locator('#chat-display > *').count() == 200
                assert await page.locator('#event-stream > *').count() == 100
                assert await page.locator('#console-logs > *').count() == 250
                assert 'message 299' in await page.locator('#chat-display > *').last.inner_text()
            finally:
                await browser.close()
    asyncio.run(run())


def test_holographic_memory_stats_use_saved_data_without_legacy_labels(tmp_path):
    from ui import MainWindow
    memory_path = tmp_path/'memory.json'
    memory_path.write_text('{}', encoding='utf-8')
    hud = MagicMock()
    target = SimpleNamespace(hud=hud)
    with patch("memory.memory_manager.load_memory", return_value={"notes": {"a": 1, "b": 2}, "preferences": {"tone": "natural"}}), patch("memory.memory_manager.MEMORY_PATH", memory_path):
        MainWindow._refresh_memory_stats(target)
    args = hud.setMemoryStats.call_args.args
    assert args[:2] == (3, 2)
    assert args[2] != 'No saved memory'


def test_app_tool_does_not_promote_unverified_launch_to_verified():
    from actions.open_app import open_app
    player = MagicMock()
    with patch("actions.open_app.open_app_structured", return_value={"success": True, "verified": False, "app": "Fixture", "mode": "desktop", "message": "Opened Fixture"}):
        result = open_app("Fixture", player=player)
    assert result["success"] and not result["verified"]
    assert "verification pending" in result["message"]
    assert player.set_state.call_args.args == ("RECOVERING",)


def test_structured_desktop_launch_retains_actual_verification():
    from actions.open_app import open_app_structured
    descriptor = SimpleNamespace(normalized_name="fixture", display_name="Fixture")
    verified = SimpleNamespace(status="COMPLETED", verification_passed=True, message="Opened Fixture")
    with patch("actions.universal_app_resolver.default_app_resolver.resolve_application", return_value=descriptor), patch("actions.application_launch_executor.default_launch_executor.launch_application", return_value=verified):
        result = open_app_structured("Fixture")
    assert result["success"] and result["verified"]
