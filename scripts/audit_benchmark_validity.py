# scripts/audit_benchmark_validity.py
# Benchmark Validity & Mathematical Reconciliation Profiler for Ollama Local Inference
# Independent nanosecond-precision micro-audit for:
# 1. Exact HTTP connection vs server receipt vs prompt eval vs TTFT vs generation breakdown
# 2. Reconciling reported prompt eval time (0.28 ms/tok) vs TTFT (~2154 ms)
# 3. Reading raw Ollama server telemetry metadata (load_duration, prompt_eval_duration, eval_duration)
# 4. Stage-by-stage COLD x5 vs WARM x20 statistical percentiles

import os
import sys
import time
import json
import urllib.request
import statistics

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL = "fotiecodes/jarvis:latest"

def percentile(vals, p):
    if not vals: return 0.0
    s = sorted(vals)
    idx = (p / 100.0) * (len(s) - 1)
    low = int(idx)
    high = min(low + 1, len(s) - 1)
    w = idx - low
    return s[low] * (1.0 - w) + s[high] * w

def stats_dict(vals):
    s = sorted(vals)
    return {
        "min": s[0],
        "p50": statistics.median(s),
        "p95": percentile(s, 95.0),
        "p99": percentile(s, 99.0),
        "max": s[-1]
    }

def audit_single_request(prompt: str, system_prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
        "options": {
            "temperature": 0.7,
            "num_predict": 80,
            "num_ctx": 1024
        },
        "keep_alive": "15m"
    }
    data = json.dumps(payload).encode("utf-8")
    
    t0_start = time.perf_counter_ns()
    
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json", "Connection": "keep-alive"},
        method="POST"
    )
    
    t1_http_sent = time.perf_counter_ns()
    
    tokens = []
    sentence_buf = ""
    first_sentence = ""
    
    t2_resp_headers = None
    t3_first_token = None
    t4_first_sentence = None
    final_json = {}
    
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        t2_resp_headers = time.perf_counter_ns()
        
        for line in resp:
            t_line = time.perf_counter_ns()
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            token = chunk.get("response", "")
            
            if chunk.get("done", False):
                final_json = chunk
                
            if token:
                if t3_first_token is None:
                    t3_first_token = t_line
                tokens.append(token)
                sentence_buf += token
                if t4_first_sentence is None and any(p in sentence_buf for p in [".", "!", "?", "\n"]):
                    t4_first_sentence = t_line
                    first_sentence = sentence_buf.strip()
                    
    t5_end = time.perf_counter_ns()
    
    # Nanosecond to Millisecond breakdown
    py_http_dispatch = (t1_http_sent - t0_start) / 1e6
    py_headers_recv = (t2_resp_headers - t1_http_sent) / 1e6
    py_ttft = (t3_first_token - t0_start) / 1e6 if t3_first_token else (t2_resp_headers - t0_start) / 1e6
    py_first_sentence = (t4_first_sentence - t0_start) / 1e6 if t4_first_sentence else py_ttft
    py_total = (t5_end - t0_start) / 1e6
    
    # Raw Ollama Telemetry (ns -> ms)
    total_dur_ms = final_json.get("total_duration", 0) / 1e6
    load_dur_ms = final_json.get("load_duration", 0) / 1e6
    peval_cnt = final_json.get("prompt_eval_count", 0)
    peval_dur_ms = final_json.get("prompt_eval_duration", 0) / 1e6
    eval_cnt = final_json.get("eval_count", 0)
    eval_dur_ms = final_json.get("eval_duration", 0) / 1e6
    
    peval_ms_per_tok = (peval_dur_ms / peval_cnt) if peval_cnt > 0 else 0.0
    eval_tok_per_sec = (eval_cnt / (eval_dur_ms / 1000.0)) if eval_dur_ms > 0 else 0.0
    
    return {
        "py_http_dispatch": py_http_dispatch,
        "py_headers_recv": py_headers_recv,
        "py_ttft": py_ttft,
        "py_first_sentence": py_first_sentence,
        "py_total": py_total,
        "ollama_total_ms": total_dur_ms,
        "ollama_load_ms": load_dur_ms,
        "ollama_peval_cnt": peval_cnt,
        "ollama_peval_ms": peval_dur_ms,
        "ollama_peval_ms_per_tok": peval_ms_per_tok,
        "ollama_eval_cnt": eval_cnt,
        "ollama_eval_ms": eval_dur_ms,
        "ollama_eval_tps": eval_tok_per_sec,
        "tokens_len": len(tokens),
        "first_sentence": first_sentence
    }

