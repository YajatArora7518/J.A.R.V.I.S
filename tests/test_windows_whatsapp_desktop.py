# tests/test_windows_whatsapp_desktop.py
# Comprehensive Test Suite for Installed Windows WhatsApp Desktop Integration
# Validates Hard Target Assertion ("WINDOWS_INSTALLED_WHATSAPP_DESKTOP"), Browser/Web Rejection,
# Contact Ambiguity Protection, Message Send Verification, Call State Machine, Answer/Decline/End Safety, and Event Deduplication.

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from actions.windows_whatsapp_desktop_executor import (
    windows_whatsapp_desktop_executor,
    send_windows_whatsapp_desktop_message,
    resolve_contact_ambiguity,
    call_state_machine,
    EXECUTION_TARGET_NAME,
    STATE_NO_CALL,
    STATE_INCOMING,
    STATE_ACTIVE,
    STATE_ENDED
)


class TestWindowsWhatsAppDesktop(unittest.TestCase):

    def setUp(self):
        call_state_machine.transition_to(STATE_NO_CALL)

    def test_01_hard_target_assertion(self):
        """Verify all WhatsApp Desktop operations return execution_target == 'WINDOWS_INSTALLED_WHATSAPP_DESKTOP'."""
        with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "Focused")), \
             patch("pyautogui.hotkey"), patch("pyautogui.write"), patch("pyautogui.press"):
            res = send_windows_whatsapp_desktop_message("Aman", "Test Message")
            self.assertEqual(res.get("execution_target"), EXECUTION_TARGET_NAME)
            self.assertNotEqual(res.get("execution_target"), "AndroidWhatsAppExecutor")
            self.assertNotEqual(res.get("execution_target"), "BrowserCDP")

    def test_02_browser_and_web_rejection(self):
        """Verify routing layer raises assertion error if execution_target is anything other than WINDOWS_INSTALLED_WHATSAPP_DESKTOP."""
        from actions.universal_messaging import send_universal_message
        with patch("actions.windows_whatsapp_desktop_executor.send_windows_whatsapp_desktop_message", return_value={"execution_target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "success": True}):
            res = send_universal_message("Aman", "Hello", platform="whatsapp")
            self.assertEqual(res.get("execution_target"), EXECUTION_TARGET_NAME)

        with patch("actions.windows_whatsapp_desktop_executor.send_windows_whatsapp_desktop_message", return_value={"execution_target": "BrowserCDP", "success": True}):
            with self.assertRaises(AssertionError):
                send_universal_message("Aman", "Hello", platform="whatsapp")

    def test_03_contact_ambiguity_protection(self):
        """Verify ambiguous contact queries ('Rahul') ask for clarification instead of guessing."""
        amb = resolve_contact_ambiguity("Rahul")
        self.assertEqual(amb.get("status"), "AMBIGUOUS_CONTACT")
        self.assertTrue(amb.get("requires_clarification"))
        self.assertIn("Kaunse Rahul", amb.get("message"))

        with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "Focused")):
            res = windows_whatsapp_desktop_executor.execute_send_message("Rahul", "Hey")
            self.assertFalse(res.get("success"))
            self.assertEqual(res.get("execution_target"), EXECUTION_TARGET_NAME)

    def test_04_message_send_and_deduplication(self):
        """Verify message send and deduplication cache."""
        with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "Focused")), \
             patch("pyautogui.hotkey"), patch("pyautogui.write"), patch("pyautogui.press"):
            res1 = windows_whatsapp_desktop_executor.execute_send_message("Aman", "Unique Msg 999")
            self.assertTrue(res1.get("success"))
            self.assertTrue(res1.get("verified"))

            # Immediate duplicate send
            res2 = windows_whatsapp_desktop_executor.execute_send_message("Aman", "Unique Msg 999")
            self.assertTrue(res2.get("duplicate_prevented"))

    def test_05_call_state_machine_and_outgoing_calls(self):
        """Verify call state machine transitions and outgoing voice/video calls."""
        with patch("actions.windows_whatsapp_desktop_executor.focus_installed_whatsapp_desktop", return_value=(True, "Focused")), \
             patch("pyautogui.hotkey"), patch("pyautogui.write"), patch("pyautogui.press"):
            res_v = windows_whatsapp_desktop_executor.execute_voice_call("Priya")
            self.assertTrue(res_v.get("success"))
            self.assertIn("voice", res_v.get("message").lower())
            self.assertEqual(res_v.get("execution_target"), EXECUTION_TARGET_NAME)

            res_vid = windows_whatsapp_desktop_executor.execute_video_call("Priya")
            self.assertTrue(res_vid.get("success"))
            self.assertIn("video", res_vid.get("message").lower())
            self.assertEqual(res_vid.get("execution_target"), EXECUTION_TARGET_NAME)

    def test_06_answer_decline_end_call_safety(self):
        """Verify answer, decline, and end call report no-op when no call exists."""
        res_ans = windows_whatsapp_desktop_executor.execute_answer_call()
        self.assertFalse(res_ans.get("success"))
        self.assertIn("Koi incoming WhatsApp call nahi hai", res_ans.get("message"))

        res_dec = windows_whatsapp_desktop_executor.execute_decline_call()
        self.assertFalse(res_dec.get("success"))
        self.assertIn("Koi incoming WhatsApp call nahi hai", res_dec.get("message"))

        res_end = windows_whatsapp_desktop_executor.execute_end_call()
        self.assertFalse(res_end.get("success"))
        self.assertIn("Koi active WhatsApp call nahi hai", res_end.get("message"))

    def test_07_incoming_call_answer_flow(self):
        """Verify answering an active incoming call."""
        call_state_machine.transition_to(STATE_INCOMING, contact="Stark")
        res_ans = windows_whatsapp_desktop_executor.execute_answer_call()
        self.assertTrue(res_ans.get("success"))
        self.assertEqual(call_state_machine.state, STATE_ACTIVE)

        res_end = windows_whatsapp_desktop_executor.execute_end_call()
        self.assertTrue(res_end.get("success"))
        self.assertEqual(call_state_machine.state, STATE_ENDED)

    def test_08_incoming_call_deduplication(self):
        """Verify incoming call event detection and notification deduplication."""
        call_state_machine.transition_to(STATE_INCOMING, contact="Aman")
        det1 = windows_whatsapp_desktop_executor.detect_incoming_call()
        self.assertTrue(det1.get("incoming"))
        self.assertIn("Boss, Aman ka WhatsApp call aa raha hai", det1.get("message"))

        # Second detection cycle for same incoming call
        det2 = windows_whatsapp_desktop_executor.detect_incoming_call()
        self.assertFalse(det2.get("incoming"))
        self.assertTrue(det2.get("deduplicated"))

    def test_09_whatsapp_does_not_relaunch_after_manual_close(self):
        """Verify WhatsApp stays closed after manual close and does NOT relaunch automatically."""
        from actions.windows_whatsapp_desktop_executor import (
            find_running_whatsapp,
            focus_running_whatsapp,
            launch_whatsapp,
            focus_installed_whatsapp_desktop,
            set_whatsapp_user_action_requested,
            is_whatsapp_user_action_requested
        )
        set_whatsapp_user_action_requested(False)
        self.assertFalse(is_whatsapp_user_action_requested())

        # Simulate WhatsApp not running
        with patch("actions.windows_whatsapp_desktop_executor.find_running_whatsapp", return_value=None), \
             patch("actions.windows_whatsapp_desktop_executor.launch_whatsapp") as mock_launch:
            focused, msg = focus_running_whatsapp()
            self.assertFalse(focused)
            self.assertIn("not currently running", msg)
            mock_launch.assert_not_called()

            # focus_installed_whatsapp_desktop should also refuse launch when user action requested is False
            focused_inst, msg_inst = focus_installed_whatsapp_desktop()
            self.assertFalse(focused_inst)
            self.assertIn("closed and no explicit user WhatsApp action was requested", msg_inst)
            mock_launch.assert_not_called()

    def test_10_non_whatsapp_commands_do_not_open_whatsapp(self):
        """Verify non-WhatsApp commands ('Chrome kholo', 'Battery kitni hai') leave WhatsApp closed."""
        from core.command_pipeline import process_user_command
        from actions.windows_whatsapp_desktop_executor import is_whatsapp_user_action_requested

        with patch("actions.windows_whatsapp_desktop_executor.launch_whatsapp") as mock_launch:
            process_user_command("Battery kitni hai?", source="voice")
            self.assertFalse(is_whatsapp_user_action_requested())
            mock_launch.assert_not_called()

            process_user_command("Chrome kholo", source="voice")
            self.assertFalse(is_whatsapp_user_action_requested())
            mock_launch.assert_not_called()

            process_user_command("volume badhao", source="voice")
            self.assertFalse(is_whatsapp_user_action_requested())
            mock_launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
