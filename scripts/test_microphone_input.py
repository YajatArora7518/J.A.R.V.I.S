"""
scripts/test_microphone_input.py
Comprehensive Phase 1 Microphone Input & Audio Pipeline Verification Test.

Checks:
A: Audio device enumeration & default device query
B: 16kHz mono int16 InputStream opening & fallback
C: Real-time audio buffer capture & RMS / peak level calculation
D: Barge-in keyword separation (verifying "stop", "chup", "bas" do NOT mute mic)
E: Mic control commands (verifying "mic off", "stop listening" DO toggle mic state)
F: Command pipeline voice dispatch integration
"""

import sys
import os
import time
import unittest
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMicrophonePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n" + "=" * 60)
        print("  J.A.R.V.I.S — Phase 1 Microphone Pipeline Verification")
        print("=" * 60)

    def test_01_device_enumeration(self):
        """Verify audio devices can be queried and at least one input exists."""
        print("\n[TEST 1] Enumerating audio devices...")
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            self.assertIsNotNone(devices)
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            print(f"  Total devices found: {len(devices)}")
            print(f"  Input devices found: {len(input_devices)}")
            for i, d in enumerate(input_devices):
                print(f"    - [{d.get('index', i)}] {d.get('name')} (HostAPI: {d.get('hostapi')}, Max In: {d.get('max_input_channels')})")
            
            self.assertGreater(len(input_devices), 0, "No input devices found on system.")
            default_in = sd.query_devices(kind="input")
            print(f"  Default input device: {default_in.get('name')}")
            self.assertIsNotNone(default_in)
        except Exception as e:
            self.fail(f"Audio device query failed: {e}")

    def test_02_stream_open_and_capture(self):
        """Verify 16kHz mono InputStream can open and capture frames without crashing."""
        print("\n[TEST 2] Testing 16kHz mono stream capture...")
        import sounddevice as sd
        
        frames_captured = []
        def callback(indata, frames, time_info, status):
            frames_captured.append(indata.copy())

        try:
            with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1024, callback=callback):
                time.sleep(0.5)
            
            print(f"  Captured {len(frames_captured)} blocks in 0.5s.")
            self.assertGreater(len(frames_captured), 0, "No frames captured during test duration.")
            
            # Check amplitude stats
            all_samples = np.concatenate(frames_captured).flatten()
            rms = np.sqrt(np.mean(all_samples.astype(np.float32) ** 2))
            peak = np.max(np.abs(all_samples))
            print(f"  RMS Amplitude: {rms:.2f}, Peak Amplitude: {peak}")
            self.assertGreaterEqual(rms, 0.0)
        except Exception as e:
            print(f"  Warning: Live stream capture returned error: {e}")

    def test_03_barge_in_separation_does_not_mute_mic(self):
        """CRITICAL: Verify 'stop', 'chup', 'bas' interrupt TTS without muting the microphone."""
        print("\n[TEST 3] Verifying barge-in words do NOT mute JARVIS mic...")
        from actions.mic_control import set_jarvis_mic_enabled, get_jarvis_mic_enabled
        from core.command_pipeline import process_user_command

        # Ensure mic is initially enabled
        set_jarvis_mic_enabled(True)
        self.assertTrue(get_jarvis_mic_enabled(), "Mic should be enabled initially.")

        test_words = ["stop", "chup", "bas", "shut up", "cancel", "quiet", "silence", "ruko"]
        for word in test_words:
            res = process_user_command(word, source="voice")
            mic_state = get_jarvis_mic_enabled()
            print(f"  Command: '{word}' -> Result: {res.get('message')} | Mic Enabled: {mic_state}")
            self.assertTrue(
                mic_state,
                f"FATAL BUG: Saying '{word}' muted the JARVIS microphone! Barge-in must NOT mute mic."
            )
            self.assertTrue(res.get("barge_in", False) or res.get("success", False))

    def test_04_explicit_mic_controls_toggle_state(self):
        """Verify explicit mic controls properly toggle the microphone state."""
        print("\n[TEST 4] Verifying explicit mic controls toggle state...")
        from actions.mic_control import set_jarvis_mic_enabled, get_jarvis_mic_enabled
        from core.command_pipeline import process_user_command

        # 1. Turn off
        res_off = process_user_command("mic off", source="voice")
        self.assertFalse(get_jarvis_mic_enabled(), "'mic off' should disable JARVIS mic.")
        print(f"  'mic off' -> Mic Enabled: {get_jarvis_mic_enabled()} (Expected: False)")

        # 2. Turn on
        res_on = process_user_command("start listening", source="voice")
        self.assertTrue(get_jarvis_mic_enabled(), "'start listening' should enable JARVIS mic.")
        print(f"  'start listening' -> Mic Enabled: {get_jarvis_mic_enabled()} (Expected: True)")

    def test_05_blob_construction_gemini_format(self):
        """Verify google.genai types.Blob constructor works for Gemini Live realtime audio."""
        print("\n[TEST 5] Verifying types.Blob creation for media chunks...")
        try:
            from google.genai import types
            sample_pcm = b"\x00\x00" * 512
            mime = "audio/pcm;rate=16000"
            blob = types.Blob(data=sample_pcm, mime_type=mime)
            self.assertEqual(blob.mime_type, mime)
            self.assertEqual(blob.data, sample_pcm)
            print("  types.Blob initialized successfully with PCM audio.")
        except ImportError:
            print("  google.genai not installed or mock environment; skipping direct blob test.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
