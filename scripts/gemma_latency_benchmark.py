# scripts/gemma_latency_benchmark.py
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.ollama_provider import generate_ollama_response, OllamaProvider

def benchmark_gemma():
    print("==================================================")
    print("      OLLAMA 3-RUN LATENCY BENCHMARK")
    print("==================================================")
    
    provider = OllamaProvider()
    latencies_struct = []
    latencies_persona = []

    prompts = [
        "open calculator",
        "what is my cpu usage",
        "send WhatsApp message to Rahul saying hi"
    ]
    allowed_tools = ["open_app", "cpu_info", "whatsapp_send_message", "computer_settings"]

    print("\n--- TEST 1: Structured Tool Proposal (gemma4:12b) ---")
    for idx, p in enumerate(prompts, 1):
        t0 = time.time()
        res = provider.generate_structured_action(p, allowed_tools=allowed_tools)
        dt = time.time() - t0
        latencies_struct.append(dt)
        print(f"Run {idx} | Latency: {dt:.2f}s | Action: {res.get('action_proposal')}")
        time.sleep(0.5)

    print("\n--- TEST 2: Conversational Chat Response (fotiecodes/jarvis:latest) ---")
    for idx, p in enumerate(prompts, 1):
        t0 = time.time()
        res = provider.chat(p, model=provider.persona_model)
        dt = time.time() - t0
        latencies_persona.append(dt)
        print(f"Run {idx} | Latency: {dt:.2f}s | Text: {res.get('text', '')[:60]}...")
        time.sleep(0.5)

    avg_struct = sum(latencies_struct) / len(latencies_struct)
    avg_persona = sum(latencies_persona) / len(latencies_persona)

    print("\n==================================================")
    print(f" Structured Tool Planning Avg Latency : {avg_struct:.2f}s")
    print(f" Persona Dialogue Chat Avg Latency     : {avg_persona:.2f}s")
    print("==================================================")

if __name__ == "__main__":
    benchmark_gemma()
