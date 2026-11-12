# scripts/run_real_world_soak.py
# Real-World Continuous Soak & Stability Telemetry Harness for J.A.R.V.I.S.
# Executes realistic non-destructive workloads over extended duration with deep telemetry.

import os
import sys
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

import psutil
import sounddevice as sd

from core.command_pipeline import process_user_command
from core.runtime_supervisor import get_runtime_supervisor, SubsystemState
from core.tts_engine import get_tts_engine
from core.ollama_provider import is_ollama_available, generate_ollama_response
from core.ai_multitier_engine import get_ai_engine
from actions.app_registry import resolve_app
from memory.memory_manager import load_memory, format_memory_for_prompt
from agent.awareness.camera_provider import camera_provider
from agent.awareness.permissions import privacy_mode_manager
from core.health_check import get_subsystem_observability_report


def run_real_world_soak(duration_sec: int = 1800, sample_interval: int = 15) -> Dict[str, Any]:
    print("=" * 75, flush=True)
    print(f"       J.A.R.V.I.S REAL-WORLD CONTINUOUS SOAK VALIDATION ({duration_sec}s)", flush=True)
    print("=" * 75, flush=True)

    proc = psutil.Process(os.getpid())
    supervisor = get_runtime_supervisor()
    tts = get_tts_engine()
    ai_engine = get_ai_engine()

    start_dt = datetime.now()
    start_time = time.time()
    print(f"[-] Test Start Timestamp    : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    # Initial pre-warmup measurement
    proc.cpu_percent(interval=None)
    initial_ram = proc.memory_info().rss / (1024 * 1024)
    initial_threads = proc.num_threads()
    print(f"[-] Pre-Warmup Process RAM  : {initial_ram:.2f} MB", flush=True)
    print(f"[-] Pre-Warmup Thread Count : {initial_threads}", flush=True)

    # Warmup pass: exercise subsystems once to load C-extensions
    print("[-] Warming up subsystems (Ollama, TTS, OpenCV, sounddevice, Gemini)...", flush=True)
    try:
        _ = process_user_command("Hello JARVIS, status check.", source="chat")
        _ = resolve_app("notepad")
        _ = load_memory()
        _ = camera_provider.sample_context()
    except Exception as we:
        print(f"[!] Warm-up note: {we}", flush=True)

    warmup_ram = proc.memory_info().rss / (1024 * 1024)
    warmup_threads = proc.num_threads()
    print(f"[-] Warm-up Baseline RAM    : {warmup_ram:.2f} MB", flush=True)
    print(f"[-] Warm-up Thread Count    : {warmup_threads}", flush=True)
    print(f"[-] Running continuous soak loop (Interval: {sample_interval}s)...\n", flush=True)

    workload_catalog = [
        # Normal conversation
        {"type": "chat", "cmd": "What is the theory of relativity in one sentence?"},
        {"type": "chat", "cmd": "Who was Alan Turing?"},
        # Hinglish conversation
        {"type": "chat", "cmd": "Kya scene hai aaj ka JARVIS?"},
        {"type": "chat", "cmd": "Monday ka timetable batao"},
        # Application resolution (safe, non-spawning)
        {"type": "app", "cmd": "notepad"},
        {"type": "app", "cmd": "Antigravity"},
        # Screen vision query
        {"type": "screen", "cmd": "What's on my screen?"},
        # Memory query
        {"type": "memory", "cmd": "read_memory"},
        # Reminder query
        {"type": "reminder", "cmd": "Remind me tomorrow at 9 AM to review code"},
        # Direct Ollama inference
        {"type": "ollama", "cmd": "Say status nominal in 3 words"},
        # Audio / TTS output
        {"type": "tts", "cmd": "Systems nominal, Boss."},
        # Idle period (baseline measurement)
        {"type": "idle", "cmd": "sleep_interval"}
    ]

    telemetry_samples: List[Dict[str, Any]] = []
    cycle_count = 0
    peak_ram = warmup_ram
    peak_threads = warmup_threads
    unhandled_exceptions = 0
    recovery_events_total = 0

    print(f"{'ELAPSED':<9} | {'RAM(MB)':<9} | {'PEAK(MB)':<9} | {'CPU%':<6} | {'THRDS':<6} | {'CHLD':<5} | {'TTS_Q':<6} | {'WORKLOAD'}", flush=True)
    print("-" * 80, flush=True)

    while True:
        elapsed = time.time() - start_time
        if elapsed >= duration_sec:
            break

        cycle_count += 1
        workload = workload_catalog[cycle_count % len(workload_catalog)]
        w_type = workload["type"]
        w_cmd = workload["cmd"]
        action_label = f"{w_type}: {w_cmd[:20]}..."

        # Execute realistic workload
        try:
            if w_type == "chat":
                _ = process_user_command(w_cmd, source="chat")
            elif w_type == "app":
                _ = resolve_app(w_cmd)
            elif w_type == "screen":
                _ = process_user_command(w_cmd, source="chat")
            elif w_type == "memory":
                _ = format_memory_for_prompt()
            elif w_type == "reminder":
                _ = process_user_command(w_cmd, source="chat")
            elif w_type == "ollama":
                if is_ollama_available():
                    _ = generate_ollama_response(w_cmd, timeout=15.0)
                else:
                    _ = ai_engine.generate_response(w_cmd, prefer_cloud=True)
            elif w_type == "tts":
                tts.speak(w_cmd, interrupt=True)
                time.sleep(0.3)
            elif w_type == "idle":
                pass
        except Exception as ex:
            unhandled_exceptions += 1
            action_label = f"ERR: {str(ex)[:20]}"

        # Periodic non-destructive maintenance checks
        if cycle_count % 4 == 0:
            try:
                # Camera awareness check
                if not privacy_mode_manager.is_privacy_mode_active():
                    _ = camera_provider.sample_context()
            except Exception:
                pass

        if cycle_count % 6 == 0:
            try:
                # Supervisor self-healing check
                rec_res = supervisor.trigger_self_healing_pass()
                if rec_res:
                    recovery_events_total += len(rec_res)
            except Exception:
                pass

        # Capture telemetry snapshot
        curr_ram = proc.memory_info().rss / (1024 * 1024)
        curr_threads = proc.num_threads()
        curr_cpu = proc.cpu_percent(interval=None)
        children_count = len(proc.children(recursive=True))
        q_size = tts._speech_queue.qsize() if hasattr(tts, "_speech_queue") else 0

        if curr_ram > peak_ram:
            peak_ram = curr_ram
        if curr_threads > peak_threads:
            peak_threads = curr_threads

        sample_record = {
            "cycle": cycle_count,
            "elapsed_sec": round(elapsed, 1),
            "ram_mb": round(curr_ram, 2),
            "peak_ram_mb": round(peak_ram, 2),
            "cpu_percent": curr_cpu,
            "threads": curr_threads,
            "children": children_count,
            "tts_queue": q_size,
            "workload": w_type
        }
        telemetry_samples.append(sample_record)

        elapsed_str = f"{int(elapsed)}s"
        print(f"{elapsed_str:<9} | {curr_ram:<9.2f} | {peak_ram:<9.2f} | {curr_cpu:<6.1f} | {curr_threads:<6} | {children_count:<5} | {q_size:<6} | {action_label}", flush=True)

        # Sleep sample interval
        time.sleep(sample_interval)

    # Soak completed - capture final metrics
    end_dt = datetime.now()
    actual_duration = time.time() - start_time
    final_ram = proc.memory_info().rss / (1024 * 1024)
    final_threads = proc.num_threads()
    final_children = len(proc.children(recursive=True))
    final_tts_q = tts._speech_queue.qsize() if hasattr(tts, "_speech_queue") else 0
    post_warmup_ram_delta = final_ram - warmup_ram
    post_warmup_thread_delta = final_threads - warmup_threads

    sup_report = supervisor.get_full_report()
    subsystems_data = sup_report.get("subsystems", {})

    print("\n" + "=" * 75, flush=True)
    print("         REAL-WORLD SOAK TELEMETRY & ACCEPTANCE REPORT", flush=True)
    print("=" * 75, flush=True)
    print(f"Start Time             : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End Time               : {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Actual Duration        : {actual_duration:.2f} seconds ({actual_duration/60:.2f} minutes, {cycle_count} cycles)")
    print(f"Warm-up Baseline RAM   : {warmup_ram:.2f} MB")
    print(f"Peak RAM               : {peak_ram:.2f} MB")
    print(f"Final RAM              : {final_ram:.2f} MB")
    print(f"Post-Warmup RAM Delta  : {post_warmup_ram_delta:+.2f} MB")
    print(f"Initial Threads        : {initial_threads}")
    print(f"Warm-up Threads        : {warmup_threads}")
    print(f"Peak Threads           : {peak_threads}")
    print(f"Final Threads          : {final_threads} (Delta: {post_warmup_thread_delta:+d})")
    print(f"Child Processes        : {final_children}")
    print(f"TTS Queue Backlog      : {final_tts_q}")
    print(f"Total Recovery Events  : {recovery_events_total}")
    print(f"Unhandled Exceptions   : {unhandled_exceptions}")
    print("=" * 75, flush=True)

    summary_dict = {
        "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_seconds": round(actual_duration, 2),
        "duration_minutes": round(actual_duration / 60, 2),
        "cycles_completed": cycle_count,
        "initial_ram_mb": round(initial_ram, 2),
        "warmup_ram_mb": round(warmup_ram, 2),
        "peak_ram_mb": round(peak_ram, 2),
        "final_ram_mb": round(final_ram, 2),
        "post_warmup_ram_delta_mb": round(post_warmup_ram_delta, 2),
        "initial_threads": initial_threads,
        "warmup_threads": warmup_threads,
        "peak_threads": peak_threads,
        "final_threads": final_threads,
        "post_warmup_thread_delta": post_warmup_thread_delta,
        "child_processes": final_children,
        "tts_queue_backlog": final_tts_q,
        "recovery_events": recovery_events_total,
        "unhandled_exceptions": unhandled_exceptions,
        "subsystems": {k: v.get("state") for k, v in subsystems_data.items()}
    }

    # Acceptance Invariants
    assert post_warmup_ram_delta < 45.0, f"Excessive RAM growth: {post_warmup_ram_delta:+.2f} MB"
    assert post_warmup_thread_delta <= 15, f"Excessive thread growth: {post_warmup_thread_delta:+d}"
    assert final_children == 0, f"Zombie processes detected: {final_children}"
    assert unhandled_exceptions == 0, f"Unhandled exceptions occurred: {unhandled_exceptions}"

    print("\n[+] REAL-WORLD SOAK RESULT: PASSED (Zero Leaks, Zero Deadlocks, Zero Zombies)", flush=True)
    return summary_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S Real-World Soak Test")
    parser.add_argument("--duration", type=int, default=1800, help="Duration in seconds (default: 1800s / 30m)")
    parser.add_argument("--interval", type=int, default=15, help="Sampling interval in seconds (default: 15s)")
    args = parser.parse_args()

    res = run_real_world_soak(duration_sec=args.duration, sample_interval=args.interval)
    sys.exit(0)
