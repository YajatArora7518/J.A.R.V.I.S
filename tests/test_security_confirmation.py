# tests/test_security_confirmation.py
# Unit Test Suite for PyQt6 Security Confirmation & Risk Handling (Phase 6B)

import unittest
from unittest.mock import MagicMock
from core.security import SecurityManager, RiskLevel, ActionConfirmationNeeded


class TestSecurityConfirmation(unittest.TestCase):
    """Verify RiskLevel classification, security callback execution, and fail-closed defaults."""

    def setUp(self):
        self.security = SecurityManager()

    def test_low_risk_no_confirmation_needed(self):
        """LOW risk actions (search, info) require no user confirmation."""
        risk = self.security.classify_risk("web_search", {"query": "python"})
        self.assertEqual(risk, RiskLevel.LOW)

        authorized, reason = self.security.validate_and_authorize("web_search", {"query": "python"})
        self.assertTrue(authorized)
        self.assertIsNone(reason)

    def test_high_risk_triggers_confirmation(self):
        """HIGH risk actions (file delete, app kill) trigger user confirmation callback."""
        risk = self.security.classify_risk("file_controller", {"action": "delete", "path": "test.txt"})
        self.assertEqual(risk, RiskLevel.HIGH)

        # Mock callback returning True (ALLOW)
        mock_cb = MagicMock(return_value=True)
        self.security.set_confirmation_callback(mock_cb)

        auth, reason = self.security.validate_and_authorize("file_controller", {"action": "delete", "path": "test.txt"})
        self.assertTrue(auth)
        self.assertIsNone(reason)
        mock_cb.assert_called_once()

    def test_high_risk_user_cancel_rejects_action(self):
        """If user cancels (returns False), action must be denied."""
        mock_cb = MagicMock(return_value=False)
        self.security.set_confirmation_callback(mock_cb)

        auth, reason = self.security.validate_and_authorize("computer_settings", {"action": "shutdown"})
        self.assertFalse(auth)
        self.assertIn("cancelled by user security prompt", reason)

    def test_high_risk_protected_path_strictly_blocked(self):
        """Protected system paths (system32) are strictly blocked regardless of user response."""
        mock_cb = MagicMock(return_value=True)
        self.security.set_confirmation_callback(mock_cb)

        auth, reason = self.security.validate_and_authorize("file_controller", {"action": "delete", "path": "C:\\Windows\\System32\\cmd.exe"})
        self.assertFalse(auth)
        self.assertIn("strictly forbidden", reason)
        mock_cb.assert_not_called()

    def test_check_permission_fail_closed_if_no_callback(self):
        """If check_permission is invoked without callback for HIGH risk, it raises ActionConfirmationNeeded."""
        with self.assertRaises(ActionConfirmationNeeded):
            self.security.check_permission("shutdown_jarvis", {})


if __name__ == "__main__":
    unittest.main()
