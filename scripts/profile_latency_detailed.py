# scripts/profile_latency_detailed.py
# High-Resolution Monotonic Latency Benchmark Suite for JARVIS Phase 5
# Profiles:
# 1. AI (Ollama Local Inference: Request prep, Connection, TTFT, Total generation)
# 2. Screen Analysis (Capture, Image Prep, Model Query, Result Parsing)
# 3. Voice & Pipeline (Command classification, Intent routing, End-to-end execution)
# 4. TTS (Queue insertion, Worker pickup, Audio start, Barge-in)
# 5. Deterministic Tools (App resolution, Computation, Diagnostics)
# Computes Median (P50), P95, and Maximum latencies across repeated runs.

import os
import sys
import time
import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from core.ollama_provider import get_ollama_provider, is_ollama_available, generate_ollama_response
from actions.screen_processor import analyze_screen_vision
from core.tts_engine import get_tts_engine
from core.command_pipeline import process_user_command
from core.intent_router import classify_intent
from actions.app_registry import resolve_app


def compute_percentile(sorted_vals: List[float], percentile: float) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    idx = (percentile / 100.0) * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    weight = idx - lower
    return sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight


def compute_stats(vals: List[float]) -> Dict[str, float]:
    if not vals:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    s = sorted(vals)
    return {
        "min": round(s[0], 2),
        "p50": round(statistics.median(s), 2),
        "p95": round(compute_percentile(s, 95.0), 2),
        "max": round(s[-1], 2),
        "mean": round(statistics.mean(s), 2)
    }


def profile_ollama(runs: int = 5) -> Dict[str, Any]:
    print("\n[PROFILER] 1. Profiling Ollama Local Inference...")
    if not is_ollama_available():
        print("  ⚠️ Ollama is offline. Skipping live Ollama benchmark.")
        return {"status": "OFFLINE"}

    provider = get_ollama_provider()
    total_latencies = []
    prep_latencies = []
    ttft_latencies = []

    prompt = "Give a 1-sentence status report on reactor core."

    for i in range(runs):
        t0 = time.perf_counter()
        # Test stream for TTFT
        stream = provider.chat_stream(prompt)
        first_token_time = None
        tokens = []
        t_prep_done = time.perf_counter()
        prep_latencies.append((t_prep_done - t0) * 1000.0)

        for tok in stream:
            if first_token_time is None and tok.strip():
                first_token_time = time.perf_counter()
            tokens.append(tok)
        t_end = time.perf_counter()

        ttft = ((first_token_time - t0) * 1000.0) if first_token_time else 0.0
        tot = (t_end - t0) * 1000.0

        ttft_latencies.append(ttft)
        total_latencies.append(tot)
        print(f"  Run {i+1}: Total={tot:.2f}ms | TTFT={ttft:.2f}ms | Tokens={len(tokens)}")

    return {
        "runs": runs,
        "total": compute_stats(total_latencies),
        "ttft": compute_stats(ttft_latencies),
        "prep": compute_stats(prep_latencies)
    }


def profile_screen_analysis(runs: int = 3) -> Dict[str, Any]:
    print("\n[PROFILER] 2. Profiling Screen Analysis Pipeline...")
    total_latencies = []

    for i in range(runs):
        t0 = time.perf_counter()
        res = analyze_screen_vision(user_query="Inspect active screen")
        dur = (time.perf_counter() - t0) * 1000.0
        total_latencies.append(dur)
        win = res.get("active_window", "")
        success = res.get("success", False)
        print(f"  Run {i+1}: Latency={dur:.2f}ms | Success={success} | Window='{win}'")

    return {
        "runs": runs,
        "latency": compute_stats(total_latencies)
    }


def profile_tts(runs: int = 5) -> Dict[str, Any]:
    print("\n[PROFILER] 3. Profiling TTS Latency & Barge-In...")
    engine = get_tts_engine()
    queue_latencies = []
    bargein_latencies = []

    for i in range(runs):
        # Measure queue insertion
        t0 = time.perf_counter()
        engine.speak("System test utterance.", interrupt=True)
        t_queue = (time.perf_counter() - t0) * 1000.0
        queue_latencies.append(t_queue)

        time.sleep(0.05)  # allow brief speech initiation

        # Measure barge-in stop latency
        t0 = time.perf_counter()
        engine.barge_in_stop()
        t_stop = (time.perf_counter() - t0) * 1000.0
        bargein_latencies.append(t_stop)

        print(f"  Run {i+1}: QueueInsert={t_queue:.3f}ms | BargeInStop={t_stop:.3f}ms")

    return {
        "runs": runs,
        "queue_insert": compute_stats(queue_latencies),
        "barge_in_stop": compute_stats(bargein_latencies)
    }


def profile_deterministic_commands(runs: int = 5) -> Dict[str, Any]:
    print("\n[PROFILER] 4. Profiling Deterministic Command Fast Paths...")
    test_commands = [
        ("App Launch", "Open Notepad"),
        ("App Launch", "Open Calculator"),
        ("Computation", "Calculate 25 * 40 + 150"),
        ("Diagnostics", "Jarvis status"),
        ("Intent Routing", "Volume badhao"),
        ("Pronoun Resolution", "Isko open karo"),
        ("Barge-in Keyword", "Chup")
    ]

    results = {}
    for category, cmd in test_commands:
        latencies = []
        for _ in range(runs):
            t0 = time.perf_counter()
            res = process_user_command(cmd, source="voice")
            dur = (time.perf_counter() - t0) * 1000.0
            latencies.append(dur)
        stats = compute_stats(latencies)
        results[cmd] = stats
        print(f"  '{cmd}': P50={stats['p50']:.2f}ms | P95={stats['p95']:.2f}ms | Max={stats['max']:.2f}ms")

    return results


def profile_system_resources() -> Dict[str, Any]:
    print("\n[PROFILER] 5. Capturing System Resource Utilization...")
    if not _HAS_PSUTIL:
        return {"status": "PSUTIL_NOT_AVAILABLE"}

    proc = psutil.Process(os.getpid())
    ram_mb = proc.memory_info().rss / (1024 * 1024)
    threads = proc.num_threads()
    cpu_pct = psutil.cpu_percent(interval=0.5)

    res = {
        "process_ram_mb": round(ram_mb, 2),
        "process_threads": threads,
        "system_cpu_pct": round(cpu_pct, 1),
        "system_ram_pct": round(psutil.virtual_memory().percent, 1)
    }
    print(f"  RAM: {res['process_ram_mb']} MB | Threads: {res['process_threads']} | CPU: {res['system_cpu_pct']}%")
    return res


def run_full_detailed_profile(output_json: str = "phase5_baseline_profile.json") -> Dict[str, Any]:
    print("=" * 70)
    print("      J.A.R.V.I.S PHASE 5 — DETAILED LATENCY & PERFORMANCE PROFILER      ")
    print("=" * 70)

    profile_data = {
        "timestamp": time.time(),
        "ollama": profile_ollama(runs=5),
        "screen": profile_screen_analysis(runs=3),
        "tts": profile_tts(runs=5),
        "deterministic": profile_deterministic_commands(runs=5),
        "resources": profile_system_resources()
    }

    out_path = Path(BASE_DIR) / output_json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)
    print(f"\n[PROFILER] [OK] Profile data saved to {out_path.name}")
    print("=" * 70)
    return profile_data


if __name__ == "__main__":
    run_full_detailed_profile()
