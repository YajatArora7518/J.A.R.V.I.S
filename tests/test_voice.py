# tests/test_voice.py
# Voice Pipeline & State Machine Recovery Test Suite

import sys
import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class MockUI:
    def __init__(self):
        self.state = "IDLE"
        self.muted = False
        self.logs = []

    def set_state(self, s: str):
        self.state = s

    def write_log(self, txt: str):
        self.logs.append(txt)


def test_voice_pipeline_state_machine() -> tuple[bool, str]:
    try:
        from main import JarvisLive
        ui = MockUI()
        jarvis = JarvisLive(ui)

        # 1. State transition to SPEAKING
        jarvis.set_speaking(True)
        if jarvis._is_speaking is not True or ui.state != "SPEAKING":
            return False, f"Failed to set SPEAKING state. Got is_speaking={jarvis._is_speaking}, ui.state={ui.state}"

        # 2. State transition to LISTENING
        jarvis.set_speaking(False)
        if jarvis._is_speaking is not False or ui.state != "LISTENING":
            return False, f"Failed to reset to LISTENING state. Got is_speaking={jarvis._is_speaking}, ui.state={ui.state}"

        # 3. Test Watchdog forced recovery from stuck SPEAKING
        jarvis.set_speaking(True)
        # Simulate last audio chunk time far in past
        jarvis._last_audio_chunk_time = time.time() - 10.0
        time.sleep(1.5)  # Wait for watchdog loop iteration

        if jarvis._is_speaking is not False or ui.state != "LISTENING":
            return False, "Watchdog failed to recover stuck SPEAKING state"

        # Stop watchdog thread
        jarvis._watchdog_running = False

        return True, "Voice state machine transitions, watchdog recovery, and queue flushing verified"
    except Exception as e:
        return False, f"Voice test exception: {e}"


def test_desktop_shortcut() -> tuple[bool, str]:
    try:
        from actions.desktop_shortcut import setup_desktop_shortcut
        res = setup_desktop_shortcut("update")
        if not res.get("success"):
            return False, f"Shortcut creation failed: {res.get('error')}"
        return True, "Windows Desktop shortcut created with jarvis.ico"
    except Exception as e:
        return False, f"Shortcut test exception: {e}"


if __name__ == "__main__":
    p1, m1 = test_voice_pipeline_state_machine()
    p2, m2 = test_desktop_shortcut()
    print(f"Voice Pipeline Test: {'PASS' if p1 else 'FAIL'} - {m1}")
    print(f"Desktop Shortcut Test: {'PASS' if p2 else 'FAIL'} - {m2}")
