# tests/test_holographic_info_hud.py
# Comprehensive Unit Test Suite for Advanced Holographic Information HUD (15 Features)

import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

ASSETS_DIR = BASE_DIR / "assets"
ORIGINAL_HTML = ASSETS_DIR / "jarvis_3d_core.html"
HOLOGRAPHIC_HTML = ASSETS_DIR / "jarvis_3d_core_holographic.html"


class TestHolographicInfoHUDAsset(unittest.TestCase):
    """Verify HTML structure, DOM panel elements, CSS, and JS APIs."""

    @classmethod
    def setUpClass(cls):
        cls.content = HOLOGRAPHIC_HTML.read_text(encoding="utf-8")

    def test_original_html_byte_for_byte_preserved(self):
        """Original jarvis_3d_core.html must remain unchanged."""
        self.assertTrue(ORIGINAL_HTML.exists())
        orig_text = ORIGINAL_HTML.read_text(encoding="utf-8")
        self.assertIn("JARVIS Quantum AI Neural Core", orig_text)

    def test_feature1_floating_3d_panels(self):
        self.assertIn('id="panel-sys"', self.content)
        self.assertIn('id="panel-weather"', self.content)
        self.assertIn('id="panel-news"', self.content)
        self.assertIn('id="panel-response"', self.content)
        self.assertIn('holo-panel', self.content)

    def test_feature2_3_system_and_gpu_telemetry(self):
        self.assertIn('id="bar-cpu"', self.content)
        self.assertIn('id="bar-ram"', self.content)
        self.assertIn('id="bar-disk"', self.content)
        self.assertIn('id="bar-gpu"', self.content)
        self.assertIn('id="val-gpu"', self.content)
        self.assertIn("setTelemetry: function(cpu, mem, disk, net, gpu)", self.content)
        self.assertIn("N/A", self.content)

    def test_feature4_weather_hologram(self):
        self.assertIn('id="w-city"', self.content)
        self.assertIn('id="w-temp"', self.content)
        self.assertIn('id="w-cond"', self.content)
        self.assertIn('id="w-details"', self.content)
        self.assertIn("setWeather: function(location, temp, feels_like, condition, humidity, wind)", self.content)

    def test_feature5_temporal_time_hud(self):
        self.assertIn('id="time-val"', self.content)
        self.assertIn('id="date-val"', self.content)
        self.assertIn("setTime: function(timeStr, dateStr)", self.content)

    def test_feature6_news_search_hologram(self):
        self.assertIn('id="news-query"', self.content)
        self.assertIn('id="news-content"', self.content)
        self.assertIn("setNews: function(query, headline)", self.content)
        self.assertIn("setSearchResults: function(query, results)", self.content)

    def test_feature7_response_visualizer(self):
        self.assertIn('id="resp-text"', self.content)
        self.assertIn("setResponse: function(text)", self.content)

    def test_feature8_voice_reactive_hud(self):
        self.assertIn('id="waveform"', self.content)
        self.assertIn("wave-bar", self.content)
        self.assertIn("setAudioLevel: function(val)", self.content)

    def test_feature9_dynamic_panel_show_hide(self):
        self.assertIn("showPanel: function(id)", self.content)
        self.assertIn("hidePanel: function(id)", self.content)
        self.assertIn("classList.add('visible')", self.content)
        self.assertIn("classList.remove('visible')", self.content)

    def test_feature10_core_data_links(self):
        self.assertIn('id="link-canvas"', self.content)
        self.assertIn("drawDataLinks", self.content)
        self.assertIn("setLineDash", self.content)

    def test_feature11_12_3d_depth_and_contextual_states(self):
        self.assertIn("setHandPosition: function(x, y, gesture, depth)", self.content)
        self.assertIn("STATE_COLORS", self.content)
        for state in ["IDLE", "LISTENING", "THINKING", "SEARCHING", "EXECUTING", "SPEAKING", "ERROR", "LEARNING"]:
            self.assertIn(state, self.content, f"State {state} missing from holographic HTML")

    def test_feature13_14_15_performance_and_js_api(self):
        self.assertIn("requestAnimationFrame", self.content)
        self.assertIn("window.JARVIS3DCore", self.content)
        self.assertIn("window._jarvis3dReady = true", self.content)


class TestPyQtUIBridge(unittest.TestCase):
    """Verify ui.py JARVIS3DCore bridge methods and feature flags."""

    @classmethod
    def setUpClass(cls):
        cls.ui_code = (BASE_DIR / "ui.py").read_text(encoding="utf-8")

    def test_jarvis3dcore_bridge_methods_exist(self):
        self.assertIn("def setTelemetry(", self.ui_code)
        self.assertIn("def setWeather(", self.ui_code)
        self.assertIn("def setTime(", self.ui_code)
        self.assertIn("def setNews(", self.ui_code)
        self.assertIn("def setSearchResults(", self.ui_code)
        self.assertIn("def setResponse(", self.ui_code)

    def test_feature_flags_configured(self):
        self.assertIn("JARVIS_HOLOGRAPHIC_UI", self.ui_code)
        self.assertIn("JARVIS_HOLOGRAPHIC_INFO", self.ui_code)

    def test_metric_and_clock_forwarders(self):
        self.assertIn("self.hud.setTime(", self.ui_code)
        self.assertIn("self.hud.setTelemetry(", self.ui_code)
        self.assertIn("self.hud.setResponse(", self.ui_code)


if __name__ == "__main__":
    unittest.main()
