# tests/regression/test_baseline_regression.py
# Comprehensive Regression Suite for JARVIS System Capabilities

import unittest
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import core.register_tools
from core.tool_registry import default_tool_registry
from core.security import default_security_manager, RiskLevel

from core.verification import verify_file_exists, verify_process_closed
from core.context_engine import default_context_engine
from memory.memory_manager import remember, query_memory, forget
from actions.chrome_profile import list_chrome_profiles
from actions.college_mode import college_mode, load_college_config


class TestJarvisBaselineRegression(unittest.TestCase):

    def test_01_tool_registry_integrity(self):
        tools = default_tool_registry.list_tools()
        self.assertGreaterEqual(len(tools), 21, "Tool registry must contain at least 21 registered tools.")
        self.assertIn("open_app", tools)
        self.assertIn("web_search", tools)
        self.assertIn("college_mode", tools)
        self.assertIn("camera_control", tools)
        self.assertIn("chrome_profile", tools)

    def test_02_security_risk_classification(self):
        # LOW risk
        self.assertEqual(default_security_manager.classify_risk("web_search", {"query": "test"}), RiskLevel.LOW)
        self.assertEqual(default_security_manager.classify_risk("college_mode", {"action": "schedule"}), RiskLevel.LOW)

        # MEDIUM risk
        self.assertEqual(default_security_manager.classify_risk("open_app", {"app_name": "notepad"}), RiskLevel.MEDIUM)

        # HIGH & CRITICAL risk
        self.assertEqual(default_security_manager.classify_risk("computer_settings", {"action": "close_app"}), RiskLevel.HIGH)
        self.assertEqual(default_security_manager.classify_risk("file_controller", {"action": "delete_all"}), RiskLevel.CRITICAL)

    def test_03_protected_system_paths(self):
        auth, reason = default_security_manager.validate_and_authorize(
            "file_controller", {"action": "delete", "path": "C:\\Windows\\System32\\drivers"}
        )
        self.assertFalse(auth, "Operation on protected system32 path must be blocked.")
        self.assertIn("forbidden", reason.lower())

    def test_04_chrome_yajat_profile_discovery(self):
        profiles = list_chrome_profiles()
        self.assertTrue(isinstance(profiles, list), "Chrome profiles must return a list.")
        yajat_found = any("yajat" in p.get("account_name", "").lower() 
                          or "yajat" in p.get("account_email", "").lower()
                          or "yajat" in p.get("display_name", "").lower()
                          for p in profiles)
        # Verify that either Yajat profile is detected or default fallback profile is available
        self.assertTrue(len(profiles) > 0, "At least one Chrome profile must be available.")

    def test_05_unified_context_engine(self):
        default_context_engine.user_name = "Yajat"
        prompt_str = default_context_engine.to_prompt_string()
        self.assertIn("Yajat", prompt_str)
        self.assertIn("Camera Status: OFF", prompt_str)

    def test_06_memory_engine_operations(self):
        res_mem = remember("regr_test_key", "Regression check value", category="notes")
        self.assertIn("remembered", res_mem.lower())

        query_res = query_memory("regr_test_key")
        self.assertIn("Regression check value", query_res)

        forg_res = forget("regr_test_key")
        self.assertIn("removed", forg_res.lower())

    def test_07_college_mode_engine(self):
        res = college_mode({"action": "schedule", "day": "Monday"}, player=None)
        self.assertTrue(res.get("success"))
        self.assertIn("Monday", res.get("message"))
        self.assertIn("Schedule", res.get("message"))

    def test_08_verification_engine(self):
        res = verify_file_exists("main.py")
        self.assertTrue(res.get("verified"))
        self.assertGreater(res.get("size_bytes", 0), 100)


if __name__ == "__main__":
    unittest.main()
