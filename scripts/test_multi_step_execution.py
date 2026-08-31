# scripts/test_multi_step_execution.py
# Verification of Compound Multi-Step System Control Requests

import sys
import os
import shutil
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from actions.file_controller import file_controller
from actions.script_executor import create_script, run_script, resolve_safe_path

def test_multi_step_execution():
    print("========================================================")
    print("     JARVIS MULTI-STEP COMPOUND EXECUTION AUDIT")
    print("========================================================\n")

    desktop_path = str(Path.home() / "Desktop")
    test_folder = os.path.join(desktop_path, "JARVIS_TEST")

    # Step 1: Create Directory on Desktop
    print("[Step 1/4] Creating Directory 'JARVIS_TEST' on Desktop...")
    res_dir = file_controller({"action": "create_folder", "path": desktop_path, "name": "JARVIS_TEST"})
    dir_exists = os.path.exists(test_folder)
    print(f"  Result: {res_dir} | Directory Exists={dir_exists}")

    # Step 2: Create Python script in JARVIS_TEST that prints system RAM
    print("\n[Step 2/4] Creating Python Script 'ram_info.py' inside 'JARVIS_TEST'...")
    script_content = "import psutil\nram = psutil.virtual_memory()\nprint(f'System RAM Total: {round(ram.total/(1024**3),2)} GB, Available: {round(ram.available/(1024**3),2)} GB')"
    res_scr = create_script(script_content, "py", filename="ram_info.py", target_dir=test_folder)
    scr_exists = res_scr.get("success", False) and os.path.exists(res_scr["target"])
    print(f"  Result: {res_scr.get('message')} | Script Exists={scr_exists}")

    # Step 3: Execute Python script & capture output
    print("\n[Step 3/4] Executing Python Script 'ram_info.py'...")
    res_exec = run_script(res_scr["target"], timeout=10)
    stdout_ok = "System RAM Total:" in res_exec.get("stdout", "")
    exit_zero = res_exec.get("exit_code") == 0
    print(f"  Result: stdout='{res_exec.get('stdout')}', exit_code={res_exec.get('exit_code')}")

    # Step 4: Cleanup temporary test artifacts
    print("\n[Step 4/4] Cleaning up 'JARVIS_TEST' folder...")
    try:
        shutil.rmtree(test_folder, ignore_errors=True)
        print("  Result: JARVIS_TEST folder cleaned up.")
    except Exception as ex:
        print(f"  Cleanup warning: {ex}")

    success = dir_exists and scr_exists and stdout_ok and exit_zero
    print("\n========================================================")
    print(f" MULTI-STEP COMPOUND EXECUTION AUDIT: {'PASS' if success else 'FAIL'}")
    print("========================================================\n")

    return success

if __name__ == "__main__":
    ok = test_multi_step_execution()
    sys.exit(0 if ok else 1)
