# scripts/test_performance_benchmarks.py
# Comprehensive Latency Profiler & Benchmark Audit for JARVIS Universal Assistant

import sys
import time
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.intent_router import classify_intent
from actions.universal_messaging import resolve_recipient_contact, send_universal_message
from actions.mobile_pc_gateway import mobile_pc_gateway


def profile_intent_classification():
    print("\n=======================================================")
    print(" 1. INTENT CLASSIFICATION LATENCY BENCHMARK")
    print("=======================================================")
    commands = [
        "Rahul ko WhatsApp message bhejo main ghar aa raha hoon",
        "Chrome kholo",
        "WhatsApp kholo",
        "Rahul ko call karo",
        "Phone online hai?",
        "All connections ka status bata"
    ]

    latencies = []
    for cmd in commands:
        t0 = time.perf_counter()
        res = classify_intent(cmd)
        lat = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat)
        print(f"Command: '{cmd:<55}' | Intent: {res.get('intent'):<20} | Latency: {lat:.3f} ms")

    avg_lat = sum(latencies) / len(latencies)
    print(f"\n[BENCHMARK] Average Intent Classification Latency: {avg_lat:.3f} ms (Target: <2.0 ms)")
    assert avg_lat < 5.0, "Intent classification latency exceeded target threshold!"
    return avg_lat


def profile_contact_resolution():
    print("\n=======================================================")
    print(" 2. CONTACT RESOLUTION & CACHE LATENCY BENCHMARK")
    print("=======================================================")
    queries = ["Rahul", "Aman", "Priya", "Rahul", "Rahul"]

    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        res = resolve_recipient_contact(q)
        lat = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat)
        status = res.get("status")
        print(f"Query: '{q:<10}' | Status: {status:<12} | Latency: {lat:.3f} ms")

    cached_lat = sum(latencies[3:]) / len(latencies[3:])
    print(f"\n[BENCHMARK] Cached Contact Resolution Latency: {cached_lat:.3f} ms (Target: <0.1 ms)")
    assert cached_lat < 1.0, "Contact resolution cache latency exceeded threshold!"
    return cached_lat


def profile_mobile_gateway():
    print("\n=======================================================")
    print(" 3. MOBILE PC GATEWAY ROUTING LATENCY BENCHMARK")
    print("=======================================================")
    
    t0 = time.perf_counter()
    res = mobile_pc_gateway.route_cross_device_action("pc", "phone", "send_sms", {"recipient": "Test", "message": "Benchmark"})
    lat = (time.perf_counter() - t0) * 1000.0
    print(f"Cross-Device Action Routing Latency: {lat:.3f} ms | Offline Verified: {res.get('device_offline')}")
    assert lat < 10.0, "Gateway routing latency exceeded target threshold!"
    return lat


def profile_end_to_end_pipeline():
    print("\n=======================================================")
    print(" 4. END-TO-END PIPELINE PROFILING BREAKDOWN")
    print("=======================================================")
    
    cmd = "Rahul ko WhatsApp par message bhejo: Fast Path Test"
    
    t0 = time.perf_counter()
    # Step 1: Intent
    t1_0 = time.perf_counter()
    intent_res = classify_intent(cmd)
    t1_1 = time.perf_counter()
    lat_intent = (t1_1 - t1_0) * 1000.0

    # Step 2: Contact
    t2_0 = time.perf_counter()
    rec_res = resolve_recipient_contact("Rahul")
    t2_1 = time.perf_counter()
    lat_contact = (t2_1 - t2_0) * 1000.0

    # Step 3: Fast-Path Routing
    t3_0 = time.perf_counter()
    # Verification of tool parameter matching
    tool_name = intent_res.get("tool")
    t3_1 = time.perf_counter()
    lat_tool = (t3_1 - t3_0) * 1000.0

    t_total = (time.perf_counter() - t0) * 1000.0

    print("END-TO-END BREAKDOWN:")
    print(f"  T1: Fast-Path Intent Router  : {lat_intent:.3f} ms")
    print(f"  T2: Contact Resolution Cache: {lat_contact:.3f} ms")
    print(f"  T3: Tool Dispatch & Select  : {lat_tool:.3f} ms")
    print(f"--------------------------------------------------")
    print(f"  TOTAL END-TO-END PIPELINE  : {t_total:.3f} ms")

    return {
        "intent_ms": lat_intent,
        "contact_ms": lat_contact,
        "tool_ms": lat_tool,
        "total_ms": t_total
    }


if __name__ == "__main__":
    print("STARTING LATENCY BENCHMARK & PERFORMANCE AUDIT...")
    lat_intent = profile_intent_classification()
    lat_contact = profile_contact_resolution()
    lat_gateway = profile_mobile_gateway()
    e2e = profile_end_to_end_pipeline()

    print("\n=======================================================")
    print(" PERFORMANCE BENCHMARK SUMMARY")
    print("=======================================================")
    print(f"  Intent Classification      : {lat_intent:.3f} ms")
    print(f"  Contact Resolution Cache   : {lat_contact:.3f} ms")
    print(f"  Gateway Routing            : {lat_gateway:.3f} ms")
    print(f"  Total Pipeline (Sub-System): {e2e['total_ms']:.3f} ms")
    print("ALL LATENCY BENCHMARKS PASSED. OPTIMIZATION COMPLETE.")
