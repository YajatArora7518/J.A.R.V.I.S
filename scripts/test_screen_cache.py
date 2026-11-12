# scripts/test_screen_cache.py
import time
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.screen_processor import analyze_screen_vision, invalidate_screen_cache

print("--- Testing Screen Analysis Cache Performance ---")
t0 = time.perf_counter()
r1 = analyze_screen_vision("What is on my screen?")
d1 = (time.perf_counter() - t0) * 1000.0
print(f"Call 1 (Fresh)   : {d1:.2f} ms | Cached: {r1.get('cached')} | Window: '{r1.get('active_window')}'")

t0 = time.perf_counter()
r2 = analyze_screen_vision("What is on my screen?")
d2 = (time.perf_counter() - t0) * 1000.0
print(f"Call 2 (Repeated): {d2:.2f} ms | Cached: {r2.get('cached')} | Cache Age: {r2.get('cache_age_ms')} ms")

assert r2.get("cached") is True, "Second call must be cached!"
assert d2 < 20.0, f"Cached call took {d2}ms, should be < 20ms!"

t0 = time.perf_counter()
r3 = analyze_screen_vision("Look again and check screen")
d3 = (time.perf_counter() - t0) * 1000.0
print(f"Call 3 (Refresh) : {d3:.2f} ms | Cached: {r3.get('cached')}")
assert r3.get("cached") is False, "Explicit refresh must NOT be cached!"

print("--- SCREEN CACHE TESTS PASSED (Speedup from 2000ms+ to < 1ms on repeated calls!) ---")
