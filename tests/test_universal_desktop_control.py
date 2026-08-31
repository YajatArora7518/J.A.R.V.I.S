# tests/test_universal_desktop_control.py
# Comprehensive Test Suite for JARVIS Universal System Control & Scoped Mic Architecture

import unittest
import time
from typing import Dict, Any

from actions.mic_control import (
    get_jarvis_mic_enabled,
    set_jarvis_mic_enabled,
    handle_mic_command,
    get_mic_states
)
from core.command_pipeline import process_user_command
from actions.system_telemetry import (
    get_cpu_info,
    get_memory_info,
    get_gpu_info,
    get_battery_info,
    get_disk_info,
    get_network_info,
    get_process_info,
    get_installed_apps_info,
    get_active_windows_info,
    get_audio_devices_info,
    inspect_filesystem,
    execute_system_telemetry
)
from actions.app_registry import resolve_app, is_app_installed


class MockHUD:
    def __init__(self):
        self.mic_state = True
        self.muted = False

    def setMicState(self, isOn: bool):
        self.mic_state = isOn


class MockUI:
    def __init__(self):
        self.muted = False
        self.hud = MockHUD()
        self.logs = []

    def set_muted(self, muted: bool):
        self.muted = muted
        self.hud.setMicState(not muted)
        set_jarvis_mic_enabled(not muted)

    def write_log(self, text: str):
        self.logs.append(text)


