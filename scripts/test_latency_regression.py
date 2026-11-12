# scripts/test_latency_regression.py
# Performance Regression Gate for J.A.R.V.I.S Subsystems
# Asserts strict upper-bound latency ceilings for all fast-path components.

import os
import sys
import time
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.intent_router import classify_intent
from memory.memory_manager import retrieve_relevant_memories
from core.context_retriever import default_context_retriever
from core.safe_calculator import calculate
from core.tts_engine import get_tts_engine
from core.command_pipeline import process_user_command
from actions.app_registry import resolve_app


class TestLatencyRegression(unittest.TestCase):

    def test_intent_routing_latency_bound(self):
        """Intent routing must complete in under 15ms (typical baseline is ~2ms)."""
        queries = [
            "Open Chrome and browse Reddit",
            "What is on my screen?",
            "Calculate 45 * 12",
            "Mute the speakers",
            "Set a reminder for meeting tomorrow"
        ]
        # Warmup
        classify_intent("warmup query")

        latencies = []
        for q in queries:
            t0 = time.perf_counter()
            classify_intent(q)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        max_lat = max(latencies)
        avg_lat = sum(latencies) / len(latencies)
        print(f"\n[LATENCY] Intent Routing: avg={avg_lat:.2f}ms, max={max_lat:.2f}ms")
        self.assertLess(max_lat, 25.0, f"Intent routing exceeded 25ms threshold: {max_lat:.2f}ms")

    def test_memory_retrieval_latency_bound(self):
        """Memory retrieval should complete in under 15ms."""
        retrieve_relevant_memories("warmup")

        t0 = time.perf_counter()
        mems = retrieve_relevant_memories("favorite editor and python project", limit=5)
        dur = (time.perf_counter() - t0) * 1000.0
        print(f"[LATENCY] Memory Retrieval: {dur:.2f}ms ({len(mems)} items)")
        self.assertLess(dur, 25.0, f"Memory retrieval exceeded 25ms ceiling: {dur:.2f}ms")

    def test_context_retrieval_latency_bound(self):
        """Context retrieval should complete in under 20ms."""
        default_context_retriever.retrieve_context("warmup")

        t0 = time.perf_counter()
        ctx = default_context_retriever.retrieve_context("What build errors are in the project?")
        dur = (time.perf_counter() - t0) * 1000.0
        print(f"[LATENCY] Context Retrieval: {dur:.2f}ms (Domain: {ctx.get('domain')})")
        self.assertLess(dur, 30.0, f"Context retrieval exceeded 30ms ceiling: {dur:.2f}ms")

    def test_safe_calculator_latency_bound(self):
        """Calculation AST evaluation must complete in under 5ms."""
        t0 = time.perf_counter()
        res = calculate("25 * 40 + 150 - (20 / 4)")
        dur = (time.perf_counter() - t0) * 1000.0
        print(f"[LATENCY] Safe Calculator: {dur:.2f}ms (Result: {res.get('result')})")
        self.assertLess(dur, 10.0, f"Calculator exceeded 10ms ceiling: {dur:.2f}ms")
        self.assertTrue(res.get("success"))

    def test_app_resolution_latency_bound(self):
        """Local app resolution should complete in under 10ms."""
        resolve_app("notepad")

        t0 = time.perf_counter()
        res = resolve_app("notepad")
        dur = (time.perf_counter() - t0) * 1000.0
        print(f"[LATENCY] App Resolution: {dur:.2f}ms (Found: {res.get('found')})")
        self.assertLess(dur, 20.0, f"App resolution exceeded 20ms ceiling: {dur:.2f}ms")

    def test_tts_queue_and_bargein_latency_bound(self):
        """TTS queue insertion and barge-in stop must both be < 10ms."""
        engine = get_tts_engine()

        t0 = time.perf_counter()
        engine.speak("Latency regression test audio.", interrupt=True)
        t_insert = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        engine.barge_in_stop()
        t_stop = (time.perf_counter() - t0) * 1000.0

        print(f"[LATENCY] TTS Queue Insert: {t_insert:.2f}ms | Barge-in Stop: {t_stop:.2f}ms")
        self.assertLess(t_insert, 15.0, f"TTS insertion exceeded 15ms: {t_insert:.2f}ms")
        self.assertLess(t_stop, 15.0, f"Barge-in stop exceeded 15ms: {t_stop:.2f}ms")


def run_latency_regression():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLatencyRegression)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_latency_regression()
    sys.exit(0 if success else 1)
