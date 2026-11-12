# scripts/test_startup_latency.py
# Startup Latency Profiler for J.A.R.V.I.S Subsystems
# Measures individual subsystem initialization times to isolate startup overhead.

import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def profile_startup_stages():
    print("=" * 65)
    print("      J.A.R.V.I.S — SUBSYSTEM STARTUP LATENCY PROFILER           ")
    print("=" * 65)

    stages = {}
    t_global_start = time.perf_counter()

    # 1. Tool Registry & Initialization
    t0 = time.perf_counter()
    from core.register_tools import initialize_all_tools
    from core.tool_registry import default_tool_registry
    initialize_all_tools()
    tool_count = len(default_tool_registry.list_tools())
    stages["tool_registry"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Tool Registry (62 tools) : {stages['tool_registry']:.2f} ms ({tool_count} registered)")

    # 2. Security Manager
    t0 = time.perf_counter()
    from core.security import default_security_manager
    sec_risk = default_security_manager.classify_risk("open_app", {})
    stages["security_manager"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Security Manager         : {stages['security_manager']:.2f} ms (Default App Risk: {sec_risk.value})")

    # 3. Memory Subsystem
    t0 = time.perf_counter()
    from memory.memory_manager import retrieve_relevant_memories
    mems = retrieve_relevant_memories("warmup", limit=1)
    stages["memory_subsystem"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Memory Subsystem         : {stages['memory_subsystem']:.2f} ms")

    # 4. Context Engine & Retriever
    t0 = time.perf_counter()
    from core.context_retriever import default_context_retriever
    ctx = default_context_retriever.retrieve_context("warmup")
    stages["context_engine"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Context Engine           : {stages['context_engine']:.2f} ms")

    # 5. Task Planner
    t0 = time.perf_counter()
    from agent.task_planner import default_task_planner
    stages["task_planner"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Task Planner             : {stages['task_planner']:.2f} ms")

    # 6. Universal TTS Engine
    t0 = time.perf_counter()
    from core.tts_engine import get_tts_engine
    tts = get_tts_engine()
    stages["tts_engine"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Universal TTS Engine     : {stages['tts_engine']:.2f} ms")

    # 7. Local Ollama Provider Check
    t0 = time.perf_counter()
    from core.ollama_provider import is_ollama_available
    ollama_ok = is_ollama_available()
    stages["ollama_check"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Ollama Server Check      : {stages['ollama_check']:.2f} ms (Online: {ollama_ok})")

    # 8. Runtime Supervisor
    t0 = time.perf_counter()
    from core.runtime_supervisor import get_runtime_supervisor
    supervisor = get_runtime_supervisor()
    stages["runtime_supervisor"] = (time.perf_counter() - t0) * 1000.0
    print(f"[-] Runtime Supervisor       : {stages['runtime_supervisor']:.2f} ms")

    t_total = (time.perf_counter() - t_global_start) * 1000.0
    print("-" * 65)
    print(f"[+] Total Subsystems Warmup  : {t_total:.2f} ms")
    print("=" * 65)
    return stages


if __name__ == "__main__":
    profile_startup_stages()
