# scripts/system_control_test.py
# Section 22 — Independent Windows System Control Verification Runner (No LLM dependency)

import sys
import os
import time
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def test_system_control():
    print("=========================================")
    print("  WINDOWS SYSTEM CONTROL VERIFICATION")
    print("=========================================")

    from core.register_tools import initialize_all_tools
    from core.tool_registry import default_tool_registry
    from core.verification import verify_app_launched, verify_process_closed
    import psutil

    initialize_all_tools()
    passed = 0
    total = 7

    # 1. System Telemetry - CPU Info
    res_cpu = default_tool_registry.execute_tool("cpu_info", {})
    if res_cpu.success and "CPU:" in str(res_cpu.message):
        print(f" [PASS] 1. CPU Telemetry      : {res_cpu.message}")
        passed += 1
    else:
        print(f" [FAIL] 1. CPU Telemetry      : {res_cpu.message}")

    # 2. System Telemetry - RAM Info
    res_ram = default_tool_registry.execute_tool("memory_info", {})
    if res_ram.success and "RAM:" in str(res_ram.message):
        print(f" [PASS] 2. RAM Telemetry      : {res_ram.message}")
        passed += 1
    else:
        print(f" [FAIL] 2. RAM Telemetry      : {res_ram.message}")

    # 3. System Telemetry - Battery Info
    res_bat = default_tool_registry.execute_tool("battery_info", {})
    if res_bat.success and "Battery:" in str(res_bat.message):
        print(f" [PASS] 3. Battery Telemetry  : {res_bat.message}")
        passed += 1
    else:
        print(f" [FAIL] 3. Battery Telemetry  : {res_bat.message}")

    # 4. System Telemetry - Disk Info
    res_disk = default_tool_registry.execute_tool("disk_info", {})
    if res_disk.success and ("Storage Drives:" in str(res_disk.message) or "Disk:" in str(res_disk.message)):
        print(f" [PASS] 4. Disk Telemetry     : {res_disk.message}")
        passed += 1
    else:
        print(f" [FAIL] 4. Disk Telemetry     : {res_disk.message}")

    # 5. Computer Settings - Volume Action
    res_vol = default_tool_registry.execute_tool("computer_settings", {"action": "volume_set", "value": 50})
    if res_vol.success:
        print(f" [PASS] 5. Volume Control     : {res_vol.message}")
        passed += 1
    else:
        print(f" [FAIL] 5. Volume Control     : {res_vol.message}")

    # 6. Application Control & OS Verification - Calculator
    res_calc = default_tool_registry.execute_tool("open_app", {"app_name": "calculator"})
    verif_calc = verify_app_launched("Calculator", timeout=3.0)
    if res_calc.success and verif_calc.get("verified"):
        print(f" [PASS] 6. Application Launch : {res_calc.message} (PID: {verif_calc.get('pid')})")
        passed += 1
    else:
        print(f" [FAIL] 6. Application Launch : {res_calc.message}")

    # 7. Safe System Control (Screenshot Capture)
    res_pwr = default_tool_registry.execute_tool("computer_control", {"action": "screenshot", "path": "tests/test_scratch/sys_test.png"})
    if res_pwr.success:
        print(f" [PASS] 7. System Screenshot   : {res_pwr.message}")
        passed += 1
    else:
        print(f" [FAIL] 7. System Screenshot   : {res_pwr.message}")

    print("=========================================")
    print(f"  SYSTEM CONTROL SCORE: {passed} / {total} PASSED")
    print("=========================================\n")

if __name__ == "__main__":
    test_system_control()
