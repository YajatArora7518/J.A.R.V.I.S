# examples/api_usage.py
# Comprehensive JARVIS Python SDK Usage Example

import sys
from pathlib import Path

# Add parent directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from jarvis_api import JarvisAPI

def main():
    print("========================================")
    print("     JARVIS PYTHON SDK DEMO")
    print("========================================")

    # 1. Initialize SDK
    jarvis = JarvisAPI()

    # 2. Get System Status & Health
    status = jarvis.get_status()
    print(f"[*] JARVIS Status: {status.status} (v{status.version})")
    print(f"[*] All Systems Operational: {status.all_systems_operational}")

    # 3. List Registered Tools
    tools = jarvis.list_tools()
    print(f"[*] Registered Tools ({len(tools)}):")
    for t in tools[:5]:
        print(f"  - {t['name']} [{t['risk_level']}]: {t['description']}")

    # 4. Save & Retrieve Memory
    print("\n[*] Testing Long-Term Memory...")
    jarvis.remember("favorite_framework", "FastAPI", category="preferences")
    fav = jarvis.get_memory("preferences", "favorite_framework")
    print(f"  Retrieved Preference: favorite_framework = '{fav}'")

    # 5. Execute Natural Language Intent
    print("\n[*] Executing natural language command: 'open notepad'")
    result = jarvis.execute("open notepad")
    print(f"  Result: {result.message} (Verified: {result.verification.get('verified')})")

    # 6. Direct Tool Call
    print("\n[*] Direct Tool Call: computer_settings -> volume_set (50%)")
    vol_res = jarvis.call_tool("computer_settings", {"action": "volume_set", "value": 50})
    print(f"  Result: {vol_res.message}")

    # 7. Close Notepad
    print("\n[*] Closing Notepad...")
    close_res = jarvis.call_tool("computer_settings", {"action": "close_app", "value": "notepad"})
    print(f"  Result: {close_res.message}")

    print("\n[OK] JARVIS Python SDK Demo completed successfully.")

if __name__ == "__main__":
    main()
