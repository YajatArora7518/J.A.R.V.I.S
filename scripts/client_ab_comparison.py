# scripts/client_ab_comparison.py
# Phase 10 Client A/B Testing Matrix: urllib vs requests vs raw socket vs persistent connection

import os
import sys
import time
import json
import socket
import urllib.request
import statistics
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"
MODEL = "fotiecodes/jarvis:latest"

PROMPT = "Quantum computing kya hai?"
SYSTEM_PROMPT = "You are JARVIS. Be concise."

def test_urllib_client():
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "system": SYSTEM_PROMPT,
        "stream": True,
        "options": {"temperature": 0.7, "num_predict": 40, "num_ctx": 1024},
        "keep_alive": "24h"
    }
    data = json.dumps(payload).encode("utf-8")
    t0 = time.perf_counter_ns()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json", "Connection": "keep-alive"},
        method="POST"
    )
    t1_sent = time.perf_counter_ns()
    ttft = None
    t_end = None
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        for line in resp:
            if not line: continue
            chunk = json.loads(line.decode("utf-8"))
            if chunk.get("response") and ttft is None:
                ttft = time.perf_counter_ns()
    t_end = time.perf_counter_ns()
    
    return {
        "dispatch_ms": (t1_sent - t0) / 1e6,
        "ttft_ms": (ttft - t0) / 1e6 if ttft else 0.0,
        "total_ms": (t_end - t0) / 1e6
    }

def test_requests_client():
    try:
        import requests
    except ImportError:
        return None

    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "system": SYSTEM_PROMPT,
        "stream": True,
        "options": {"temperature": 0.7, "num_predict": 40, "num_ctx": 1024},
        "keep_alive": "24h"
    }
    t0 = time.perf_counter_ns()
    session = requests.Session()
    t1_sent = time.perf_counter_ns()
    resp = session.post(OLLAMA_URL, json=payload, stream=True, timeout=30.0)
    ttft = None
    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line.decode("utf-8"))
            if chunk.get("response") and ttft is None:
                ttft = time.perf_counter_ns()
    t_end = time.perf_counter_ns()
    session.close()

    return {
        "dispatch_ms": (t1_sent - t0) / 1e6,
        "ttft_ms": (ttft - t0) / 1e6 if ttft else 0.0,
        "total_ms": (t_end - t0) / 1e6
    }

def test_raw_socket_client():
    payload_dict = {
        "model": MODEL,
        "prompt": PROMPT,
        "system": SYSTEM_PROMPT,
        "stream": True,
        "options": {"temperature": 0.7, "num_predict": 40, "num_ctx": 1024},
        "keep_alive": "24h"
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    t0 = time.perf_counter_ns()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((OLLAMA_HOST, OLLAMA_PORT))
    headers = (
        f"POST /api/generate HTTP/1.1\r\n"
        f"Host: {OLLAMA_HOST}:{OLLAMA_PORT}\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload_bytes)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")
    sock.sendall(headers + payload_bytes)
    t1_sent = time.perf_counter_ns()
    
    ttft = None
    buf = bytearray()
    while True:
        chunk = sock.recv(1024)
        now_ns = time.perf_counter_ns()
        if not chunk: break
        buf.extend(chunk)
        if b"\r\n\r\n" in buf and ttft is None:
            ttft = now_ns
    t_end = time.perf_counter_ns()
    sock.close()

    return {
        "dispatch_ms": (t1_sent - t0) / 1e6,
        "ttft_ms": (ttft - t0) / 1e6 if ttft else 0.0,
        "total_ms": (t_end - t0) / 1e6
    }

def run_ab_tests():
    print("=========================================================================")
    print("       JARVIS — PHASE 10 CLIENT A/B TRANSPORT COMPARISON MATRIX         ")
    print("=========================================================================\n")
    
    results = {"urllib": [], "requests": [], "raw_socket": []}
    
    for i in range(5):
        u = test_urllib_client()
        results["urllib"].append(u)
        
        req = test_requests_client()
        if req: results["requests"].append(req)
        
        raw = test_raw_socket_client()
        results["raw_socket"].append(raw)
        time.sleep(0.1)

    print("CLIENT TYPE      | DISPATCH (P50) | TTFT (P50)     | TOTAL DURATION (P50)")
    print("-------------------------------------------------------------------------")
    for client_name in ["urllib", "requests", "raw_socket"]:
        res_list = results[client_name]
        if not res_list: continue
        d_p50 = statistics.median([r["dispatch_ms"] for r in res_list])
        t_p50 = statistics.median([r["ttft_ms"] for r in res_list])
        tot_p50 = statistics.median([r["total_ms"] for r in res_list])
        print(f"{client_name:<16} | {d_p50:8.2f} ms | {t_p50:8.2f} ms | {tot_p50:8.2f} ms")
    print("-------------------------------------------------------------------------\n")

if __name__ == "__main__":
    run_ab_tests()
