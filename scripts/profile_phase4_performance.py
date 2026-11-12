# scripts/profile_phase4_performance.py
# Performance Profiler for Phase 4 Subsystems (Latency, Memory, CPU, Thread Telemetry)

import time
import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from core.ollama_provider import is_ollama_available, generate_ollama_response
from agent.task_planner import default_task_planner
from core.context_retriever import default_context_retriever
from memory.memory_manager import retrieve_relevant_memories
from core.intent_router import classify_intent
from actions.screen_processor import analyze_screen_vision


def profile_all():
    print("=" * 60)
    print("   J.A.R.V.I.S PHASE 4 — PERFORMANCE BENCHMARK PROFILE")
    print("=" * 60)

    # 1. Memory retrieval latency
    t0 = time.perf_counter()
    mems = retrieve_relevant_memories("favorite editor and python project", limit=5)
    t_mem = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Memory Retrieval Latency  : {t_mem:.2f} ms ({len(mems)} items retrieved)")

    # 2. Context retrieval latency
    t0 = time.perf_counter()
    ctx = default_context_retriever.retrieve_context("What build errors are in the project?")
    t_ctx = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Context Retrieval Latency : {t_ctx:.2f} ms (Domain: {ctx.get('domain')})")

    # 3. Intent & Tool routing latency
    t0 = time.perf_counter()
    routing = classify_intent("Antigravity kholo, mera JARVIS project open karo aur build error check karo.")
    t_route = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Intent Routing Latency    : {t_route:.2f} ms (Intent: {routing.get('intent')})")

    # 4. Task Planner generation latency
    t0 = time.perf_counter()
    plan = default_task_planner.create_plan("Open Notepad and write my notes")
    t_plan = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Planner Generation Latency: {t_plan:.2f} ms ({len(plan.steps)} steps planned)")

    # 5. Screen analysis latency
    t0 = time.perf_counter()
    scr = analyze_screen_vision("Check current foreground window")
    t_scr = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Screen Analysis Latency   : {t_scr:.2f} ms (Window: '{scr.get('active_window', '')}')")

    # 6. Ollama Local LLM inference latency
    t_ollama = 0.0
    if is_ollama_available():
        t0 = time.perf_counter()
        o_res = generate_ollama_response("Reply with one word: READY", timeout=15.0)
        t_ollama = (time.perf_counter() - t0) * 1000.0
        print(f"[-] Local Ollama Latency      : {t_ollama:.2f} ms (Reply: '{o_res.get('text', '').strip()[:30]}')")
    else:
        print(f"[-] Local Ollama Latency      : OFFLINE")

    # 7. System Resource Telemetry
    if _HAS_PSUTIL:
        proc = psutil.Process(os.getpid())
        ram_mb = proc.memory_info().rss / (1024 * 1024)
        threads = proc.num_threads()
        cpu_pct = psutil.cpu_percent(interval=0.5)
        sys_ram_pct = psutil.virtual_memory().percent
        print(f"[-] Process RAM Usage         : {ram_mb:.2f} MB")
        print(f"[-] Process Threads           : {threads}")
        print(f"[-] System CPU Usage          : {cpu_pct:.1f}%")
        print(f"[-] System RAM Usage          : {sys_ram_pct:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    profile_all()
