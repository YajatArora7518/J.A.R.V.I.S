# scripts/test_ollama_models.py
import sys
import os
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.ollama_provider import generate_ollama_response, is_ollama_available, check_ollama_health

def run_tests():
    print("==================================================")
    print("        OLLAMA REAL LOCAL INFERENCE TEST")
    print("==================================================")
    
    print("\n1. Checking Ollama Server Readiness...")
    health = check_ollama_health("http://localhost:11434")
    print("   Health Check:", health)
    
    print("\n2. Testing Conversational Persona Model: 'fotiecodes/jarvis'...")
    t0 = time.time()
    r1 = generate_ollama_response("Jarvis, who are you?", model="fotiecodes/jarvis")
    dt1 = time.time() - t0
    print(f"   Success : {r1.get('success')}")
    print(f"   Model   : {r1.get('model_used')}")
    print(f"   Response: {r1.get('text')}")
    print(f"   Latency : {dt1:.2f} seconds")
    
    print("\n3. Testing Structured Tool Model: 'gemma4:12b'...")
    t0 = time.time()
    r2 = generate_ollama_response("Select the appropriate tool for launching Notepad.", model="gemma4:12b")
    dt2 = time.time() - t0
    print(f"   Success : {r2.get('success')}")
    print(f"   Model   : {r2.get('model_used')}")
    print(f"   Response: {r2.get('text')}")
    print(f"   Latency : {dt2:.2f} seconds")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
