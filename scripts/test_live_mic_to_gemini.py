import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import asyncio
import json
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

def get_api_key():
    config_path = Path("config/api_keys.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

async def stream_live_mic():
    client = genai.Client(
        api_key=get_api_key(),
        http_options={"api_version": "v1beta"}
    )
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription={},
        input_audio_transcription={},
    )
    
    model = "models/gemini-2.5-flash-native-audio-latest"
    print(f"[LIVE TEST] Connecting to Gemini Live ({model})...")
    
    out_queue = asyncio.Queue(maxsize=100)
    loop = asyncio.get_running_loop()
    
    counters = {
        "frames_captured": 0,
        "bytes_captured": 0,
        "chunks_sent": 0,
        "transcripts_received": 0,
        "rms_values": [],
        "peaks": [],
    }
    
    def mic_callback(indata, frames, time_info, status):
        data = indata.tobytes()
        counters["frames_captured"] += 1
        counters["bytes_captured"] += len(data)
        
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(samples ** 2))
        peak = np.max(np.abs(samples))
        counters["rms_values"].append(rms)
        counters["peaks"].append(peak)
        
        try:
            out_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

    async with client.aio.live.connect(model=model, config=config) as session:
        print("[LIVE TEST] ✅ Gemini Live session connected!")
        
        # Audio sender task
        async def send_task():
            while True:
                data = await out_queue.get()
                try:
                    await session.send_realtime_input(
                        media=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                    )
                    counters["chunks_sent"] += 1
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[LIVE TEST] ⚠️ Send error: {e}")
        
        # Audio receiver task
        async def recv_task():
            user_transcript = []
            async for resp in session.receive():
                if resp.server_content:
                    sc = resp.server_content
                    if sc.input_transcription and sc.input_transcription.text:
                        txt = sc.input_transcription.text.strip()
                        if txt:
                            counters["transcripts_received"] += 1
                            user_transcript.append(txt)
                            print(f"[LIVE TRANSCRIPTION] 👤 '{txt}'")
                    if sc.turn_complete:
                        full_text = " ".join(user_transcript).strip()
                        print(f"[LIVE TURN COMPLETE] Full user speech: '{full_text}'")
                        user_transcript = []
                    if sc.output_transcription and sc.output_transcription.text:
                        print(f"[JARVIS SPEECH TEXT] 🤖 '{sc.output_transcription.text.strip()}'")

        sender = asyncio.create_task(send_task())
        receiver = asyncio.create_task(recv_task())
        
        print("\n" + "="*60)
        print("🎤 MICROPHONE CAPTURE IS OPEN FOR 6 SECONDS.")
        print("   If you speak into your microphone right now,")
        print("   real speech will stream to Gemini Live.")
        print("="*60 + "\n")
        
        try:
            with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1024, callback=mic_callback):
                await asyncio.sleep(6.0)
        finally:
            sender.cancel()
            receiver.cancel()
            
        print("\n[LIVE TEST SUMMARY]")
        print(f"  Frames captured : {counters['frames_captured']}")
        print(f"  Bytes captured  : {counters['bytes_captured']}")
        print(f"  Chunks sent     : {counters['chunks_sent']}")
        print(f"  Transcripts rx  : {counters['transcripts_received']}")
        if counters['rms_values']:
            print(f"  Average RMS     : {np.mean(counters['rms_values']):.2f}")
            print(f"  Max Peak        : {np.max(counters['peaks'])}")

if __name__ == "__main__":
    asyncio.run(stream_live_mic())
