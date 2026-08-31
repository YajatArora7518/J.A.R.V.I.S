# scripts/test_ollama.py
# Section 21 — Comprehensive Ollama Local LLM Verification Script for JARVIS

import sys
import os
import time
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def verify_ollama():
    print("=========================================")
    print("       JARVIS OLLAMA VERIFICATION")
    print("=========================================")

    from core.ollama_provider import (
        OllamaProvider,
        find_ollama_executable,
        is_ollama_available,
        get_available_ollama_models,
        check_ollama_health
    )

    # 1. Installation Check
    exe = find_ollama_executable()
    installed_pass = bool(exe) or is_ollama_available()
    print(f"Ollama Installed : {'PASS' if installed_pass else 'FAIL'}")

    # 2. Service Connectivity Check
    reachable_pass = is_ollama_available()
    print(f"Ollama Reachable  : {'PASS' if reachable_pass else 'FAIL'}")

    # 3. Model Discovery
    models = get_available_ollama_models()
    discovery_pass = bool(models)
    print(f"Model Discovery   : {'PASS' if discovery_pass else 'FAIL'} ({len(models)} models found)")
    print(f"Installed Models  : {models}")

    # 4. Instantiate OllamaProvider & Model Selection
    provider = OllamaProvider()
    selected_persona = provider.persona_model
    selected_tool = provider.tool_model
    print(f"Selected Persona Model : {selected_persona}")
    print(f"Selected Tool Model    : {selected_tool}")

    if not reachable_pass or not discovery_pass:
        print("\nSTATUS: DEGRADED (Service or models unavailable)")
        return

    # 5. Basic Chat Test (Persona Model)
    t0 = time.time()
    chat_res = provider.chat("Jarvis, identify yourself briefly.", model=selected_persona)
    chat_pass = chat_res.get("success", False)
    total_ms = chat_res.get("total_ms", int((time.time() - t0) * 1000))
    print(f"Basic Chat        : {'PASS' if chat_pass else 'FAIL'}")
    print(f"Chat Response     : {chat_res.get('text', '')[:100]}...")

    # 6. Streaming Test (Persona Model)
    t0_stream = time.time()
    stream_chunks = []
    first_token_ms = 0
    try:
        for chunk in provider.chat_stream("Say hi", model=selected_persona):
            if not stream_chunks and chunk:
                first_token_ms = int((time.time() - t0_stream) * 1000)
            stream_chunks.append(chunk)
        stream_pass = bool(stream_chunks)
    except Exception:
        stream_pass = False
    print(f"Streaming         : {'PASS' if stream_pass else 'FAIL'}")
    print(f"First Token Latency: {first_token_ms} ms")
    print(f"Total Latency     : {total_ms} ms")

    # 7. Structured Output Test (Tool Model)
    allowed_tools = ["open_app", "computer_settings", "system_info", "battery_info"]
    struct_res = provider.generate_structured_action("Open calculator", allowed_tools=allowed_tools, model=selected_tool)
    struct_pass = struct_res.get("success", False)
    print(f"Structured Output : {'PASS' if struct_pass else 'FAIL'}")
    if struct_pass:
        print(f"Action Proposal   : {struct_res.get('action_proposal')}")

    all_ok = installed_pass and reachable_pass and discovery_pass and chat_pass and struct_pass
    print("=========================================")
    print(f"STATUS: {'READY' if all_ok else 'DEGRADED'}")
    print("=========================================\n")

if __name__ == "__main__":
    verify_ollama()
