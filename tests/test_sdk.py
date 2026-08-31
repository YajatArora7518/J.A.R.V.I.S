# tests/test_sdk.py
# Python SDK Method Integration Test

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from jarvis_api import JarvisAPI

def test_sdk_methods() -> tuple[bool, str]:
    try:
        jarvis = JarvisAPI()

        # 1. Status
        st = jarvis.get_status()
        if not st.version:
            return False, "get_status returned invalid model"

        # 2. List tools
        tools = jarvis.list_tools()
        if not tools:
            return False, "list_tools returned empty list"

        # 3. Memory
        jarvis.remember("sdk_test_key", "sdk_test_val", category="notes")
        mem_val = jarvis.get_memory("notes", "sdk_test_key")
        if mem_val != "sdk_test_val":
            return False, f"Memory check failed: expected 'sdk_test_val', got '{mem_val}'"
        jarvis.delete_memory("notes", "sdk_test_key")

        # 4. Call Tool
        res = jarvis.call_tool("web_search", {"query": "test"})
        if not res.success:
            return False, f"call_tool returned error: {res.message}"

        return True, "SDK status, list_tools, memory, and call_tool verified"
    except Exception as e:
        return False, f"SDK test exception: {e}"

if __name__ == "__main__":
    passed, msg = test_sdk_methods()
    print(f"SDK Test: {'PASS' if passed else 'FAIL'} - {msg}")
