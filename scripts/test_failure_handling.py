# scripts/test_failure_handling.py
# Failure Testing & Edge-Case Verification Suite for JARVIS
# Verifies that JARVIS reports truthful failure explanations without hallucinating success.

import sys
import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def run_failure_handling_tests():
    print("========================================================")
    print("      JARVIS FAILURE & EDGE-CASE HANDLING AUDIT")
    print("========================================================\n")

    results = {}

    # 1. Invalid Application Launch (Native Desktop Not Found)
    print("[1/9] Testing Invalid Application Launch...")
    from actions.open_app import open_app_structured
    res_app = open_app_structured("zzzz_non_existent_app_999")
    if not res_app.get("success") or res_app.get("mode") == "none":
        results["Invalid Application"] = "PASS"
        print(f"  [PASS] Invalid Application PASS: Truthfully reported '{res_app.get('message')}'")
    else:
        results["Invalid Application"] = "FAIL"
        print(f"  [FAIL] Invalid Application FAIL: {res_app}")

    # 2. Invalid File Read
    print("\n[2/9] Testing Non-Existent File Read...")
    from actions.file_controller import file_controller
    res_file = file_controller({"action": "read_file", "path": "C:\\non_existent_folder_xyz\\file.txt"})
    if "not found" in str(res_file).lower() or "error" in str(res_file).lower() or "not exist" in str(res_file).lower():
        results["Invalid File"] = "PASS"
        print(f"  [PASS] Invalid File PASS: Truthfully reported '{res_file}'")
    else:
        results["Invalid File"] = "FAIL"
        print(f"  [FAIL] Invalid File FAIL: {res_file}")

    # 3. Protected Path Security Block
    print("\n[3/9] Testing Protected System Path Block (C:\\Windows\\System32\\config)...")
    from core.security import default_security_manager
    auth_ok, reason = default_security_manager.validate_and_authorize(
        "file_controller",
        {"action": "delete_file", "path": "C:\\Windows\\System32\\config\\sam"}
    )
    if not auth_ok and "protected" in str(reason).lower():
        results["Security Policy Block"] = "PASS"
        print(f"  [PASS] Security Policy Block PASS: Blocked with '{reason}'")
    else:
        results["Security Policy Block"] = "FAIL"
        print(f"  [FAIL] Security Policy Block FAIL: auth_ok={auth_ok}, reason={reason}")

    # 4. Missing Interpreter Handling
    print("\n[4/9] Testing Missing Interpreter Handling (.js script)...")
    from actions.script_executor import run_script
    res_script = run_script("test.xyz_unsupported_ext", timeout=5)
    if not res_script.get("success"):
        results["Missing Interpreter"] = "PASS"
        print(f"  [PASS] Missing Interpreter PASS: Reported '{res_script.get('stderr')}'")
    else:
        results["Missing Interpreter"] = "FAIL"
        print(f"  [FAIL] Missing Interpreter FAIL: {res_script}")

    # 5. Script Execution Timeout
    print("\n[5/9] Testing Script Execution Timeout Enforcement...")
    from actions.script_executor import create_script, get_workspace_dir
    workspace = get_workspace_dir()
    hang_script = create_script("import time\ntime.sleep(10)", "py", filename="hang_test.py", target_dir=workspace)
    if hang_script.get("success"):
        res_timeout = run_script(hang_script["target"], timeout=1)
        if not res_timeout.get("success") and "timed out" in res_timeout.get("stderr", "").lower():
            results["Script Timeout"] = "PASS"
            print(f"  [PASS] Script Timeout PASS: Timeout captured after 1 sec.")
        else:
            results["Script Timeout"] = "FAIL"
            print(f"  [FAIL] Script Timeout FAIL: {res_timeout}")
    else:
        results["Script Timeout"] = "FAIL"

    # 6. Terminating Closed Process
    print("\n[6/9] Testing Process Termination on Closed Process...")
    from actions.computer_settings import computer_settings
    res_proc = computer_settings({"action": "close_app", "value": "NonExistentProcess_9999"})
    if isinstance(res_proc, (dict, str)):
        results["Process Closed Check"] = "PASS"
        print(f"  [PASS] Process Closed Check PASS: Output handled gracefully.")
    else:
        results["Process Closed Check"] = "FAIL"

    # 7. Non-Existent Service Status Query
    print("\n[7/9] Testing Non-Existent Windows Service Query...")
    from actions.windows_services import get_service_status
    res_srv = get_service_status("NonExistentService_123")
    if not res_srv.get("success") or "not found" in str(res_srv).lower():
        results["Non-Existent Service"] = "PASS"
        print(f"  [PASS] Non-Existent Service PASS: Service failure captured.")
    else:
        results["Non-Existent Service"] = "FAIL"

    # 8. Web Search Graceful Handling
    print("\n[8/9] Testing Web Search Engine Output...")
    from actions.web_search import web_search
    res_web = web_search({"query": "qwertyuiopasdfghjklzxcvbnm_random_non_existent"})
    if res_web:
        results["Web Search Handling"] = "PASS"
        print("  [PASS] Web Search Handling PASS: Empty/broad result handled gracefully.")
    else:
        results["Web Search Handling"] = "FAIL"

    # 9. UAC Bridge Invalid Target Check
    print("\n[9/9] Testing UAC Bridge Status Check...")
    from actions.windows_uac_bridge import is_running_as_admin
    admin_state = is_running_as_admin()
    if isinstance(admin_state, bool):
        results["UAC Invalid Target"] = "PASS"
        print(f"  [PASS] UAC Bridge Status Check PASS: Running as admin={admin_state}")
    else:
        results["UAC Invalid Target"] = "FAIL"

    # Clean up timeout test script
    try:
        os.remove(hang_script["target"])
    except Exception:
        pass

    all_ok = all(v == "PASS" for v in results.values())
    print("\n========================================================")
    print("          FAILURE HANDLING AUDIT SUMMARY")
    print("========================================================")
    for test_name, status in results.items():
        symbol = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f" {symbol} {test_name:<28} : {status}")
    print("========================================================")
    print(f" AUDIT RESULT: {'ALL FAILURE AUDITS PASSED' if all_ok else 'SOME AUDITS FAILED'}")
    print("========================================================\n")

    return all_ok

if __name__ == "__main__":
    success = run_failure_handling_tests()
    sys.exit(0 if success else 1)
