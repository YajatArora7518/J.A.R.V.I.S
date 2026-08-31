# examples/rest_example.py
# HTTP REST Client Example using Python requests

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"
API_KEY  = "default-jarvis-key"

HEADERS  = {
    "X-JARVIS-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

def main():
    print("========================================")
    print("     JARVIS REST API CLIENT DEMO")
    print("========================================")

    # 1. Health Check (Public)
    res = requests.get(f"{BASE_URL}/health")
    print(f"[*] Health Check: {res.status_code} -> {res.json()}")

    # 2. System Status (Authenticated)
    res = requests.get(f"{BASE_URL}/status", headers=HEADERS)
    print(f"[*] System Status: {res.status_code} -> {res.json().get('status')}")

    # 3. List Tools
    res = requests.get(f"{BASE_URL}/tools", headers=HEADERS)
    tools = res.json().get("tools", [])
    print(f"[*] Registered Tools ({len(tools)} tools returned)")

    # 4. Post Execute Command
    res = requests.post(f"{BASE_URL}/execute", headers=HEADERS, json={"command": "Open Chrome"})
    print(f"[*] Execute Command Output: {res.json()}")

    # 5. Direct Tool Call
    res = requests.post(f"{BASE_URL}/tool", headers=HEADERS, json={"tool": "computer_settings", "arguments": {"action": "volume_set", "value": "45"}})
    print(f"[*] Tool Call Output: {res.json()}")

if __name__ == "__main__":
    main()
