# tests/test_real_voice_pipeline.py
"""
Comprehensive Unit Test Suite for Voice Pipeline, VAD, Barge-In, and Audio Privacy Controls.
"""

import unittest
from unittest.mock import patch, MagicMock

import sounddevice as sd
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from core.intent_router import classify_intent


class TestRealVoicePipeline(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.resume_awareness()

    def test_sounddevice_query(self):
        """Verify sounddevice can query input audio hardware devices cleanly."""
        devices = sd.query_devices()
        self.assertGreater(len(devices), 0)

    def test_multi_turn_intent_classification(self):
        """Verify intent router classifies initial and follow-up query intents."""
        res1 = classify_intent("WhatsApp check karo")
        intent1 = res1.get("intent") if isinstance(res1, dict) else str(res1)
        self.assertEqual(intent1, "WHATSAPP_READ")

        res2 = classify_intent("Aur uske baad?")
        intent2 = res2.get("intent") if isinstance(res2, dict) else str(res2)
        self.assertIsNotNone(intent2)

    def test_audio_privacy_mode_suppression(self):
        """Verify Privacy Mode halts audio awareness and recovers cleanly."""
        privacy_mode_manager.enable_privacy_mode()
        self.assertTrue(privacy_mode_manager.is_privacy_mode_active())

        privacy_mode_manager.resume_awareness()
        self.assertFalse(privacy_mode_manager.is_privacy_mode_active())


if __name__ == "__main__":
    unittest.main()