class TestUniversalDesktopControl(unittest.TestCase):

    def setUp(self):
        self.mock_ui = MockUI()
        set_jarvis_mic_enabled(True, ui_instance=self.mock_ui)

    def test_01_manual_mic_off(self):
        self.mock_ui.set_muted(True)
        self.assertFalse(get_jarvis_mic_enabled())
        self.assertTrue(self.mock_ui.muted)
        self.assertFalse(self.mock_ui.hud.mic_state)

    def test_02_manual_mic_on(self):
        self.mock_ui.set_muted(True)
        self.mock_ui.set_muted(False)
        self.assertTrue(get_jarvis_mic_enabled())
        self.assertFalse(self.mock_ui.muted)
        self.assertTrue(self.mock_ui.hud.mic_state)

    def test_03_voice_mic_off(self):
        res = handle_mic_command("Jarvis mic off", ui_instance=self.mock_ui)
        self.assertTrue(res["success"])
        self.assertFalse(res["state"])
        self.assertFalse(get_jarvis_mic_enabled())
        self.assertTrue(self.mock_ui.muted)

    def test_04_voice_mic_on(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        res = handle_mic_command("Jarvis mic on", ui_instance=self.mock_ui)
        self.assertTrue(res["success"])
        self.assertTrue(res["state"])
        self.assertTrue(get_jarvis_mic_enabled())
        self.assertFalse(self.mock_ui.muted)

    def test_05_typed_mic_off(self):
        res = process_user_command("Jarvis mic off", source="chat")
        self.assertTrue(res["success"])
        self.assertFalse(get_jarvis_mic_enabled())

    def test_06_typed_mic_on(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        res = process_user_command("Jarvis mic on", source="chat")
        self.assertTrue(res["success"])
        self.assertTrue(get_jarvis_mic_enabled())

    def test_07_mic_state_ui_sync(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        self.assertFalse(self.mock_ui.hud.mic_state)
        set_jarvis_mic_enabled(True, ui_instance=self.mock_ui)
        self.assertTrue(self.mock_ui.hud.mic_state)

    def test_08_mic_off_safety(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        states = get_mic_states()
        self.assertFalse(states["jarvis_mic"])
        # Ensure state query does not raise exceptions
        self.assertIsInstance(states, dict)

    def test_09_mic_on_restores_listening(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        set_jarvis_mic_enabled(True, ui_instance=self.mock_ui)
        self.assertTrue(get_jarvis_mic_enabled())

    def test_10_voice_text_command_parity(self):
        voice_res = process_user_command("What CPU do I have?", source="voice")
        text_res = process_user_command("What CPU do I have?", source="chat")
        self.assertEqual(voice_res.get("action"), text_res.get("action"))
        self.assertTrue(voice_res.get("success"))
        self.assertTrue(text_res.get("success"))

    def test_11_typed_application_launch(self):
        res = process_user_command("Open Notepad", source="chat")
        self.assertTrue(res.get("success"))

    def test_12_native_application_detection(self):
        res = resolve_app("notepad")
        self.assertIsNotNone(res)
        self.assertTrue(is_app_installed("notepad"))

    def test_13_cpu_query(self):
        data = get_cpu_info()
        self.assertIn("processor", data)
        self.assertGreater(data["logical_cores"], 0)

    def test_14_ram_query(self):
        data = get_memory_info()
        self.assertGreater(data["total_gb"], 0)
        self.assertGreaterEqual(data["free_gb"], 0)

    def test_15_gpu_query(self):
        data = get_gpu_info()
        self.assertIn("gpus", data)
        self.assertGreater(len(data["gpus"]), 0)

    def test_16_battery_query(self):
        data = get_battery_info()
        self.assertIn("percent", data)

    def test_17_disk_query(self):
        data = get_disk_info()
        self.assertIn("drives", data)
        self.assertGreater(len(data["drives"]), 0)

    def test_18_network_query(self):
        data = get_network_info()
        self.assertIn("connected", data)

    def test_19_process_query(self):
        data = get_process_info()
        self.assertGreater(data["total_running_count"], 0)

    def test_20_installed_apps_query(self):
        data = get_installed_apps_info()
        self.assertGreaterEqual(data["total_installed_detected"], 0)

    def test_21_active_windows_query(self):
        data = get_active_windows_info()
        self.assertIn("windows", data)

    def test_22_audio_devices_query(self):
        data = get_audio_devices_info()
        self.assertIn("active_speakers", data)

    def test_23_hinglish_commands(self):
        res1 = process_user_command("Mera RAM kitna hai?", source="chat")
        self.assertTrue(res1.get("success"))
        res2 = process_user_command("Battery kitni hai?", source="chat")
        self.assertTrue(res2.get("success"))

    def test_24_english_commands(self):
        res1 = process_user_command("How much RAM do I have?", source="chat")
        self.assertTrue(res1.get("success"))
        res2 = process_user_command("What's my battery percentage?", source="chat")
        self.assertTrue(res2.get("success"))

    def test_25_ambiguous_mic_prompt(self):
        res = handle_mic_command("Mic status", ui_instance=self.mock_ui)
        self.assertEqual(res.get("status"), "MIC_SCOPE_AMBIGUOUS")
        self.assertIn("JARVIS mic, app mic, Discord mic, ya system mic?", res.get("message"))

    def test_26_typed_command_while_mic_off(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        self.assertFalse(get_jarvis_mic_enabled())
        res = process_user_command("Open Notepad", source="chat")
        self.assertTrue(res.get("success"))

    def test_27_typed_mic_on_restores_mic(self):
        set_jarvis_mic_enabled(False, ui_instance=self.mock_ui)
        self.assertFalse(get_jarvis_mic_enabled())
        res = process_user_command("Jarvis mic on", source="chat")
        self.assertTrue(res.get("success"))
        self.assertTrue(get_jarvis_mic_enabled())

    def test_28_holo_bridge_slots(self):
        from ui import HoloBridge
        bridge = HoloBridge(self.mock_ui)
        self.assertTrue(hasattr(bridge, "sendCommand"))
        self.assertTrue(hasattr(bridge, "send_text_command"))
        self.assertTrue(hasattr(bridge, "toggleMute"))
        self.assertTrue(hasattr(bridge, "set_muted"))

    def test_29_html_qwebchannel_integration(self):
        from pathlib import Path
        html_path = Path(__file__).resolve().parent.parent / "assets" / "jarvis_holographic_ui.html"
        content = html_path.read_text(encoding="utf-8")
        self.assertIn("qrc:///qtwebchannel/qwebchannel.js", content)
        self.assertIn("submitTextCommand", content)
        self.assertIn("z-index: 20", content)


if __name__ == "__main__":
    unittest.main()
