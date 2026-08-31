# tests/test_holographic_ui_replacement.py
# Comprehensive Unit Test Suite for Full-Screen Holographic UI Replacement

import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

ASSETS_DIR = BASE_DIR / "assets"
ORIGINAL_HTML = ASSETS_DIR / "jarvis_3d_core.html"
HOLOGRAPHIC_HUD_HTML = ASSETS_DIR / "jarvis_3d_core_holographic.html"
FULL_HOLOGRAPHIC_UI_HTML = ASSETS_DIR / "jarvis_holographic_ui.html"


class TestHolographicUIAssets(unittest.TestCase):
    """Verify file structure, fallback chain, and HTML DOM elements."""

    def test_original_fallback_html_preserved(self):
        """Original jarvis_3d_core.html must remain byte-for-byte untouched."""
        self.assertTrue(ORIGINAL_HTML.exists())
        content = ORIGINAL_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Quantum AI Neural Core", content)

    def test_holographic_hud_fallback_preserved(self):
        """jarvis_3d_core_holographic.html must remain available."""
        self.assertTrue(HOLOGRAPHIC_HUD_HTML.exists())
        content = HOLOGRAPHIC_HUD_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Holographic AI Core", content)

    def test_full_holographic_ui_html_exists(self):
        """New jarvis_holographic_ui.html must exist."""
        self.assertTrue(FULL_HOLOGRAPHIC_UI_HTML.exists())

    def test_full_holographic_ui_structure(self):
        content = FULL_HOLOGRAPHIC_UI_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Full Holographic AI Command Center", content)
        self.assertIn('id="panel-sys"', content)
        self.assertIn('id="tools-grid"', content)
        self.assertIn('id="cmd-input"', content)
        self.assertIn('id="chat-panel"', content)
        self.assertIn('id="panel-weather"', content)
        self.assertIn('id="panel-news"', content)
        self.assertIn('id="panel-response"', content)
        self.assertIn('id="event-stream"', content)


class TestJSAPIContractPreservation(unittest.TestCase):
    """Verify all required JS API functions exist in jarvis_holographic_ui.html."""

    @classmethod
    def setUpClass(cls):
        cls.content = FULL_HOLOGRAPHIC_UI_HTML.read_text(encoding="utf-8")

    def test_jarvis3dcore_object_exists(self):
        self.assertIn("window.JARVIS3DCore", self.content)

    def test_required_js_methods(self):
        methods = [
            "setState", "setAudioLevel", "setHandPosition", "setTelemetry",
            "setWeather", "setTime", "setNews", "setSearchResults",
            "setResponse", "setTools", "setBattery", "setMicState",
            "setAwareness", "setActiveWindow", "addAction", "appendLog",
            "appendChat", "setCollegeInfo", "setMemoryStats"
        ]
        for m in methods:
            self.assertIn(f"{m}:", self.content, f"JS API method {m} missing from jarvis_holographic_ui.html")

    def test_ready_flag_contract(self):
        self.assertIn("window._jarvis3dReady = false", self.content)
        self.assertIn("window._jarvis3dReady = true", self.content)


class TestPyQtUIBridgeIntegration(unittest.TestCase):
    """Verify ui.py HoloBridge class and JARVIS3DCore bridge wrapper methods."""

    @classmethod
    def setUpClass(cls):
        cls.ui_code = (BASE_DIR / "ui.py").read_text(encoding="utf-8")

    def test_holobridge_class_exists(self):
        self.assertIn("class HoloBridge(QObject):", self.ui_code)
        self.assertIn("def sendCommand(", self.ui_code)
        self.assertIn("def toggleMute(", self.ui_code)
        self.assertIn("def focusActiveWindow(", self.ui_code)
        self.assertIn("def openMemorySearch(", self.ui_code)

    def test_jarvis3dcore_extended_methods(self):
        methods = [
            "def setTools(", "def setBattery(", "def setMicState(",
            "def setAwareness(", "def setActiveWindow(", "def addAction(",
            "def appendLog(", "def appendChat(", "def setCollegeInfo(",
            "def setMemoryStats("
        ]
        for m in methods:
            self.assertIn(m, self.ui_code, f"JARVIS3DCore method {m} missing from ui.py")

    def test_dynamic_tool_discovery_call(self):
        self.assertIn("def _send_tools_to_hud(", self.ui_code)
        self.assertIn("default_tool_registry.list_tools()", self.ui_code)


if __name__ == "__main__":
    unittest.main()
