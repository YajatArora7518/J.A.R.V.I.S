# tests/test_holographic_hud.py
# Holographic HUD Feature Tests — Zero Regression on Existing Functionality

import os
import sys
import re
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

ASSETS_DIR = BASE_DIR / "assets"
ORIGINAL_HTML = ASSETS_DIR / "jarvis_3d_core.html"
HOLOGRAPHIC_HTML = ASSETS_DIR / "jarvis_3d_core_holographic.html"


class TestHolographicHUDFiles(unittest.TestCase):
    """Verify file existence and structure."""

    def test_original_html_exists(self):
        """Original jarvis_3d_core.html must still exist as fallback."""
        self.assertTrue(ORIGINAL_HTML.exists(), "Original jarvis_3d_core.html is missing")

    def test_holographic_html_exists(self):
        """New holographic HTML must exist."""
        self.assertTrue(HOLOGRAPHIC_HTML.exists(), "jarvis_3d_core_holographic.html is missing")

    def test_original_html_not_modified(self):
        """Original HTML must contain its original title marker."""
        content = ORIGINAL_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Quantum AI Neural Core", content,
                      "Original HTML appears modified — title marker missing")

    def test_holographic_html_has_correct_title(self):
        content = HOLOGRAPHIC_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Holographic AI Core", content)


class TestJavaScriptAPIContract(unittest.TestCase):
    """Verify the holographic HTML preserves the exact JS API contract."""

    @classmethod
    def setUpClass(cls):
        cls.content = HOLOGRAPHIC_HTML.read_text(encoding="utf-8")

    def test_jarvis3dcore_object_exists(self):
        self.assertIn("window.JARVIS3DCore", self.content)

    def test_setState_function(self):
        self.assertIn("setState: function(state)", self.content)

    def test_setAudioLevel_function(self):
        self.assertIn("setAudioLevel: function(val)", self.content)

    def test_setHandPosition_function(self):
        self.assertIn("setHandPosition: function(x, y, gesture, depth)", self.content)

    def test_setCameraState_function(self):
        self.assertIn("window.setCameraState = function(active)", self.content)

    def test_jarvis3dReady_flag(self):
        # Must start as false, then set to true at end
        self.assertIn("window._jarvis3dReady = false", self.content)
        self.assertIn("window._jarvis3dReady = true", self.content)

    def test_camera_indicator_element(self):
        self.assertIn('id="camera-indicator"', self.content)

    def test_state_text_element(self):
        self.assertIn('id="state-text"', self.content)

    def test_telem_audio_element(self):
        self.assertIn('id="telem-audio"', self.content)

    def test_telem_hand_element(self):
        self.assertIn('id="telem-hand"', self.content)


class TestOriginalAPIContractPreserved(unittest.TestCase):
    """Verify original HTML also has the same API (baseline check)."""

    @classmethod
    def setUpClass(cls):
        cls.content = ORIGINAL_HTML.read_text(encoding="utf-8")

    def test_original_has_setState(self):
        self.assertIn("setState: function(state)", self.content)

    def test_original_has_setAudioLevel(self):
        self.assertIn("setAudioLevel: function(val)", self.content)

    def test_original_has_setHandPosition(self):
        self.assertIn("setHandPosition: function(x, y, gesture, depth)", self.content)

    def test_original_has_setCameraState(self):
        self.assertIn("window.setCameraState = function(active)", self.content)

    def test_original_has_ready_flag(self):
        self.assertIn("window._jarvis3dReady = true", self.content)


class TestFeatureFlag(unittest.TestCase):
    """Verify the feature flag mechanism in ui.py."""

    @classmethod
    def setUpClass(cls):
        cls.ui_content = (BASE_DIR / "ui.py").read_text(encoding="utf-8")

    def test_feature_flag_env_var_present(self):
        self.assertIn("JARVIS_HOLOGRAPHIC_UI", self.ui_content)

    def test_holographic_html_reference(self):
        self.assertIn("jarvis_3d_core_holographic.html", self.ui_content)

    def test_original_fallback_preserved(self):
        self.assertIn("jarvis_3d_core.html", self.ui_content)

    def test_fallback_logic_exists(self):
        """The code must fallback to original if holographic HTML doesn't exist."""
        self.assertIn("guaranteed fallback", self.ui_content)


class TestHolographicVisualContent(unittest.TestCase):
    """Verify the holographic HTML has the expected visual features."""

    @classmethod
    def setUpClass(cls):
        cls.content = HOLOGRAPHIC_HTML.read_text(encoding="utf-8")

    def test_has_corner_brackets(self):
        self.assertIn("corner-bracket", self.content)

    def test_has_scanning_line(self):
        self.assertIn("scan-line", self.content)

    def test_has_radar_sweep(self):
        self.assertIn("radar-sweep", self.content)

    def test_has_holographic_grid(self):
        self.assertIn("GridHelper", self.content)

    def test_has_data_streams(self):
        self.assertIn("data-stream", self.content)

    def test_has_waveform_bars(self):
        self.assertIn("wave-bar", self.content)

    def test_has_concentric_rings(self):
        # Should have 5 rings instead of 3
        self.assertIn("makeRing", self.content)

    def test_has_state_color_system(self):
        self.assertIn("STATE_COLORS", self.content)

    def test_supports_all_states(self):
        for state in ["IDLE", "LISTENING", "THINKING", "SPEAKING", "EXECUTING", "ERROR"]:
            self.assertIn(state, self.content, f"State {state} not found in holographic HTML")

    def test_three_js_import(self):
        self.assertIn("import * as THREE from 'three'", self.content)

    def test_bloom_postprocessing(self):
        self.assertIn("UnrealBloomPass", self.content)


class TestUIExceptionIsolation(unittest.TestCase):
    """Verify that if holographic HTML were missing, the system would not crash."""

    def test_missing_holographic_falls_back(self):
        """Simulate: if holographic file didn't exist, code path falls back to original."""
        # This tests the logic pattern, not runtime
        ui_content = (BASE_DIR / "ui.py").read_text(encoding="utf-8")
        # The code must check if html_path.exists() and fallback
        self.assertIn("if not html_path.exists()", ui_content)


if __name__ == "__main__":
    unittest.main()
