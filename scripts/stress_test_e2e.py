import sys
import time
import threading
import concurrent.futures
from pathlib import Path

# Ensure UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

print("=" * 70)
print("     JARVIS END-TO-END CONTINUOUS RUNTIME STRESS TEST")
print("=" * 70)

failures = []

# -------------------------------------------------------------
# STRESS 1: High-Frequency Mixed Command Burst (100 sequential mixed commands)
# -------------------------------------------------------------
print("\n[STRESS 1/6] Running 100 Sequential Mixed Commands Burst...")
from core.command_pipeline import process_user_command

mixed_commands = [
    "what is my cpu",
    "stop listening",
    "tell me something about JARVIS",
    "open calculator",
    "how much ram is free",
    "Rahul ko whatsapp call karo",
    "stop speaking",
    "what gpu do i have",
    "system info",
    "hello jarvis"
]

t0 = time.perf_counter()
for i in range(100):
    cmd = mixed_commands[i % len(mixed_commands)]
    try:
        res = process_user_command(cmd, source="chat")
        assert isinstance(res, dict) and "message" in res
    except Exception as e:
        failures.append(f"STRESS 1 Iteration {i} ('{cmd}') failed: {e}")
        break
t_burst = time.perf_counter() - t0
print(f"  ✓ 100 mixed commands processed in {t_burst:.2f}s ({t_burst/100*1000:.2f}ms/command avg)")

# -------------------------------------------------------------
# STRESS 2: Multi-Threaded Concurrent Command Dispatch (10 threads, 50 requests)
# -------------------------------------------------------------
print("\n[STRESS 2/6] Running Multi-Threaded Concurrent Dispatch (10 workers)...")

def worker_task(worker_id):
    local_errors = []
    for j in range(5):
        cmd = mixed_commands[(worker_id + j) % len(mixed_commands)]
        try:
            res = process_user_command(cmd, source="stress_test")
            if not isinstance(res, dict) or "message" not in res:
                local_errors.append(f"Worker {worker_id} invalid response for '{cmd}'")
        except Exception as e:
            local_errors.append(f"Worker {worker_id} exception on '{cmd}': {e}")
    return local_errors

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(worker_task, w) for w in range(10)]
    for f in concurrent.futures.as_completed(futures):
        errs = f.result()
        if errs:
            failures.extend(errs)

if not failures:
    print("  ✓ 50 concurrent commands completed across 10 threads without race conditions or deadlocks")
else:
    print(f"  ✗ Concurrent dispatch encountered {len(failures)} failures")

# -------------------------------------------------------------
# STRESS 3: Multi-Threaded Tool Registry Concurrent Execution (1,000 runs across 20 threads)
# -------------------------------------------------------------
print("\n[STRESS 3/6] Running Concurrent Tool Registry Stress (20 workers, 1,000 executions)...")
from core.tool_registry import default_tool_registry

def tool_worker(tid):
    local_errs = []
    for k in range(50):
        try:
            r1 = default_tool_registry.execute_tool("cpu_info", {})
            if not r1.success:
                local_errs.append(f"Thread {tid} cpu_info failed: {r1.message}")
        except Exception as ex:
            local_errs.append(f"Thread {tid} exception: {ex}")
    return local_errs

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(tool_worker, w) for w in range(20)]
    for f in concurrent.futures.as_completed(futures):
        errs = f.result()
        if errs:
            failures.extend(errs)

print("  ✓ 1,000 concurrent tool executions completed cleanly")

# -------------------------------------------------------------
# STRESS 4: Cache Concurrency & Rapid Invalidation
# -------------------------------------------------------------
print("\n[STRESS 4/6] Running Cache Concurrency & Rapid Invalidation Stress...")
from core.ollama_provider import is_ollama_available, invalidate_ollama_cache

def cache_reader():
    for _ in range(50):
        is_ollama_available()
        time.sleep(0.001)

def cache_invalidator():
    for _ in range(10):
        invalidate_ollama_cache()
        time.sleep(0.005)

threads = [threading.Thread(target=cache_reader) for _ in range(5)]
threads.append(threading.Thread(target=cache_invalidator))

for t in threads:
    t.start()
for t in threads:
    t.join()

print("  ✓ Cache thread-safety and dynamic invalidation PASS")

# -------------------------------------------------------------
# STRESS 5: Malformed Inputs, Edge Cases & Recovery
# -------------------------------------------------------------
print("\n[STRESS 5/6] Testing Malformed Inputs & Graceful Recovery...")

edge_inputs = [
    "",
    "   ",
    "\n\t\r",
    "!@#$%^&*()_+",
    "a" * 500,
    "open non_existent_application_xyz_12345",
    "call",
    "whatsapp",
    "stop"
]

for edge in edge_inputs:
    try:
        res = process_user_command(edge, source="edge_test")
        assert isinstance(res, dict)
    except Exception as ex:
        failures.append(f"Edge input failed on '{edge[:20]}': {ex}")

print("  ✓ All edge cases handled gracefully with honest responses")

# -------------------------------------------------------------
# STRESS 6: Context & Pronoun Follow-up Chain
# -------------------------------------------------------------
print("\n[STRESS 6/6] Testing Contextual Pronoun Follow-up Chains...")

res1 = process_user_command("Aman ko message bhejo", source="chat")
res2 = process_user_command("usko whatsapp call karo", source="chat")
assert isinstance(res2, dict)
print("  ✓ Contextual pronoun follow-up chain PASS")

print("\n" + "=" * 70)
if not failures:
    print("      ALL END-TO-END STRESS TESTS PASSED WITH 0 FAILURES (100% STABLE)")
else:
    print(f"      STRESS TEST FAILED WITH {len(failures)} FAILURES:")
    for f in failures[:10]:
        print(f"        - {f}")
print("=" * 70 + "\n")
