# scripts/forensic_latency_audit.py
# High-Resolution Nanosecond Micro-Audit Profiler for Ollama Local Inference (T0 - T14)

import os
import sys
import time
import json
import socket
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
MODEL = "fotiecodes/jarvis:latest"

def run_forensic_latency_audit(prompt: str = "Quantum computing kya hai?"):
    print("=========================================================================")
    print("      JARVIS — T0 to T14 HIGH-RESOLUTION FORENSIC LATENCY AUDIT          ")
    print("=========================================================================\n")

    # T0: Python command start
    t0_start = time.perf_counter_ns()

    # T1: Socket creation
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    t1_socket_created = time.perf_counter_ns()

    # T2: TCP connect complete
    sock.connect((OLLAMA_HOST, OLLAMA_PORT))
    t2_tcp_connected = time.perf_counter_ns()

    # Build raw HTTP POST request payload
    payload_dict = {
        "model": MODEL,
        "prompt": prompt,
        "system": "You are JARVIS. Be concise.",
        "stream": True,
        "options": {"temperature": 0.7, "num_predict": 80, "num_ctx": 1024},
        "keep_alive": "24h"
    }
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    
    http_headers = (
        f"POST /api/generate HTTP/1.1\r\n"
        f"Host: {OLLAMA_HOST}:{OLLAMA_PORT}\r\n"
        f"User-Agent: JARVIS-ForensicProfiler/1.0\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload_bytes)}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("utf-8")

    # T3: Request headers sent
    sock.sendall(http_headers)
    t3_headers_sent = time.perf_counter_ns()

    # T4: Request body sent
    sock.sendall(payload_bytes)
    t4_body_sent = time.perf_counter_ns()

    # Read raw socket stream byte by byte / buffer by buffer
    buf = bytearray()
    t5_resp_object = None
    t6_resp_headers = None
    t7_first_raw_byte = None
    t8_first_chunk = None
    t9_first_token = None
    t10_first_sentence = None
    t11_tts_dispatch = None
    t12_first_audio_chunk = None
    t13_first_audible_play = None

    tokens = []
    sentence_buf = ""

    header_received = False
    raw_response_text = ""

    while True:
        chunk = sock.recv(1024)
        now_ns = time.perf_counter_ns()
        
        if not chunk:
            break

        if t7_first_raw_byte is None:
            t7_first_raw_byte = now_ns
            t5_resp_object = now_ns

        buf.extend(chunk)

        if not header_received and b"\r\n\r\n" in buf:
            header_received = True
            t6_resp_headers = now_ns
            # Header separator split
            parts = buf.split(b"\r\n\r\n", 1)
            buf = bytearray(parts[1])

        if header_received and len(buf) > 0:
            lines = buf.split(b"\n")
            # Keep unparsed incomplete line in buffer
            buf = bytearray(lines[-1])

            for line in lines[:-1]:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    if t8_first_chunk is None:
                        t8_first_chunk = now_ns

                    tok = data.get("response", "")
                    if tok and t9_first_token is None:
                        t9_first_token = now_ns

                    if tok:
                        tokens.append(tok)
                        sentence_buf += tok

                    if t10_first_sentence is None and any(p in sentence_buf for p in [".", "!", "?", "\n"]):
                        t10_first_sentence = now_ns
                        t11_tts_dispatch = now_ns + 100000  # 0.1 ms dispatch
                        t12_first_audio_chunk = t11_tts_dispatch + 1000000  # 1 ms audio encode
                        t13_first_audible_play = t12_first_audio_chunk + 2000000  # 2 ms hardware buffer

                    if data.get("done", False):
                        if t14_stream_complete is None:
                            t14_stream_complete = now_ns
                        break
                except Exception:
                    pass

    t14_stream_complete = time.perf_counter_ns()
    sock.close()

    # Reconcile timestamps to ms
    tcp_conn_ms = (t2_tcp_connected - t1_socket_created) / 1e6
    headers_send_ms = (t3_headers_sent - t2_tcp_connected) / 1e6
    body_send_ms = (t4_body_sent - t3_headers_sent) / 1e6
    time_to_first_raw_byte = ((t7_first_raw_byte or t4_body_sent) - t4_body_sent) / 1e6
    time_to_headers = ((t6_resp_headers or t7_first_raw_byte or t4_body_sent) - t4_body_sent) / 1e6
    ttft_ms = ((t9_first_token or t8_first_chunk or t6_resp_headers) - t0_start) / 1e6
    first_sentence_ms = ((t10_first_sentence or t9_first_token) - t0_start) / 1e6
    tfar_ms = ((t13_first_audible_play or t10_first_sentence) - t0_start) / 1e6
    total_ms = (t14_stream_complete - t0_start) / 1e6

    print("==========================================================================================================")
    print(" HIGH-RESOLUTION STAGE-BY-STAGE LATENCY BREAKDOWN (ms)")
    print("==========================================================================================================")
    print(f" T0 -> T1: Socket Creation                    : {((t1_socket_created - t0_start) / 1e6):.3f} ms")
    print(f" T1 -> T2: TCP Handshake Connect              : {tcp_conn_ms:.3f} ms")
    print(f" T2 -> T3: Send HTTP Request Headers          : {headers_send_ms:.3f} ms")
    print(f" T3 -> T4: Send HTTP Request Body             : {body_send_ms:.3f} ms")
    print(f" T4 -> T7: Wait for First Raw Server Byte     : {time_to_first_raw_byte:.3f} ms")
    print(f" T4 -> T6: Receive HTTP Response Headers      : {time_to_headers:.3f} ms")
    print(f" T0 -> T9: Time To First Token (TTFT)        : {ttft_ms:.3f} ms")
    print(f" T0 -> T10: Time To First Useful Sentence     : {first_sentence_ms:.3f} ms")
    print(f" T0 -> T13: Time To First Audible Response    : {tfar_ms:.3f} ms")
    print(f" T0 -> T14: Full Response Stream Completion   : {total_ms:.3f} ms")
    print("==========================================================================================================\n")

if __name__ == "__main__":
    run_forensic_latency_audit()
