"""Isolated Qt dashboard acceptance through the real WebChannel and worker.

Creates an unshown test window; never sends input to the user's live desktop.
Only arithmetic and temporary local daily goals reach the real command pipeline;
speech is recorded, not played. The user's task and planner files are untouched.
"""
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import time
from unittest.mock import MagicMock, patch

# Use the laptop's working Qt platform, but never show this test window.
# The offscreen platform's graphics initialization exits natively on this host.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui import JarvisUI, MainWindow
from main import JarvisLive
from core.command_pipeline import process_user_command


def verify():
    print("[BRIDGE CHECK] Creating isolated Qt application", flush=True)
    app = QApplication.instance() or QApplication(sys.argv)
    print("[BRIDGE CHECK] Creating unshown dashboard", flush=True)
    window = MainWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()  # Start WebEngine without placing the test UI on the desktop.
    ui = JarvisUI.__new__(JarvisUI)
    ui._app, ui._win = app, window
    live = JarvisLive.__new__(JarvisLive)
    live.ui = ui
    live._command_lock = threading.RLock()
    live._update_proactive_state = MagicMock()
    live.speak = MagicMock()
    live.tts_engine = MagicMock()
    live.set_speaking = MagicMock()
    ui.on_text_command = live._on_text_command
    ui.on_voice_wake = live._request_voice_followup
    page = window.hud._web.page()
    report = {"mode": "isolated unshown Qt dashboard; actual production WebChannel", "checks": []}
    temporary = tempfile.TemporaryDirectory()
    from agent.daily_planner import DailyPlanner
    from agent.task_manager import UnifiedTaskManager
    planner = DailyPlanner(Path(temporary.name)/'planner.json', UnifiedTaskManager(Path(temporary.name)/'tasks.json'))

    def javascript(code):
        pending = []
        page.runJavaScript(code, lambda result: pending.append(result))
        deadline = time.monotonic() + 5
        while not pending and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.02)
        if not pending:
            raise TimeoutError("Dashboard JavaScript did not return")
        return pending[0]

    def wait_for(predicate, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            time.sleep(.05)
        raise TimeoutError("Dashboard did not reach expected state")

    def fixture_commands_only(text, source="chat", **kwargs):
        from core.intent_router import classify_intent
        assert classify_intent(text)["intent"] == "COMPUTATION" or text == 'aaj ka plan: Bridge fixture study', "Unexpected test action refused"
        return process_user_command(text, source=source, **kwargs)

    try:
        wait_for(lambda: bool(javascript("window._jarvis3dReady && !!window.pyBridge")))
        javascript('window.pyBridge.listenNow(); true')
        wait_for(lambda: live._voice_is_addressed('calculate 13 times 17'))
        report['talk_button'] = {'bridge_callback': True, 'empty_audio_ignored': not live._voice_is_addressed('')}
        live._voice_followup_deadline = 0
        report['talk_button']['continues_without_deadline'] = live._voice_is_addressed('calculate 13 times 17')
        live._apply_conversation_control('ab wait kar')
        report['talk_button']['explicit_pause'] = not live._voice_is_addressed('calculate 13 times 17')
        with patch('agent.daily_planner.get_daily_planner', return_value=planner), patch("core.command_pipeline.process_user_command", side_effect=fixture_commands_only) as execute:
            for input_id, command, answer in (("cmd-input", "calculate 13 * 17", "221"),
                                               ("chat-input", "calculate 29 * 31", "899"),
                                               ("chat-input", "calculate 17 * 19 then calculate 6 * 7", "42"),
                                               ("chat-input", "aaj ka plan: Bridge fixture study", "0/1 complete")):
                before = execute.call_count
                javascript(f"document.getElementById({json.dumps(input_id)}).value={json.dumps(command)};submitTextCommand({json.dumps(input_id)});true")
                wait_for(lambda: bool(javascript(f"document.getElementById('resp-text').textContent.includes({json.dumps(answer)})")))
                state = javascript("JSON.stringify({messages:Array.from(document.querySelectorAll('#chat-display .chat-msg')).map(e=>e.textContent),actions:Array.from(document.querySelectorAll('#event-stream .timeline-desc')).map(e=>e.textContent)})")
                state = json.loads(state)
                result = {"input": input_id, "command": command, "answer": answer,
                          "pipeline_calls": execute.call_count - before,
                          "user_bubbles": sum(message == "You: " + command for message in state["messages"]),
                          "answer_bubbles": sum(answer in message for message in state["messages"]),
                          "action_entries": sum(action == "Executing: " + command for action in state["actions"])}
                expected_calls = 3 if ' then ' in command else 1
                result["verified"] = result['pipeline_calls'] == expected_calls and all(result[key] == 1 for key in ("user_bubbles", "answer_bubbles", "action_entries"))
                report["checks"].append(result)
            report["speech_requests"] = [call.args[0] for call in live.speak.call_args_list]
            voice_text = 'Jarvis, explain the bridge fixture'
            window._on_log_received('You: ' + voice_text)
            wait_for(lambda: javascript("Array.from(document.querySelectorAll('#chat-display .chat-msg')).filter(e=>e.textContent===" + json.dumps('You: ' + voice_text) + ").length") == 1)
            report['voice_user_bubble'] = True
            stored = DailyPlanner(planner.path, planner.tasks).handle_command('aaj ka plan')['message']
            report['planner_restart_persistence'] = 'Bridge fixture study' in stored and '0/1 complete' in stored
            report["verified"] = all(check["verified"] for check in report["checks"]) and len(report["speech_requests"]) == 4 and all(report['talk_button'].values()) and report['planner_restart_persistence'] and report['voice_user_bubble']
    except Exception as exc:
        report.update(verified=False, error=f"{type(exc).__name__}: {exc}")
        report["page_state"] = javascript("JSON.stringify({ready:window._jarvis3dReady,bridge:!!window.pyBridge,location:location.href})")
    finally:
        window.close()
        app.processEvents()
        (ROOT/"scratch"/"dashboard_bridge_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        temporary.cleanup()
    print(json.dumps(report, indent=2))
    return report["verified"]


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
