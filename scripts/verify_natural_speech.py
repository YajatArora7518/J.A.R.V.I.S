"""Explicit real reply-only provider probe. Save audio; never contact anyone."""
import json
from pathlib import Path
import sys
import time
import wave
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.tts_engine import UniversalTTSEngine
import threading
from collections import OrderedDict

engine = UniversalTTSEngine.__new__(UniversalTTSEngine)
engine._cloud_retry_after = 0
engine._stop_requested = threading.Event()
engine._audio_cache = OrderedDict()
engine._audio_cache_bytes = 0
chunks = []
class Capture:
    def __init__(self, **kwargs): self.rate = kwargs['samplerate']
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def write(self, chunk): chunks.append(bytes(chunk))
started = time.monotonic()
with patch('sounddevice.RawOutputStream', Capture):
    success = engine._speak_natural('Haan bhai, sun raha hoon. Baat karte raho.')
report = {'success': success and bool(chunks), 'elapsed_seconds': round(time.monotonic()-started,2),
          'audio_bytes': sum(map(len,chunks)), 'source': 'real reply-only Gemini TTS; no extra user context'}
root = Path(__file__).resolve().parent.parent / 'scratch'
if report['success']:
    with wave.open(str(root/'natural_hinglish_probe.wav'),'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b''.join(chunks))
(root/'natural_hinglish_probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
sys.exit(0 if report['success'] else 1)
