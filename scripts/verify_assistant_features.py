"""Real cloud vision and voice/tool integration using only artificial input."""
import asyncio
import io
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def verify():
    from PIL import Image, ImageDraw, ImageFont
    from config import get_api_key, get_live_model_name
    from google import genai
    from google.genai import types
    from main import JarvisLive
    from actions.screen_processor import analyze_screen_vision, invalidate_screen_cache
    from core.command_pipeline import process_user_command
    result = {}
    image = Image.new("RGB", (900, 350), "white")
    draw = ImageDraw.Draw(image)
    draw.text((45, 40), "JARVIS VISION TEST 4729", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40))
    draw.rectangle((70, 160, 190, 280), fill="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    invalidate_screen_cache()
    with patch("actions.screen_processor._capture_screenshot", return_value=buffer.getvalue()), patch("pygetwindow.getActiveWindow", return_value=SimpleNamespace(title="Artificial verification image")):
        vision = analyze_screen_vision("Read the four-digit number and identify the color of the square.")
    text = vision.get("message", "")
    result["vision"] = {"verified": bool(vision.get("success") and "4729" in text and "red" in text.lower()), "input": "artificial image", "response": text}
    arithmetic = process_user_command("calculate 27 * 13", source="chat")
    result["command_pipeline"] = {"verified": bool(arithmetic.get("success") and "351" in arithmetic.get("message", "")), "response": arithmetic.get("message")}
    class QuietUI:
        muted = True
        def set_state(self, _): pass
        def write_log(self, _): pass
    live = JarvisLive.__new__(JarvisLive)
    live.ui = QuietUI()
    live._command_lock = threading.RLock()
    live._turn_command_results = {}
    config = live._build_config()
    config.system_instruction = "You are a laptop assistant. For arithmetic always use assistant_command. After its verified result, say the numeric answer once in a natural short sentence."
    client = genai.Client(api_key=get_api_key(), http_options=types.HttpOptions(timeout=15000))
    calls, received_audio, output_text = [], False, []
    try:
        async with asyncio.timeout(30):
            async with client.aio.live.connect(model=get_live_model_name(), config=config) as session:
                await session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text="Use assistant_command with query calculate 27 * 13 and tell me the answer.")]), turn_complete=True)
                while not received_audio:
                    async for item in session.receive():
                        if item.tool_call:
                            responses = []
                            for call in item.tool_call.function_calls:
                                if call.name != "assistant_command":
                                    raise RuntimeError("Unexpected verification tool")
                                response = await live._execute_tool(call)
                                calls.append({"name": call.name, "query": call.args.get("query"), "verified": response.response.get("verified")})
                                responses.append(response)
                            await session.send_tool_response(function_responses=responses)
                        if item.data:
                            received_audio = True
                        content = item.server_content
                        if content and content.output_transcription and content.output_transcription.text:
                            output_text.append(content.output_transcription.text)
                        if content and content.turn_complete and received_audio:
                            break
        result["live_tool_voice"] = {"verified": bool(calls and all(c["verified"] for c in calls) and received_audio), "calls": calls, "audio_received": received_audio, "transcript": "".join(output_text)}
    except Exception as exc:
        result["live_tool_voice"] = {"verified": False, "error": type(exc).__name__, "calls": calls}
    finally:
        client.close()
    output = Path(__file__).resolve().parent.parent / "scratch" / "assistant_features.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(verify())
