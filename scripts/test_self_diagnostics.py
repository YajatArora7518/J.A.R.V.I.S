# scripts/test_self_diagnostics.py
# Behavior-focused unit and integration tests for Self Diagnostics (Phase 4G)

import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.diagnostics import SelfDiagnostics


class TestSelfDiagnostics(unittest.TestCase):

    def setUp(self):
        self.diag = SelfDiagnostics()

    def test_01_which_ai_query(self):
        """Verify 'Which AI are you using?' reports active engine and health."""
        reply = self.diag.handle_diagnostic_query("Which AI are you using?")
        self.assertIsNotNone(reply)
        self.assertTrue("Ollama" in reply or "Gemini" in reply)
        self.assertTrue("camera" in reply.lower())
        self.assertTrue("voice" in reply.lower())

    def test_02_system_status_check(self):
        """Verify 'JARVIS status' and 'Kya chal raha hai?' return complete health summary."""
        reply1 = self.diag.handle_diagnostic_query("JARVIS status")
        self.assertIsNotNone(reply1)
        self.assertIn("CPU", reply1)
        self.assertIn("RAM", reply1)

        reply2 = self.diag.handle_diagnostic_query("Kya chal raha hai?")
        self.assertIsNotNone(reply2)
        self.assertIn("subsystems operational", reply2.lower())

    def test_03_why_are_you_slow_explanation(self):
        """Verify 'Why are you slow?' diagnoses latency and resource load accurately."""
        reply = self.diag.handle_diagnostic_query("Why are you slow?")
        self.assertIsNotNone(reply)
        self.assertTrue("latency" in reply.lower() or "slow" in reply.lower() or "resource" in reply.lower())

    def test_04_zero_credentials_revealed(self):
        """Verify no sensitive API keys, tokens, or passwords can ever leak in diagnostic reports."""
        summary = self.diag.get_diagnostics_summary()
        summary_str = str(summary)
        for secret_indicator in ["sk-", "AIzaSy", "Bearer ", "password=", "token="]:
            self.assertNotIn(secret_indicator, summary_str)


if __name__ == "__main__":
    unittest.main()
