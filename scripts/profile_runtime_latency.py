# scripts/profile_runtime_latency.py
# Real Runtime Latency Profiler for JARVIS

import os
import sys
import time
import json
import logging
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.WARNING)

def measure_runtime_latency():
    metrics = {}
    print("\n========================================================")
    print("        JARVIS REAL RUNTIME LATENCY PROFILER")
    print("========================================================\n")

    # 1. Startup Latency: Import Core Pipeline & Tool Registry
    t0 = time.perf_counter()
    import core.register_tools
    t_tools_import = time.perf_counter()
    metrics["tool_registry_import_ms"] = (t_tools_import - t0) * 1000

    from core.tool_registry import default_tool_registry
    t_tools_init0 = time.perf_counter()
    core.register_tools.initialize_all_tools()
    t_tools_init1 = time.perf_counter()
    metrics["tool_registry_init_ms"] = (t_tools_init1 - t_tools_init0) * 1000
    metrics["total_startup_tools_ms"] = (t_tools_init1 - t0) * 1000
    metrics["registered_tool_count"] = len(default_tool_registry.list_tools())

    # 2. Voice Pipeline / Intent Router Initialization Latency
    from core.intent_router import classify_intent
    t0 = time.perf_counter()
    for _ in range(100):
        classify_intent("open chrome")
    metrics["avg_intent_classification_ms"] = ((time.perf_counter() - t0) / 100) * 1000

    # 3. Intent -> Tool Selection & App Resolution Latency
    from actions.universal_app_resolver import default_app_resolver
    t0 = time.perf_counter()
    for _ in range(100):
        default_app_resolver.resolve_application("chrome")
    metrics["avg_app_resolution_ms"] = ((time.perf_counter() - t0) / 100) * 1000

    # 4. Safe AST Calculator Computation Latency
    from core.safe_calculator import calculate
    t0 = time.perf_counter()
    for _ in range(100):
        calculate("calculate 25 times 37")
    metrics["avg_safe_calculator_ms"] = ((time.perf_counter() - t0) / 100) * 1000

    # 5. Screen Capture Latency
    from actions.screen_processor import _capture_screenshot
    t0 = time.perf_counter()
    for _ in range(5):
        _capture_screenshot()
    metrics["avg_screen_capture_ms"] = ((time.perf_counter() - t0) / 5) * 1000

    # 6. Memory Load & Format Latency
    from memory.memory_manager import load_memory, format_memory_for_prompt
    t0 = time.perf_counter()
    for _ in range(100):
        m = load_memory()
        format_memory_for_prompt(m)
    metrics["avg_memory_load_format_ms"] = ((time.perf_counter() - t0) / 100) * 1000

    # 7. End-to-End Deterministic Command Pipeline Latency
    from core.command_pipeline import process_user_command

    deterministic_commands = [
        "calculate 25 times 37",
        "what is 125 + 378",
        "open settings",
        "volume up",
        "mute mic"
    ]

    pipeline_times = []
    for cmd in deterministic_commands:
        t_start = time.perf_counter()
        res = process_user_command(cmd, source="voice")
        dt = (time.perf_counter() - t_start) * 1000
        pipeline_times.append(dt)
        print(f"  [Cmd] '{cmd:<24}' -> Status: {res.get('status', 'OK'):<15} Latency: {dt:6.2f} ms")

    metrics["avg_deterministic_pipeline_ms"] = sum(pipeline_times) / len(pipeline_times)

    # 8. Ollama Local LLM Latency Check (if available)
    from core.ollama_provider import is_ollama_available, get_ollama_provider
    if is_ollama_available():
        provider = get_ollama_provider()
        t0 = time.perf_counter()
        res = provider.chat("Say 'Hello Boss' in 3 words.", system_prompt="You are JARVIS.")
        metrics["ollama_generation_ms"] = (time.perf_counter() - t0) * 1000
        metrics["ollama_status"] = "ONLINE"
    else:
        metrics["ollama_generation_ms"] = 0.0
        metrics["ollama_status"] = "OFFLINE"

    # 9. Print Comprehensive Summary Table
    print("\n--------------------------------------------------------")
    print("             RUNTIME LATENCY SUMMARY")
    print("--------------------------------------------------------")
    print(f" Tool Registry Import Time       : {metrics['tool_registry_import_ms']:8.2f} ms")
    print(f" Tool Registry Initialize Time   : {metrics['tool_registry_init_ms']:8.2f} ms")
    print(f" Total Tool Startup Latency      : {metrics['total_startup_tools_ms']:8.2f} ms")
    print(f" Registered Tool Count           : {metrics['registered_tool_count']} tools")
    print(f" Intent Classification Latency   : {metrics['avg_intent_classification_ms']:8.3f} ms")
    print(f" App Resolution Latency          : {metrics['avg_app_resolution_ms']:8.3f} ms")
    print(f" Safe Calculation Latency        : {metrics['avg_safe_calculator_ms']:8.3f} ms")
    print(f" Memory Load & Format Latency    : {metrics['avg_memory_load_format_ms']:8.3f} ms")
    print(f" Screen Capture Latency          : {metrics['avg_screen_capture_ms']:8.2f} ms")
    print(f" Deterministic Pipeline Latency  : {metrics['avg_deterministic_pipeline_ms']:8.2f} ms")
    print(f" Ollama Status / Latency         : {metrics['ollama_status']} ({metrics['ollama_generation_ms']:8.2f} ms)")
    print("========================================================\n")

    return metrics

if __name__ == "__main__":
    measure_runtime_latency()
