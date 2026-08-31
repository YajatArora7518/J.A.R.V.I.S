# scripts/profile_llm_latency.py
# Deep LLM & Voice Response Latency Profiler for JARVIS

import os
import sys
import time
import json
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def profile_llm_latency(iterations: int = 5) -> Dict[str, Any]:
    print("\n========================================================")
    print("        JARVIS LLM & VOICE RESPONSE PROFILER")
    print("========================================================\n")

    results: Dict[str, Any] = {}

    # 1. Prompt Construction & Memory Formatting Time
    from memory.memory_manager import load_memory, format_memory_for_prompt
    t0 = time.perf_counter()
    mem = load_memory()
    mem_ctx = format_memory_for_prompt(mem)
    results["memory_context_ms"] = round((time.perf_counter() - t0) * 1000, 3)

    user_query = "What is quantum computing in one simple sentence?"
    base_sys_prompt = "You are JARVIS, Tony Stark's AI assistant. Be extremely concise (1-2 sentences), direct, and witty."
    full_prompt = f"{mem_ctx}\nUser: {user_query}" if mem_ctx else user_query

    results["prompt_char_length"] = len(full_prompt)
    results["system_prompt_char_length"] = len(base_sys_prompt)

    # 2. Ollama Local LLM Profiling (Cold vs Warm & Streaming TTFT)
    from core.ollama_provider import is_ollama_available, get_ollama_provider

    if not is_ollama_available():
        print(" [WARN] Local Ollama service is not available. Skipping LLM benchmarking.")
        results["ollama_available"] = False
        return results

    results["ollama_available"] = True
    provider = get_ollama_provider()
    results["persona_model"] = provider.persona_model
    results["tool_model"] = provider.tool_model

    ttft_list: List[float] = []
    total_time_list: List[float] = []
    tokens_count_list: List[int] = []
    first_chunk_text_list: List[str] = []

    print(f"Profiling Model: {provider.persona_model} across {iterations} iterations...\n")

    for i in range(iterations):
        t_start = time.perf_counter()
        first_token_time = None
        token_count = 0
        chunks = []

        for token in provider.chat_stream(user_query, system_prompt=base_sys_prompt):
            if not token:
                continue
            if first_token_time is None and token.strip():
                first_token_time = time.perf_counter()
            token_count += 1
            chunks.append(token)

        t_end = time.perf_counter()
        ttft_ms = round((first_token_time - t_start) * 1000, 2) if first_token_time else 0.0
        total_ms = round((t_end - t_start) * 1000, 2)
        ttft_list.append(ttft_ms)
        total_time_list.append(total_ms)
        tokens_count_list.append(token_count)
        first_chunk_text_list.append("".join(chunks[:3]).strip())

        tps = round(token_count / ((total_ms - ttft_ms) / 1000), 2) if (total_ms > ttft_ms and (total_ms - ttft_ms) > 0) else 0.0
        print(f"  [Run {i+1}] TTFT: {ttft_ms:7.2f} ms | Total: {total_ms:7.2f} ms | Tokens: {token_count:3d} | Speed: {tps:5.1f} tps")

    results["cold_ttft_ms"] = ttft_list[0] if ttft_list else 0.0
    results["warm_avg_ttft_ms"] = round(sum(ttft_list[1:]) / len(ttft_list[1:]), 2) if len(ttft_list) > 1 else ttft_list[0]
    results["avg_total_stream_ms"] = round(sum(total_time_list) / len(total_time_list), 2)
    results["avg_token_count"] = round(sum(tokens_count_list) / len(tokens_count_list), 1)

    avg_gen_time_sec = (results["avg_total_stream_ms"] - results["warm_avg_ttft_ms"]) / 1000.0
    results["avg_tokens_per_sec"] = round(results["avg_token_count"] / avg_gen_time_sec, 2) if avg_gen_time_sec > 0 else 0.0

    print("\n--------------------------------------------------------")
    print("            LLM LATENCY PROFILING SUMMARY")
    print("--------------------------------------------------------")
    print(f" Model Used                     : {results['persona_model']}")
    print(f" Cold TTFT                      : {results['cold_ttft_ms']:8.2f} ms")
    print(f" Warm TTFT (Avg)                : {results['warm_avg_ttft_ms']:8.2f} ms")
    print(f" Average Total Stream Time      : {results['avg_total_stream_ms']:8.2f} ms")
    print(f" Average Token Count            : {results['avg_token_count']:8.1f} tokens")
    print(f" Generation Throughput          : {results['avg_tokens_per_sec']:8.2f} tokens/sec")
    print(f" Memory Context Build Latency   : {results['memory_context_ms']:8.3f} ms")
    print("========================================================\n")

    return results

if __name__ == "__main__":
    profile_llm_latency(iterations=5)
