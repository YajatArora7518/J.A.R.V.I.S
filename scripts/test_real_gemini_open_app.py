import sys
import os
from pathlib import Path

# Add root directory to sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import asyncio
import json
import traceback
from google import genai
from google.genai import types

from main import _get_api_key, LIVE_MODEL, TOOL_DECLARATIONS
from core.register_tools import default_tool_registry, initialize_all_tools
from core.command_pipeline import process_user_command

initialize_all_tools()

class DummyUI:
    def __init__(self):
        self.muted = False
    def set_state(self, s):
        print(f"[DummyUI] set_state: {s}")
    def write_log(self, s):
        print(f"[DummyUI] write_log: {s}")
    def add_recent_action(self, s):
        print(f"[DummyUI] add_recent_action: {s}")

async def test_gemini_live():
    ui = DummyUI()
    client = genai.Client(
        api_key=_get_api_key(),
        http_options={"api_version": "v1beta"}
    )

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        output_audio_transcription={},
        input_audio_transcription={},
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        )
    )

    print(f"[TEST] Connecting to Gemini Live ({LIVE_MODEL})...")
    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        print("[TEST] Connected! Sending text command: 'open Notepad'...")
        
        await session.send_client_content(
            turns=[types.Content(role="user", parts=[types.Part.from_text(text="open Notepad")])],
            turn_complete=True
        )

        print("[TEST] Waiting for Gemini Live response...")
        async for response in session.receive():
            print(f"[TEST] Received response chunk: server_content={response.server_content is not None}, tool_call={response.tool_call is not None}")
            
            if response.server_content:
                sc = response.server_content
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.text:
                            print(f"[TEST] Model text: {part.text}")
                if sc.turn_complete:
                    print("[TEST] Turn complete.")

            if response.tool_call:
                print(f"[TEST] Tool call received! function_calls: {response.tool_call.function_calls}")
                for fc in response.tool_call.function_calls:
                    print(f"[TEST] Calling tool: {fc.name} with args: {fc.args} (type={type(fc.args)})")
                    
                    loop = asyncio.get_event_loop()
                    try:
                        args = dict(fc.args or {})
                        print(f"[TEST] args passed to execute_tool: {args}")
                        res = await loop.run_in_executor(
                            None,
                            lambda: default_tool_registry.execute_tool(fc.name, args, player=ui, speak=print)
                        )
                        print(f"[TEST] Tool execution result: {res}")
                        print(f"[TEST] res.message: {res.message}")
                        
                        fr = types.FunctionResponse(
                            id=fc.id, name=fc.name,
                            response={"result": res.message}
                        )
                        print(f"[TEST] Sending function response back to Gemini: {fr}")
                        await session.send_tool_response(function_responses=[fr])
                        print("[TEST] Function response sent successfully!")
                    except Exception as e:
                        print(f"[TEST] CRASH / EXCEPTION CAUGHT: {e}")
                        traceback.print_exc()
                break

if __name__ == "__main__":
    asyncio.run(test_gemini_live())
