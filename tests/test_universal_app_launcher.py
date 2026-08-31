# tests/test_universal_app_launcher.py
# Comprehensive automated test suite for JARVIS Universal Installed Application Launcher

import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.universal_app_resolver import UniversalApplicationResolver, default_app_resolver, InstalledAppCatalog
from actions.application_launch_executor import ApplicationLaunchExecutor, default_launch_executor, ActionResult
from actions.open_app import open_app_structured
from core.intent_router import classify_intent
from core.command_pipeline import process_user_command


class TestUniversalAppLauncher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.resolver = UniversalApplicationResolver()
        cls.executor = ApplicationLaunchExecutor()

    def test_01_dynamic_catalog_discovery(self):
        """Verify dynamic discovery of installed applications."""
        catalog = self.resolver.catalog.get_catalog()
        self.assertGreater(len(catalog), 0, "App catalog should discover installed applications.")
        print(f"\n[TEST] Discovered {len(catalog)} app entries in dynamic catalog.")

    def test_02_intent_separation(self):
        """Verify strict separation of LAUNCH_APPLICATION, WEB_SEARCH, STORE_SEARCH, and INSTALL_APPLICATION."""
        # A. Launch Application
        res_launch = classify_intent("Open Chrome")
        self.assertEqual(res_launch["intent"], "WINDOWS_APPLICATION")
        self.assertEqual(res_launch["tool"], "open_app")

        res_launch2 = classify_intent("Launch VS Code")
        self.assertEqual(res_launch2["intent"], "WINDOWS_APPLICATION")

        res_launch3 = classify_intent("Start Spotify")
        self.assertEqual(res_launch3["intent"], "WINDOWS_APPLICATION")

        res_launch4 = classify_intent("Open Antigravity")
        self.assertEqual(res_launch4["intent"], "WINDOWS_APPLICATION")

        # B. Web Search
        res_search = classify_intent("Search for Chrome")
        self.assertEqual(res_search["intent"], "WEB_SEARCH")
        self.assertEqual(res_search["tool"], "web_search")

        res_search2 = classify_intent("Search Google for VS Code")
        self.assertEqual(res_search2["intent"], "WEB_SEARCH")

        res_search3 = classify_intent("Find information about Spotify")
        self.assertEqual(res_search3["intent"], "WEB_SEARCH")

        # C. Store Search
        res_store = classify_intent("Find Chrome on Microsoft Store")
        self.assertEqual(res_store["intent"], "STORE_SEARCH")

        res_store2 = classify_intent("Search Microsoft Store for Spotify")
        self.assertEqual(res_store2["intent"], "STORE_SEARCH")

        # D. Install Application
        res_install = classify_intent("Install Spotify")
        self.assertEqual(res_install["intent"], "INSTALL_APPLICATION")

        print("[TEST] Intent separation passed 100%.")

    def test_03_alias_resolution(self):
        """Verify generic alias matching for installed apps."""
        desc_chrome = self.resolver.resolve_application("Chrome")
        if desc_chrome:
            self.assertIn("chrome", desc_chrome.normalized_name.lower())

        desc_vscode = self.resolver.resolve_application("VS Code")
        if desc_vscode:
            self.assertTrue("code" in desc_vscode.normalized_name.lower() or "visual studio" in desc_vscode.display_name.lower())

        desc_edge = self.resolver.resolve_application("Edge")
        if desc_edge:
            self.assertIn("edge", desc_edge.normalized_name.lower())

        desc_notepad = self.resolver.resolve_application("Notepad")
        self.assertIsNotNone(desc_notepad)
        self.assertEqual(desc_notepad.display_name.lower(), "notepad")

        desc_calc = self.resolver.resolve_application("Calculator")
        self.assertIsNotNone(desc_calc)

        desc_explorer = self.resolver.resolve_application("File Explorer")
        self.assertIsNotNone(desc_explorer)

        print("[TEST] Alias resolution passed.")

    def test_04_non_existent_app_failure(self):
        """Verify that a non-existent app returns honest local failure and NEVER opens Store or Web."""
        target_name = "XYZ_THIS_APP_DOES_NOT_EXIST"
        
        # Resolver check
        desc = self.resolver.resolve_application(target_name)
        self.assertIsNone(desc, "Resolver must return None for non-existent applications.")

        # Structured Action check
        res = open_app_structured(target_name)
        self.assertFalse(res["success"], "Action must report failure for non-existent applications.")
        self.assertEqual(res["mode"], "none", "Mode must be 'none' (NO web_fallback).")
        self.assertIn("couldn't find", res["message"].lower())

        print("[TEST] Non-existent app failure test passed (No Store/Web fallback).")

    def test_05_real_launch_notepad_and_calculator(self):
        """Verify real launch and verification of System/Win32/Packaged apps (Notepad & Calculator)."""
        # Test 1: Notepad
        res_note = open_app_structured("Notepad")
        self.assertTrue(res_note["success"], f"Notepad launch failed: {res_note.get('message')}")
        self.assertEqual(res_note["mode"], "desktop")

        # Test 2: Calculator
        res_calc = open_app_structured("Calculator")
        self.assertTrue(res_calc["success"], f"Calculator launch failed: {res_calc.get('message')}")

        print("[TEST] Real launch and verification of Notepad and Calculator passed.")

    def test_06_multi_app_command_execution(self):
        """Verify sequential execution and verification of multi-app commands."""
        res_multi = process_user_command("Open Notepad, Calculator and File Explorer")
        self.assertTrue(res_multi["success"], f"Multi-app command failed: {res_multi.get('message')}")
        self.assertEqual(res_multi.get("status"), "COMPLETED")

        # Test multi-app command with a non-existent app failure in sequence
        res_fail = process_user_command("Open Notepad, XYZ_DOES_NOT_EXIST and Calculator")
        self.assertFalse(res_fail["success"], "Multi-app command containing invalid app must fail.")
        self.assertEqual(res_fail.get("status"), "MULTI_APP_FAILED")
        self.assertIn("failed to launch", res_fail["message"].lower())

        print("[TEST] Multi-app sequential execution and partial failure handling passed.")


if __name__ == "__main__":
    unittest.main()
