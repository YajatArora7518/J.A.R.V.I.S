# scripts/profile_benchmarks.py
# Comprehensive Performance Benchmark Suite for JARVIS

import time
import timeit
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def benchmark_suite():
    results = {}

    # 1. Imports Benchmark
    t0 = time.perf_counter()
    import core.intent_router
    results["import_intent_router_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    import core.safe_calculator
    results["import_safe_calculator_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    import core.command_pipeline
    results["import_command_pipeline_ms"] = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    import core.register_tools
    results["import_register_tools_ms"] = (time.perf_counter() - t0) * 1000

    # 2. Fast Intent Classification Latency (500 iterations)
    from core.intent_router import classify_intent

    test_queries = [
        "open chrome",
        "open whatsapp",
        "calculate 25 times 37",
        "what is 125 + 378",
        "volume up",
        "mute mic",
        "screen dekh",
        "tell me a story about robots"
    ]

    intent_latencies = []
    for q in test_queries:
        t0 = time.perf_counter()
        for _ in range(500):
            classify_intent(q)
        dt = ((time.perf_counter() - t0) / 500) * 1000  # ms per call
        intent_latencies.append(dt)
    results["avg_intent_classification_ms"] = sum(intent_latencies) / len(intent_latencies)

    # 3. Safe Calculator Computation Latency (1000 iterations)
    from core.safe_calculator import calculate

    math_queries = ["25 * 37", "984 / 12", "2 ** 10", "sqrt(144)", "17% of 850", "125 + 378"]
    calc_latencies = []
    for expr in math_queries:
        t0 = time.perf_counter()
        for _ in range(500):
            calculate(expr)
        dt = ((time.perf_counter() - t0) / 500) * 1000
        calc_latencies.append(dt)
    results["avg_safe_calculator_ms"] = sum(calc_latencies) / len(calc_latencies)

    # 4. Universal App Resolver Lookup Latency
    from actions.universal_app_resolver import default_app_resolver
    t0 = time.perf_counter()
    for _ in range(100):
        default_app_resolver.resolve_application("chrome")
        default_app_resolver.resolve_application("whatsapp")
        default_app_resolver.resolve_application("settings")
    results["avg_app_resolve_ms"] = ((time.perf_counter() - t0) / 300) * 1000

    # 5. Direct Command Pipeline Latency (End-to-End Deterministic)
    from core.command_pipeline import process_user_command

    pipeline_queries = [
        "calculate 25 times 37",
        "what is 125 + 378",
        "open settings"
    ]
    pipe_latencies = []
    for pq in pipeline_queries:
        t0 = time.perf_counter()
        for _ in range(20):
            process_user_command(pq, source="voice")
        dt = ((time.perf_counter() - t0) / 20) * 1000
        pipe_latencies.append(dt)
    results["avg_pipeline_deterministic_dispatch_ms"] = sum(pipe_latencies) / len(pipe_latencies)

    # 6. Screen Capture Benchmark
    from actions.screen_processor import _capture_screenshot
    t0 = time.perf_counter()
    for _ in range(5):
        _capture_screenshot()
    results["avg_screen_capture_ms"] = ((time.perf_counter() - t0) / 5) * 1000

    # 7. Memory Manager Read/Format Latency
    from memory.memory_manager import load_memory, format_memory_for_prompt
    t0 = time.perf_counter()
    for _ in range(100):
        mem = load_memory()
        format_memory_for_prompt(mem)
    results["avg_memory_load_format_ms"] = ((time.perf_counter() - t0) / 100) * 1000

    # Output Benchmark Summary
    print("\n========================================================")
    print("           JARVIS PERFORMANCE BENCHMARK")
    print("========================================================")
    for k, v in results.items():
        print(f" {k:<42}: {v:8.3f} ms")
    print("========================================================\n")

    return results

if __name__ == "__main__":
    benchmark_suite()