def main():
    print("=========================================================================")
    print("      JARVIS — BENCHMARK VALIDITY & MATHEMATICAL RECONCILIATION          ")
    print("=========================================================================\n")
    
    sys_prompt = "You are JARVIS. Be concise, direct, and witty."
    prompt = "Quantum computing kya hai aur yeh kaise kaam karta hai?"
    
    print("Running COLD x5 requests...")
    cold_results = []
    for i in range(5):
        r = audit_single_request(prompt, sys_prompt)
        cold_results.append(r)
        print(f"  Cold {i+1}: Headers={r['py_headers_recv']:.2f}ms | TTFT={r['py_ttft']:.2f}ms | LoadDur={r['ollama_load_ms']:.2f}ms | PEvalDur={r['ollama_peval_ms']:.2f}ms | GenTotal={r['py_total']:.2f}ms")
        time.sleep(0.2)
        
    print("\nRunning WARM x20 requests...")
    warm_results = []
    for i in range(20):
        r = audit_single_request(prompt, sys_prompt)
        warm_results.append(r)
        print(f"  Warm {i+1:02d}: Headers={r['py_headers_recv']:.2f}ms | TTFT={r['py_ttft']:.2f}ms | LoadDur={r['ollama_load_ms']:.2f}ms | PEvalDur={r['ollama_peval_ms']:.2f}ms | EvalDur={r['ollama_eval_ms']:.2f}ms")
        time.sleep(0.05)
        
    print("\n==========================================================================================================================")
    print(" INDEPENDENT STAGE-BY-STAGE LATENCY BREAKDOWN (ms) [WARM x20 STATS]")
    print("==========================================================================================================================")
    
    metrics = [
        ("Python HTTP Dispatch Time", "py_http_dispatch"),
        ("HTTP Response Headers Recv", "py_headers_recv"),
        ("Python Measured TTFT", "py_ttft"),
        ("First Useful Sentence", "py_first_sentence"),
        ("Python Total Request", "py_total"),
        ("Ollama Telemetry: Total Duration", "ollama_total_ms"),
        ("Ollama Telemetry: Model Load", "ollama_load_ms"),
        ("Ollama Telemetry: Prompt Eval", "ollama_peval_ms"),
        ("Ollama Telemetry: Token Eval", "ollama_eval_ms"),
    ]
    
    print(f"{'STAGE METRIC':<36} | {'MIN':<9} | {'P50':<9} | {'P95':<9} | {'P99':<9} | {'MAX':<9}")
    print("-" * 92)
    for label, key in metrics:
        st = stats_dict([r[key] for r in warm_results])
        print(f"{label:<36} | {st['min']:<9.2f} | {st['p50']:<9.2f} | {st['p95']:<9.2f} | {st['p99']:<9.2f} | {st['max']:<9.2f}")
        
    print("\n==========================================================================================================================")
    print(" OLLAMA RAW TELEMETRY MATHEMATICAL RECONCILIATION")
    print("==========================================================================================================================")
    med_r = warm_results[0]
    peval_cnt = stats_dict([r["ollama_peval_cnt"] for r in warm_results])['p50']
    peval_ms = stats_dict([r["ollama_peval_ms"] for r in warm_results])['p50']
    eval_cnt = stats_dict([r["ollama_eval_cnt"] for r in warm_results])['p50']
    eval_ms = stats_dict([r["ollama_eval_ms"] for r in warm_results])['p50']
    headers_ms = stats_dict([r["py_headers_recv"] for r in warm_results])['p50']
    load_ms = stats_dict([r["ollama_load_ms"] for r in warm_results])['p50']
    ttft_ms = stats_dict([r["py_ttft"] for r in warm_results])['p50']
    
    print(f"1. Prompt Token Count (P50)           : {peval_cnt:.0f} tokens")
    print(f"2. Prompt Evaluation Duration (P50)   : {peval_ms:.2f} ms")
    print(f"3. Prompt Eval Rate (peval_ms / cnt)  : {peval_ms / peval_cnt:.2f} ms/token")
    print(f"4. Model Load Duration (P50)          : {load_ms:.2f} ms")
    print(f"5. HTTP Response Headers Recv (P50)   : {headers_ms:.2f} ms")
    print(f"6. Python Measured TTFT (P50)         : {ttft_ms:.2f} ms")
    print(f"7. Mathematical Sum (Load + PEval)    : {(load_ms + peval_ms):.2f} ms")
    print(f"8. Discrepancy (Headers Recv - Sum)   : {(headers_ms - (load_ms + peval_ms)):.2f} ms")
    print("==========================================================================================================================\n")

if __name__ == "__main__":
    main()
