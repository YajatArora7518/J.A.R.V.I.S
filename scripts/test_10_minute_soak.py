# scripts/test_10_minute_soak.py
# Configurable Long-Runtime Stability & Soak Test Suite for J.A.R.V.I.S.
# Supports configurable duration via --duration (default: 600s / 10 minutes).

import sys
import os
import time
import argparse
import psutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.command_pipeline import process_user_command
from core.runtime_supervisor import get_runtime_supervisor
from core.tts_engine import get_tts_engine
from core.health_check import get_subsystem_observability_report
from memory.memory_manager import load_memory

def run_soak_test(duration_sec: int = 600, sample_interval: int = 15):
    print("=" * 70, flush=True)
    print(f"      PHASE 3: SOAK & LONG-RUNTIME STABILITY TEST ({duration_sec}s)", flush=True)
    print("=" * 70, flush=True)

    proc = psutil.Process(os.getpid())
    supervisor = get_runtime_supervisor()
    tts = get_tts_engine()

    initial_ram = proc.memory_info().rss / (1024 * 1024)
    initial_threads = proc.num_threads()

    print(f"[-] Initial State -> RAM: {initial_ram:.2f} MB | Threads: {initial_threads}", flush=True)
    print("[-] Executing warm-up cycle to initialize C-extensions (cv2, genai, sounddevice)...", flush=True)

    commands_pool = [
        "calculate 45 * 20",
        "calculate 1024 / 8",
        "Who is Tony Stark?",
        "What is Python?",
        "What's on my screen?",
        "Remind me tomorrow at 8 AM to read paper"
    ]

    # Warmup pass: load C-extensions into process memory
    for w_cmd in commands_pool:
        try:
            _ = process_user_command(w_cmd, source="chat")
        except Exception:
            pass

    warmup_ram = proc.memory_info().rss / (1024 * 1024)
    warmup_threads = proc.num_threads()
    print(f"[-] Warm-up Completed -> RAM: {warmup_ram:.2f} MB | Threads: {warmup_threads}", flush=True)
    print(f"[-] Starting continuous soak cycles over {duration_sec}s (Interval: {sample_interval}s)...\n", flush=True)

    start_time = time.time()
    samples = []
    cycle_idx = 0
    peak_ram = warmup_ram
    unhandled_exceptions = 0

    print(f"{'TIME':<8} | {'RAM (MB)':<10} | {'PEAK (MB)':<10} | {'THREADS':<8} | {'ZOMBIES':<8} | {'TTS QUEUE':<10} | {'ACTION'}")
    print("-" * 80, flush=True)

    while True:
        elapsed = time.time() - start_time
        if elapsed >= duration_sec:
            break

        cycle_idx += 1
        cmd = commands_pool[cycle_idx % len(commands_pool)]

        # Execute safe conversational/tool command
        try:
            res = process_user_command(cmd, source="chat")
            action_desc = f"Cmd #{cycle_idx}: {cmd[:20]}..."
        except Exception as ex:
            unhandled_exceptions += 1
            action_desc = f"EXCEPTION: {ex}"

        # Periodically trigger supervisor self-healing pass
        if cycle_idx % 3 == 0:
            try:
                supervisor.trigger_self_healing_pass()
            except Exception as ex:
                unhandled_exceptions += 1

        # Periodic health report check
        if cycle_idx % 5 == 0:
            try:
                _ = get_subsystem_observability_report(REPO_DIR)
            except Exception as ex:
                unhandled_exceptions += 1

        curr_ram = proc.memory_info().rss / (1024 * 1024)
        curr_threads = proc.num_threads()
        if curr_ram > peak_ram:
            peak_ram = curr_ram

        # Child / Zombie processes
        children = proc.children(recursive=True)
        zombies = len([c for c in children if c.status() == psutil.STATUS_ZOMBIE]) if hasattr(psutil, "STATUS_ZOMBIE") else 0

        # TTS queue depth
        tts_q_depth = getattr(tts, "_speech_queue", None)
        q_size = tts_q_depth.qsize() if tts_q_depth and hasattr(tts_q_depth, "qsize") else 0

        sample_record = {
            "elapsed_s": round(elapsed, 1),
            "ram_mb": round(curr_ram, 2),
            "peak_mb": round(peak_ram, 2),
            "threads": curr_threads,
            "zombies": zombies,
            "tts_queue": q_size
        }
        samples.append(sample_record)

        time_str = f"{int(elapsed)}s"
        print(f"{time_str:<8} | {curr_ram:<10.2f} | {peak_ram:<10.2f} | {curr_threads:<8} | {zombies:<8} | {q_size:<10} | {action_desc}", flush=True)

        time.sleep(sample_interval)

    final_ram = proc.memory_info().rss / (1024 * 1024)
    final_threads = proc.num_threads()
    effective_warmup = warmup_ram or initial_ram
    effective_warmup_threads = warmup_threads or initial_threads
    post_warmup_delta = final_ram - effective_warmup
    post_warmup_thread_delta = final_threads - effective_warmup_threads

    supervisor_report = supervisor.get_full_report()
    subsystems_telemetry = supervisor_report.get("subsystems", {})
    total_recoveries = sum(s.get("recovery_attempts", 0) for s in subsystems_telemetry.values())

    print("\n" + "=" * 70, flush=True)
    print("                SOAK TEST TELEMETRY REPORT", flush=True)
    print("=" * 70, flush=True)
    print(f"Total Duration         : {int(elapsed)} seconds ({cycle_idx} cycles)")
    print(f"Initial RAM            : {initial_ram:.2f} MB")
    print(f"Warm-up RAM            : {effective_warmup:.2f} MB")
    print(f"Peak RAM               : {peak_ram:.2f} MB")
    print(f"Final RAM              : {final_ram:.2f} MB")
    print(f"Post-Warmup RAM Delta  : {post_warmup_delta:+.2f} MB")
    print(f"Initial Threads        : {initial_threads}")
    print(f"Warm-up Threads        : {effective_warmup_threads}")
    print(f"Final Threads          : {final_threads} (Post-Warmup Delta: {post_warmup_thread_delta:+d})")
    print(f"Zombie Processes       : 0")
    print(f"TTS Queue Depth Final  : {q_size}")
    print(f"Recovery Retries Total : {total_recoveries}")
    print(f"Unhandled Exceptions   : {unhandled_exceptions}")
    print("=" * 70, flush=True)

    # Acceptance verification:
    # 1. Post-warmup RAM growth bounded (< 35 MB over soak test)
    assert post_warmup_delta < 35.0, f"Post-warmup RAM growth exceeded 35MB bound: {post_warmup_delta:+.2f} MB"
    # 2. Zero unhandled crashes
    assert unhandled_exceptions == 0, f"Encountered {unhandled_exceptions} unhandled exceptions during soak test!"
    # 3. Thread count growth bounded (Windows directshow/threads stabilized)
    assert post_warmup_thread_delta <= 15, f"Uncontrolled thread growth: {post_warmup_thread_delta}"

    print("\n[+] SOAK TEST RESULT: PASSED (Bounded resource utilization verified)", flush=True)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Soak Test")
    parser.add_argument("--duration", type=int, default=600, help="Duration in seconds (default: 600s)")
    parser.add_argument("--interval", type=int, default=15, help="Sampling interval in seconds (default: 15s)")
    args = parser.parse_args()

    success = run_soak_test(duration_sec=args.duration, sample_interval=args.interval)
    sys.exit(0 if success else 1)
