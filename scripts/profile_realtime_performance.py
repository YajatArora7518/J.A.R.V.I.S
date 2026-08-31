# scripts/profile_realtime_performance.py
# Comprehensive Real-Time Performance Profiler for JARVIS

import os
import sys
import time
import json
import psutil
import threading
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def profile_jarvis_system() -> Dict[str, Any]:
    print("\n========================================================")
    print("      JARVIS ULTRA-LOW-LATENCY RUNTIME PROFILER")
    print("========================================================\n")

    process = psutil.Process(os.getpid())
    results = {}

    # 1. Cold Startup & ToolRegistry Initialization Latency
    t0 = time.perf_counter()
    import core.register_tools
    t_import = time.perf_counter()
    import core.tool_registry
    tool_count = len(core.tool_registry.default_tool_registry.list_tools())
    t_init = time.perf_counter()

    results["tool_registry_import_ms"] = round((t_import - t0) * 1000, 3)
    results["tool_registry_init_ms"] = round((t_init - t_import) * 1000, 3)
    results["total_startup_tools_ms"] = round((t_init - t0) * 1000, 3)
    results["registered_tools_count"] = tool_count

    # 2. Intent Classification Latency (Cold & Warm)
    from core.intent_router import classify_intent
    t0 = time.perf_counter()
    classify_intent("open chrome")
    t_cold_intent = time.perf_counter()
    results["cold_intent_classification_ms"] = round((t_cold_intent - t0) * 1000, 3)

    t0 = time.perf_counter()
    for _ in range(100):
        classify_intent("open chrome")
        classify_intent("calculate 25 * 37")
        classify_intent("volume up")
        classify_intent("screen dekh")
    results["avg_warm_intent_classification_ms"] = round(((time.perf_counter() - t0) / 400) * 1000, 3)

    # 3. App Resolution Latency (Cold & Warm)
    from actions.universal_app_resolver import default_app_resolver
    t0 = time.perf_counter()
    default_app_resolver.resolve_application("spotify")
    t_cold_app = time.perf_counter()
    results["cold_app_resolve_ms"] = round((t_cold_app - t0) * 1000, 3)

    t0 = time.perf_counter()
    for _ in range(100):
        default_app_resolver.resolve_application("spotify")
    results["avg_warm_app_resolve_ms"] = round(((time.perf_counter() - t0) / 100) * 1000, 3)

    # 4. Safe AST Calculator Latency
    from core.safe_calculator import calculate
    t0 = time.perf_counter()
    for _ in range(100):
        calculate("calculate 25 times 37")
    results["avg_safe_calculator_ms"] = round(((time.perf_counter() - t0) / 100) * 1000, 3)

    # 5. Screen Capture Latency
    from actions.screen_processor import _capture_screenshot
    t0 = time.perf_counter()
    for _ in range(5):
        _capture_screenshot()
    results["avg_screen_capture_ms"] = round(((time.perf_counter() - t0) / 5) * 1000, 3)

    # 6. Memory Load & Prompt Formatting Latency
    from memory.memory_manager import load_memory, format_memory_for_prompt
    t0 = time.perf_counter()
    for _ in range(100):
        m = load_memory()
        format_memory_for_prompt(m)
    results["avg_memory_access_ms"] = round(((time.perf_counter() - t0) / 100) * 1000, 3)

    # 7. End-to-End Deterministic Pipeline Latency
    from core.command_pipeline import process_user_command
    test_commands = [
        "calculate 25 * 37",
        "what is 125 + 378",
        "open settings",
        "volume up",
        "mute mic"
    ]
    cmd_latencies = []
    for cmd in test_commands:
        t_start = time.perf_counter()
        res = process_user_command(cmd, source="voice")
        dt = (time.perf_counter() - t_start) * 1000
        cmd_latencies.append(dt)
        print(f"  [Pipeline Benchmark] '{cmd:<22}' -> {dt:6.2f} ms | Status: {res.get('status', 'OK')}")

    results["avg_deterministic_pipeline_ms"] = round(sum(cmd_latencies) / len(cmd_latencies), 3)

    # 8. Web Search Provider Availability Check Latency
    from actions.web_search_providers import init_search_providers, _PROVIDER_STATUS
    t0 = time.perf_counter()
    init_search_providers()
    results["web_search_provider_lookup_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    results["active_web_provider"] = "DuckDuckGo Fallback" if _PROVIDER_STATUS.get("duckduckgo") else "None"

    # 9. System Telemetry & Resource Consumption
    mem_info = process.memory_info()
    results["process_rss_mb"] = round(mem_info.rss / (1024 * 1024), 2)
    results["thread_count"] = process.num_threads()
    results["cpu_percent"] = process.cpu_percent(interval=0.1)

    # 10. Ollama Local LLM Latency & TTFT Check
    from core.ollama_provider import is_ollama_available, get_ollama_provider
    if is_ollama_available():
        prov = get_ollama_provider()
        results["ollama_status"] = "ONLINE"
        results["ollama_persona_model"] = prov.persona_model
        results["ollama_tool_model"] = prov.tool_model

        # Measure Streaming TTFT
        t0 = time.perf_counter()
        first_token_time = None
        total_tokens = 0
        try:
            for token in prov.chat_stream("Say hello.", system_prompt="You are JARVIS. Reply in 3 words."):
                if first_token_time is None and token.strip():
                    first_token_time = time.perf_counter()
                total_tokens += 1
            t_done = time.perf_counter()
            results["ollama_ttft_ms"] = round((first_token_time - t0) * 1000, 2) if first_token_time else 0.0
            results["ollama_total_stream_ms"] = round((t_done - t0) * 1000, 2)
        except Exception as e:
            results["ollama_stream_error"] = str(e)
    else:
        results["ollama_status"] = "OFFLINE"
        results["ollama_ttft_ms"] = 0.0
        results["ollama_total_stream_ms"] = 0.0

    print("\n--------------------------------------------------------")
    print("           REALTIME PROFILING RESULTS SUMMARY")
    print("--------------------------------------------------------")
    print(f" Tool Registry Import Latency    : {results['tool_registry_import_ms']:8.2f} ms")
    print(f" Tool Registry Init Latency      : {results['tool_registry_init_ms']:8.2f} ms")
    print(f" Total Tool Startup Latency      : {results['total_startup_tools_ms']:8.2f} ms")
    print(f" Registered Tool Count           : {results['registered_tools_count']} tools")
    print(f" Cold Intent Classification      : {results['cold_intent_classification_ms']:8.3f} ms")
    print(f" Warm Intent Classification      : {results['avg_warm_intent_classification_ms']:8.3f} ms")
    print(f" Cold App Resolution             : {results['cold_app_resolve_ms']:8.3f} ms")
    print(f" Warm App Resolution (Cached)    : {results['avg_warm_app_resolve_ms']:8.3f} ms")
    print(f" Safe Calculator AST Evaluation  : {results['avg_safe_calculator_ms']:8.3f} ms")
    print(f" Screen Capture Latency          : {results['avg_screen_capture_ms']:8.2f} ms")
    print(f" Memory Access Latency           : {results['avg_memory_access_ms']:8.3f} ms")
    print(f" Deterministic Pipeline Latency  : {results['avg_deterministic_pipeline_ms']:8.2f} ms")
    print(f" Active Web Search Provider      : {results['active_web_provider']} ({results['web_search_provider_lookup_ms']:.2f} ms)")
    print(f" Process RAM (RSS)               : {results['process_rss_mb']:8.2f} MB")
    print(f" Active Thread Count             : {results['thread_count']}")
    print(f" Ollama Status / Model           : {results['ollama_status']} ({results.get('ollama_persona_model', 'N/A')})")
    print(f" Ollama TTFT (First Token)       : {results['ollama_ttft_ms']:8.2f} ms")
    print(f" Ollama Total Stream Time        : {results['ollama_total_stream_ms']:8.2f} ms")
    print("========================================================\n")

    return results

if __name__ == "__main__":
    profile_jarvis_system()
