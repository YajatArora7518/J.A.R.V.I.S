import asyncio
import json
import time
from pathlib import Path
from google import genai
from google.genai import types

def get_api_key():
    config_path = Path("config/api_keys.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]

async def main():
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
    print(f"[TEST] Connecting to Gemini Live with model '{model}'...")
    
    async with client.aio.live.connect(model=model, config=config) as session:
        print("[TEST] Connected!")
        
        # Test sending media chunk with types.Blob
        silence = bytes(3200) # 100ms at 16000Hz 16-bit mono
        print("[TEST] Sending media chunk using types.Blob...")
        await session.send_realtime_input(
            media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
        )
        print("[TEST] Successfully sent media chunk without WebSocket crash!")
        
        # Test receiving response with timeout
        print("[TEST] Waiting for server events (5s timeout)...")
        try:
            async with asyncio.timeout(5.0):
                async for response in session.receive():
                    print("[TEST] Received event:", response)
                    if response.server_content:
                        sc = response.server_content
                        print("  model_turn:", sc.model_turn is not None)
                        print("  turn_complete:", sc.turn_complete)
                        print("  interrupted:", sc.interrupted)
                    break
        except asyncio.TimeoutError:
            print("[TEST] Timeout reached cleanly (expected if silence produced no speech turn).")

if __name__ == "__main__":
    asyncio.run(main())
