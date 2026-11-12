"""Read-only connection check. No microphones, screenshots or messages are used."""
import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_api_key, get_live_model_name, get_model_name, get_runtime_config
from core.ai_policy import is_cloud_ai_allowed


async def main():
    result = {"cloud_allowed": is_cloud_ai_allowed(), "gemini_key_configured": bool(get_api_key()), "openrouter_key_configured": bool(get_api_key("openrouter_api_key"))}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
            result["ollama"] = {"ready": True, "models": [m["name"] for m in json.load(response).get("models", [])]}
    except Exception as exc:
        result["ollama"] = {"ready": False, "error": type(exc).__name__}
    if result["cloud_allowed"] and get_api_key():
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=get_api_key(), http_options=types.HttpOptions(timeout=12000))
        try:
            started = time.monotonic()
            reply = client.models.generate_content(model=get_model_name(), contents="Reply with READY, one word only.", config=types.GenerateContentConfig(max_output_tokens=32))
            result["text"] = {"ready": bool(reply.text), "model": get_model_name(), "latency_ms": round((time.monotonic() - started) * 1000)}
        except Exception as exc:
            result["text"] = {"ready": False, "error": type(exc).__name__, "code": getattr(exc, "code", None)}
        result["live"] = []
        for model in [get_live_model_name()] + get_runtime_config().get("live_fallback_models", []):
            try:
                async with asyncio.timeout(15):
                    async with client.aio.live.connect(model=model, config=types.LiveConnectConfig(response_modalities=["AUDIO"])) as session:
                        await session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text="Say Ready, one word only.")]), turn_complete=True)
                        received_audio = False
                        async for item in session.receive():
                            if item.data:
                                received_audio = True
                            if item.server_content and item.server_content.turn_complete:
                                break
                        result["live"].append({"ready": received_audio, "model": model})
                        if received_audio:
                            break
            except Exception as exc:
                result["live"].append({"ready": False, "model": model, "error": type(exc).__name__, "code": getattr(exc, "code", None)})
        client.close()
    print(json.dumps(result, indent=2))
    output = Path(__file__).resolve().parent.parent / "scratch" / "assistant_connections.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
