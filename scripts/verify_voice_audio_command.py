"""Verify actual Live speech input with synthetic audio and harmless arithmetic."""
import asyncio
import json
from pathlib import Path
import sys
import threading
import wave
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_api_key, get_live_model_name
from google import genai
from google.genai import types
from main import JarvisLive


def synthesize(path, text="Jarvis, calculate twenty seven times thirteen."):
    import win32com.client
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Format.Type = 18  # SAFT16kHz16BitMono; verify the actual WAV below.
    stream.Open(str(path), 3, False)
    try:
        voice.AudioOutputStream = stream
        voice.Speak(text, 0)
    finally:
        stream.Close()
    with wave.open(str(path), "rb") as audio:
        assert (audio.getframerate(), audio.getsampwidth(), audio.getnchannels()) == (16000, 2, 1)
        return audio.readframes(audio.getnframes())


async def verify():
    root = Path(__file__).resolve().parent.parent
    pcm = synthesize(root/"scratch"/"voice_command_fixture.wav")
    background = synthesize(root/"scratch"/"voice_background_fixture.wav", "Calculate nineteen times twenty.")
    logs = []
    class QuietUI:
        muted = True
        def set_state(self, _): pass
        def write_log(self, text): logs.append(text)
    live = JarvisLive.__new__(JarvisLive)
    live.ui = QuietUI()
    live._command_lock = threading.RLock()
    live._turn_command_results = {}
    live._turn_had_tool_call = False
    live._turn_received_audio = False
    live._voice_require_address = True
    live._mic_stats = {"frames_sent": 0, "last_audio_ts": 0, "send_errors": 0, "transcript_events": 0, "speech_segments": 0}
    live.out_queue, live.audio_in_queue = asyncio.Queue(), asyncio.Queue()
    live.set_speaking = MagicMock()
    live._update_proactive_state = MagicMock()
    live.speak = MagicMock()
    config = live._build_config()
    config.system_instruction = (root/"core"/"prompt.txt").read_text(encoding="utf-8")
    client = genai.Client(api_key=get_api_key(), http_options=types.HttpOptions(timeout=15000))
    report = {"input": "synthetic 16kHz speech; no live microphone capture", "production_sender_receiver": True,
              "calls": [], "audio_response": False, "input_transcript": "", "output_transcript": ""}
    original_execute = live._execute_tool
    async def arithmetic_only(call):
        from core.intent_router import classify_intent
        assert call.name == "assistant_command" and classify_intent(call.args.get("query", ""))["intent"] == "COMPUTATION", "Unexpected voice test action refused"
        response = await original_execute(call)
        report["calls"].append({"query": call.args.get("query"), "verified": response.response.get("verified"), "message": response.response.get("message")})
        return response
    live._execute_tool = arithmetic_only
    try:
        async with asyncio.timeout(50):
            async with client.aio.live.connect(model=get_live_model_name(), config=config) as session:
                class SessionObserver:
                    async def receive(self):
                        async for item in session.receive():
                            sc = item.server_content
                            if sc:
                                for field, key in ((sc.input_transcription, "input_transcript"), (sc.output_transcription, "output_transcript")):
                                    if field and field.text:
                                        report[key] += field.text
                            yield item
                    async def send_realtime_input(self, **kwargs):
                        return await session.send_realtime_input(**kwargs)
                    async def send_tool_response(self, **kwargs):
                        return await session.send_tool_response(**kwargs)
                live.session = SessionObserver()

                async def stream(audio):
                    for offset in range(0, len(audio), 3200):
                        await live.out_queue.put({"data": audio[offset:offset+3200], "mime_type": "audio/pcm;rate=16000"})
                        await asyncio.sleep(.1)
                    for _ in range(15):
                        await live.out_queue.put({"data": bytes(3200), "mime_type": "audio/pcm;rate=16000"})
                        await asyncio.sleep(.1)

                with patch("main._update_memory_async"), patch("main._is_session_active", return_value=True):
                    sender = asyncio.create_task(live._send_realtime())
                    receiver = asyncio.create_task(live._receive_audio())
                    try:
                        await stream(background)
                        await asyncio.sleep(3)
                        report["background_ignored"] = not report["calls"] and live.audio_in_queue.empty() and not logs
                        await stream(pcm)
                        await session.send_realtime_input(audio_stream_end=True)
                        while not any(text.startswith("Jarvis:") and "351" in text for text in logs):
                            if receiver.done():
                                await receiver
                            await asyncio.sleep(.1)
                        report["audio_response"] = not live.audio_in_queue.empty()
                        report["ui_response"] = next(text for text in logs if text.startswith("Jarvis:") and "351" in text)
                        report["frames_sent"] = live._mic_stats["frames_sent"]
                        report["send_errors"] = live._mic_stats["send_errors"]
                    finally:
                        sender.cancel()
                        receiver.cancel()
                        await asyncio.gather(sender, receiver, return_exceptions=True)
        report["verified"] = bool(report.get("background_ignored") and len(report["calls"]) == 1 and report["calls"][0]["verified"] and "351" in report["calls"][0]["message"] and report["audio_response"])
    except Exception as exc:
        report.update(verified=False, error=type(exc).__name__, code=getattr(exc, "code", None))
    finally:
        client.close()
    (root/"scratch"/"voice_audio_command_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["verified"]:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify())
