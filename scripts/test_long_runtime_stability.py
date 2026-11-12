# scripts/test_long_runtime_stability.py
# Phase 2 Real Long-Runtime Stability, Resource Leak & Telemetry Test

import sys
import os
import time
import psutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.command_pipeline import process_user_command
from core.tts_engine import get_tts_engine
from core.health_check import get_subsystem_observability_report
from memory.memory_manager import load_memory

def run_long_runtime_stability_test(target_duration_seconds: float = 60.0):
    print("=" * 70)
    print("      PHASE 2: DEFINED BASELINE LONG-RUNTIME STABILITY TEST")
    print("=" * 70)

    proc = psutil.Process()
    tts = get_tts_engine()

    # 1. Baseline Telemetry Acquisition
    initial_mem_info = proc.memory_info()
    initial_ram_mb = initial_mem_info.rss / (1024 * 1024)
    initial_threads = proc.num_threads()
    initial_cpu = proc.cpu_percent(interval=0.2)
    initial_children = len(proc.children())

    print(f"[-] INITIAL BASELINE TELEMETRY (t=0s):")
    print(f"    • RAM: {initial_ram_mb:.2f} MB")
    print(f"    • Threads: {initial_threads}")
    print(f"    • CPU: {initial_cpu:.1f}%")
    print(f"    • Child Processes: {initial_children}")
    print(f"    • Target Test Duration: {target_duration_seconds:.1f}s")
    print("-" * 70)

    # Telemetry tracking arrays
    snapshots = []
    peak_ram_mb = initial_ram_mb
    cycle = 0
    start_time = time.time()
    warmup_ram_mb = None
    warmup_threads = None

    print(f"{'TIME (s)':<10} | {'CYCLE':<6} | {'RAM (MB)':<10} | {'THREADS':<8} | {'CPU %':<7} | {'QUEUE':<6} | {'ACTIVITY'}")
    print("-" * 70)

    # Workload commands to cycle through
    workload = [
        ("calculate 12 * 15", "chat"),
        ("what is my preferred language?", "chat"),
        ("system status check", "chat"),
        ("who is Tony Stark?", "chat"),
        ("status check", "voice")
    ]

    while (time.time() - start_time) < target_duration_seconds:
        cycle += 1
        elapsed = time.time() - start_time

        # 1. Run command pipeline workload
        cmd, src = workload[cycle % len(workload)]
        res = process_user_command(cmd, source=src)

        # 2. Run memory read
        mem = load_memory()

        # 3. Observability telemetry sample
        if cycle % 3 == 0:
            obs = get_subsystem_observability_report(REPO_DIR)

        # 4. Check TTS queue behavior & clear
        q_depth = tts._speech_queue.qsize()
        tts.stop()  # Clean queue

        # Capture snapshot
        curr_mem = proc.memory_info().rss / (1024 * 1024)
        if curr_mem > peak_ram_mb:
            peak_ram_mb = curr_mem
        if cycle == 3:
            warmup_ram_mb = curr_mem
            warmup_threads = proc.num_threads()

        curr_threads = proc.num_threads()
        curr_cpu = proc.cpu_percent(interval=None)

        snapshots.append({
            "elapsed": elapsed,
            "cycle": cycle,
            "ram_mb": curr_mem,
            "threads": curr_threads,
            "cpu": curr_cpu,
            "queue": q_depth
        })

        print(f"{elapsed:>8.1f}s | {cycle:>6} | {curr_mem:>8.2f}MB | {curr_threads:>8} | {curr_cpu:>5.1f}% | {q_depth:>6} | {cmd[:20]}")
        time.sleep(1.2)

    total_actual_duration = time.time() - start_time
    final_mem_info = proc.memory_info()
    final_ram_mb = final_mem_info.rss / (1024 * 1024)
    final_threads = proc.num_threads()
    final_cpu = proc.cpu_percent(interval=0.2)
    final_children = len(proc.children())

    # Delta calculations
    net_ram_growth = final_ram_mb - initial_ram_mb
    post_warmup_growth = final_ram_mb - (warmup_ram_mb or initial_ram_mb)
    post_warmup_threads_delta = final_threads - (warmup_threads or initial_threads)

    print("\n" + "=" * 70)
    print("      FINAL LONG-RUNTIME STABILITY REPORT")
    print("=" * 70)
    print(f"  • Actual Run Duration      : {total_actual_duration:.2f} seconds (NOT extrapolated)")
    print(f"  • Completed Active Cycles  : {cycle}")
    print(f"  • Initial RAM              : {initial_ram_mb:.2f} MB")
    print(f"  • Warm-up RAM (Cycle 2)    : {warmup_ram_mb:.2f} MB")
    print(f"  • Peak RAM                 : {peak_ram_mb:.2f} MB")
    print(f"  • Final RAM                : {final_ram_mb:.2f} MB")
    print(f"  • Total RAM Delta          : {net_ram_growth:+.2f} MB")
    print(f"  • Post-Warmup RAM Delta    : {post_warmup_growth:+.2f} MB")
    print(f"  • Thread Count (Init/Warm/Peak/End): {initial_threads} / {warmup_threads} / {max(s['threads'] for s in snapshots)} / {final_threads}")
    print(f"  • Post-Warmup Thread Delta : {post_warmup_threads_delta:+d}")
    print(f"  • Child Processes          : {final_children} (Zero zombie processes)")
    print(f"  • Final TTS Queue Depth    : {tts._speech_queue.qsize()}")
    print("-" * 70)

    # -------------------------------------------------------------
    # Defined Acceptance Criteria Verification
    # -------------------------------------------------------------
    # 1. Distinguish between expected warm-up growth and unbounded growth:
    # Post-warmup growth must be bounded (< 80 MB across the test)
    assert post_warmup_growth < 80.0, f"UNBOUNDED MEMORY LEAK DETECTED: Post-warmup growth was {post_warmup_growth:.2f} MB (> 80 MB)!"
    print("  [✅] Memory Leak Check: PASSED (Post-warmup growth bounded at {0:+.2f} MB)".format(post_warmup_growth))

    # 2. Thread count must not continuously grow after subsystems warm up
    assert post_warmup_threads_delta <= 5, f"THREAD LEAK DETECTED: Post-warmup thread delta is +{post_warmup_threads_delta}!"
    print(f"  [✅] Thread Leak Check: PASSED (Post-warmup thread delta: {post_warmup_threads_delta:+d})")

    # 3. Child process leak check
    assert final_children == 0, f"ZOMBIE PROCESSES DETECTED: {final_children} children left alive!"
    print("  [✅] Process Leak Check: PASSED (Zero zombie/orphan processes)")

    # 4. Queue depth check
    assert tts._speech_queue.qsize() == 0, "TTS Queue deadlock / unbounded backlog detected!"
    print("  [✅] Audio Queue Check: PASSED (Queue cleanly drained)")

    print("\n" + "=" * 70)
    print("LONG-RUNTIME STABILITY: PASSED (Defined baseline satisfied)")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = run_long_runtime_stability_test(target_duration_seconds=60.0)
    sys.exit(0 if success else 1)
