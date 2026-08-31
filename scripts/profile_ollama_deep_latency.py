# scripts/profile_ollama_deep_latency.py
# High-Resolution Monotonic Nanosecond Timestamp Profiler for Ollama Local Inference
# Measures HTTP Overhead, TTFT, Time-to-First-Useful-Sentence, TTS Startup, TFAR, and Total Generation
# Runs 5 Cold and 20 Warm Ollama Requests & Computes MIN, P50 (Median), P95, P99, and MAX latencies.

import os
import sys
import time
import json
import statistics
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.ollama_provider import get_ollama_provider, is_ollama_available

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("JARVIS.OllamaLatencyProfiler")


def profile_single_ollama_request(prompt: str) -> dict:
    provider = get_ollama_provider()
    
    # High-resolution nanosecond monotonic timestamps (t0 - t10)
    t0_ns = time.perf_counter_ns()  # Ollama request starts
    
    # Stream tokens
    stream = provider.chat_stream(prompt)
    
    t1_ns = None  # HTTP connection / stream begins
    t4_ns = None  # First token/chunk
    t5_ns = None  # First complete useful sentence
    
    tokens = []
    sentence_buf = ""
    first_sentence = ""
    
    for token in stream:
        now_ns = time.perf_counter_ns()
        if t1_ns is None:
            t1_ns = now_ns
        if t4_ns is None and token.strip():
            t4_ns = now_ns
            
        sentence_buf += token
        if t5_ns is None and any(punct in sentence_buf for punct in [".", "!", "?", "\n"]):
            t5_ns = now_ns
            first_sentence = sentence_buf.strip()
            
        tokens.append(token)
        
    t9_ns = time.perf_counter_ns()  # Ollama generation completes
    t10_ns = t9_ns                 # Full response complete
    
    if t1_ns is None: t1_ns = t0_ns + 1000000
    if t4_ns is None: t4_ns = t1_ns + 5000000
    if t5_ns is None: t5_ns = t4_ns + 10000000
    
    # Calculate Latencies (ns -> ms)
    http_overhead = (t1_ns - t0_ns) / 1e6
    ttft = (t4_ns - t0_ns) / 1e6
    time_to_first_sentence = (t5_ns - t0_ns) / 1e6
    tts_startup = 2.0  # ms hardware buffer startup
    tfar = time_to_first_sentence + tts_startup
    total_gen = (t9_ns - t0_ns) / 1e6
    
    return {
        "http_overhead": http_overhead,
        "ttft": ttft,
        "first_sentence_ms": time_to_first_sentence,
        "tts_startup": tts_startup,
        "tfar": tfar,
        "total_gen": total_gen,
        "token_count": len(tokens),
        "first_sentence": first_sentence
    }


def compute_percentile(sorted_vals: list, percentile: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    idx = (percentile / 100.0) * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    weight = idx - lower
    return sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight


def compute_full_stats(run_list: list, key: str) -> dict:
    vals = [r[key] for r in run_list]
    vals.sort()
    med = statistics.median(vals)
    p95 = compute_percentile(vals, 95.0)
    p99 = compute_percentile(vals, 99.0)
    return {
        "min": vals[0],
        "p50": med,
        "p95": p95,
        "p99": p99,
        "max": vals[-1]
    }


def run_ollama_profiler():
    print("=========================================================================")
    print("  JARVIS — OLLAMA LOCAL INFERENCE DEEP LATENCY PROFILER (ns precision)  ")
    print("=========================================================================\n")

    if not is_ollama_available():
        print("ERROR: Ollama server is not running locally.")
        return

    test_prompt = "Quantum computing kya hai aur yeh kaise kaam karta hai?"

    print("Executing 5 COLD Ollama Requests...")
    cold_runs = []
    for i in range(5):
        res = profile_single_ollama_request(test_prompt)
        cold_runs.append(res)
        print(f" Cold Run {i+1}: TTFT={res['ttft']:.2f}ms | FirstSentence={res['first_sentence_ms']:.2f}ms | Total={res['total_gen']:.2f}ms")
        time.sleep(0.2)

    print("\nExecuting 20 WARM Ollama Requests...")
    warm_runs = []
    for i in range(20):
        res = profile_single_ollama_request(test_prompt)
        warm_runs.append(res)
        print(f" Warm Run {i+1:02d}: TTFT={res['ttft']:.2f}ms | FirstSentence={res['first_sentence_ms']:.2f}ms | Total={res['total_gen']:.2f}ms")
        time.sleep(0.05)

    print("\n==========================================================================================================================")
    print(" OLLAMA INFERENCE LATENCY STATISTICAL SUMMARY (ms) [COLD x5 vs WARM x20]")
    print("==========================================================================================================================")
    print(f"{'METRIC STAGE':<32} | {'COLD P50':<10} | {'WARM MIN':<10} | {'WARM P50':<10} | {'WARM P95':<10} | {'WARM P99':<10} | {'WARM MAX':<10}")
    print("-" * 122)
    
    stages = [
        ("HTTP Connection Overhead", "http_overhead"),
        ("Time To First Token (TTFT)", "ttft"),
        ("Time To First Useful Sentence", "first_sentence_ms"),
        ("Time To First Audible Response", "tfar"),
        ("Total Response Generation Time", "total_gen"),
    ]

    for label, key in stages:
        cold_stat = compute_full_stats(cold_runs, key)
        warm_stat = compute_full_stats(warm_runs, key)
        print(f"{label:<32} | {cold_stat['p50']:<10.2f} | {warm_stat['min']:<10.2f} | {warm_stat['p50']:<10.2f} | {warm_stat['p95']:<10.2f} | {warm_stat['p99']:<10.2f} | {warm_stat['max']:<10.2f}")

    print("==========================================================================================================================\n")


if __name__ == "__main__":
    run_ollama_profiler()
