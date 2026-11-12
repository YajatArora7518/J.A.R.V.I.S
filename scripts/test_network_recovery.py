# scripts/test_network_recovery.py
# Phase 3C: Network Loss & Local Autonomy Verification Test

import sys
import os
import time
import socket
from pathlib import Path
from unittest.mock import patch

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.register_tools import default_tool_registry
from core.runtime_supervisor import get_runtime_supervisor, SubsystemState
from memory.memory_manager import load_memory, save_memory

def run_network_recovery_test():
    print("=" * 65, flush=True)
    print("      PHASE 3C: NETWORK LOSS & LOCAL AUTONOMY TEST", flush=True)
    print("=" * 65, flush=True)

    supervisor = get_runtime_supervisor()

    # 1. Simulate WAN Outage: Block external socket connections
    print("\n[-] STEP 1: Simulating WAN Outage (Local Loopback 127.0.0.1 Allowed)", flush=True)
    
    orig_connect = socket.socket.connect

    def mock_socket_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # Allow loopback/localhost connections so local Ollama & local IPC work
        if host in ("127.0.0.1", "localhost", "::1"):
            return orig_connect(self, address)
        raise socket.error("Network unreachable (Simulated WAN outage)")

    with patch.object(socket.socket, "connect", side_effect=mock_socket_connect):
        # Cloud provider should be marked OFFLINE
        supervisor.record_failure(
            "CLOUD_PROVIDER",
            offline=True,
            error_msg="Simulated WAN disconnection: DNS/Socket unreachable",
            category="WAN_OUTAGE"
        )
        cloud_sub = supervisor.get_subsystem("CLOUD_PROVIDER")
        assert cloud_sub.state == SubsystemState.OFFLINE, f"Expected OFFLINE, got {cloud_sub.state}"
        print(f"  [+] Cloud subsystem transitioned to {cloud_sub.state} (Error: {cloud_sub.error_category})", flush=True)

        # 2. Verify Local Autonomy during WAN outage
        print("\n[-] STEP 2: Verifying Local Tools & Memory Function Offline", flush=True)
        # Tool 1: System info tool
        sys_tool = default_tool_registry.get_tool("system_info")
        assert sys_tool is not None, "system_info tool missing!"
        sys_res = sys_tool.execute({})
        assert sys_res.success is True, f"Local tool execution failed during WAN outage: {sys_res.error}"
        print(f"  [+] Local tool 'system_info' executed offline: CPU {sys_res.data.get('cpu_percent')}%", flush=True)

        # Tool 2: Local persistent memory operations
        from memory.memory_manager import update_memory, save_memory
        update_memory("preferences", "test_offline", "verified")
        updated_mem = load_memory()
        assert updated_mem.get("preferences", {}).get("test_offline", {}).get("value") == "verified", "Memory save failed offline!"
        print(f"  [+] Local memory save/recall verified offline.", flush=True)

        # Tool 3: Active windows inspection
        win_tool = default_tool_registry.get_tool("active_windows_info")
        assert win_tool is not None, "active_windows_info missing!"
        win_res = win_tool.execute({})
        assert win_res.success is True, f"active_windows_info failed offline: {win_res.error}"
        print(f"  [+] Local active windows tool verified offline.", flush=True)

        # Cleanup memory
        if "test_offline" in updated_mem.get("preferences", {}):
            del updated_mem["preferences"]["test_offline"]
            save_memory(updated_mem)

    # 3. Simulate WAN Recovery: Cloud Capability Restored
    print("\n[-] STEP 3: Simulating WAN Recovery & Cloud Restoration", flush=True)
    cloud_sub.next_recovery_due = time.time() - 1.0  # Elapse backoff
    healing_res = supervisor.trigger_self_healing_pass()
    print(f"  [+] Self-healing pass result for CLOUD_PROVIDER: {healing_res.get('CLOUD_PROVIDER')}", flush=True)
    assert cloud_sub.state == SubsystemState.HEALTHY, f"Cloud provider not restored to HEALTHY: {cloud_sub.state}"
    print(f"  [+] Cloud provider restored to {cloud_sub.state} without restarting JARVIS.", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3C NETWORK LOSS & LOCAL AUTONOMY TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_network_recovery_test()
    sys.exit(0 if success else 1)
