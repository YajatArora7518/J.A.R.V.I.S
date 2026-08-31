# tests/test_single_execution_guarantee.py
# Automated Regression Guard Asserting Single-Execution Invariant

import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.command_pipeline import process_user_command

class TestSingleExecutionGuarantee(unittest.TestCase):

    def test_deterministic_command_counts(self):
        result = process_user_command("volume badhao", source="test")
        self.assertTrue(result.get("success", False))
        
        metrics = result.get("execution_metrics", {})
        self.assertLessEqual(metrics.get("stt", 1), 1)
        self.assertEqual(metrics.get("intent", 1), 1)
        self.assertLessEqual(metrics.get("context", 0), 1)
        self.assertLessEqual(metrics.get("tool", 0), 1)
        self.assertEqual(metrics.get("llm", 0), 0, "Deterministic command MUST bypass LLM")
        self.assertLessEqual(metrics.get("tts", 1), 1)

    def test_whatsapp_call_command_counts(self):
        result = process_user_command("Aman ko call karo", source="test")
        intent_type = result.get("intent") or result.get("details", {}).get("intent")
        self.assertEqual(intent_type, "WHATSAPP_CALL")
        
        metrics = result.get("execution_metrics", {})
        self.assertEqual(metrics.get("intent", 1), 1)
        self.assertEqual(metrics.get("llm", 0), 0, "WhatsApp call fast path MUST bypass LLM")

    def test_app_close_command_counts(self):
        result = process_user_command("Chrome band karo", source="test")
        self.assertTrue(result.get("success", False))
        
        metrics = result.get("execution_metrics", {})
        self.assertEqual(metrics.get("intent", 1), 1)
        self.assertEqual(metrics.get("llm", 0), 0, "App close fast path MUST bypass LLM")

if __name__ == "__main__":
    unittest.main()
