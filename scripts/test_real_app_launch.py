# scripts/test_real_app_launch.py
# Phase 2 Real Application Launch & Window Verification

import sys
import os
import time
import subprocess
import psutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from actions.app_registry import resolve_app
from actions.open_app import open_app_structured, _is_process_running

def get_process_pids(process_names: list[str]) -> set[int]:
    """Returns the set of active PIDs matching any of the process names."""
    pids = set()
    targets = [t.lower().replace(".exe", "").strip() for t in process_names if t]
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower().replace(".exe", "").strip()
            for t in targets:
                if t and (t == pname or t in pname):
                    pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return pids

def verify_window_present(process_names: list[str], timeout_sec: float = 3.0) -> bool:
    """Verifies if a visible window exists for any of the target process names."""
    import ctypes
    user32 = ctypes.windll.user32
    targets = [t.lower().replace(".exe", "").strip() for t in process_names if t]
    start_t = time.time()

    while time.time() - start_t < timeout_sec:
        found = []
        def enum_win(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    for t in targets:
                        if t in title:
                            found.append(hwnd)
                            return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_win), 0)
        if found:
            return True
        time.sleep(0.3)
    return False

def test_app_launch(app_query: str, expected_names: list[str]):
    print(f"\n[-] Testing App: '{app_query}'")
    
    # 1. Resolve application
    entry = resolve_app(app_query)
    assert entry is not None, f"Could not resolve application for '{app_query}'"
    print(f"  [+] 1. Resolved: '{entry['name']}' (Category: {entry.get('category')})")

    executables = entry.get("executables", [])
    process_names = entry.get("process_names", executables) + expected_names
    
    # 2. Record pre-existing state & PIDs
    pre_pids = get_process_pids(process_names)
    was_already_running = len(pre_pids) > 0
    print(f"  [+] 2. Pre-existing state: running={was_already_running} (PIDs: {pre_pids})")

    # 3. Launch application via JARVIS action
    t0 = time.time()
    res = open_app_structured(app_query)
    launch_latency = int((time.time() - t0) * 1000)
    print(f"  [+] 3. Launch action result: {res.get('message')} ({launch_latency}ms)")
    assert res.get("success"), f"open_app_structured failed for '{app_query}': {res.get('message')}"

    # Wait briefly for process to settle
    time.sleep(1.5)

    # 4. Verify process creation / presence
    post_pids = get_process_pids(process_names)
    assert len(post_pids) > 0, f"No process found for '{app_query}' after launch!"
    new_pids = post_pids - pre_pids
    
    if was_already_running:
        print(f"  [+] 4. Process Verified: Existing instance focused/maintained (PID: {list(pre_pids)[0]})")
    else:
        assert len(new_pids) > 0, f"Expected new process instance, but no new PIDs detected!"
        print(f"  [+] 4. Process Verified: New instance spawned with PID(s): {new_pids}")

    # 5. Verify window presence where possible
    has_window = verify_window_present(process_names, timeout_sec=2.0)
    print(f"  [+] 5. Window Presence Verified: {has_window}")

    # 6. Verify process belongs to requested application
    verified_pids = new_pids if new_pids else post_pids
    for p in verified_pids:
        try:
            proc = psutil.Process(p)
            proc_name = proc.name().lower()
            assert any(t.lower().replace(".exe", "") in proc_name for t in process_names), \
                f"PID {p} ({proc_name}) does not match expected targets: {process_names}"
            print(f"  [+] 6. Process Identity Verified: PID {p} -> '{proc.name()}'")
            break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 7. Strict Cleanup: ONLY terminate NEW instances created by this test
    # NEVER terminate pre-existing processes (especially user IDE / user apps)
    if new_pids:
        print(f"  [-] Cleaning up ONLY test-spawned PIDs: {new_pids}")
        for pid in new_pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=2.0)
                print(f"  [+] Cleanly terminated test PID {pid}")
            except Exception as e:
                print(f"  [!] Note during cleanup for PID {pid}: {e}")
    else:
        print(f"  [-] No test-spawned processes to clean up (pre-existing user instance preserved).")

    print(f"  [✅] '{app_query}' launch verification PASSED.")
    return True

def run_real_app_launch_tests():
    print("=" * 65)
    print("      PHASE 2: REAL APPLICATION LAUNCH VERIFICATION")
    print("=" * 65)

    test_targets = [
        ("notepad", ["notepad.exe"]),
        ("calculator", ["CalculatorApp.exe", "calc.exe"]),
        ("chrome", ["chrome.exe"]),
        ("antigravity ide", ["Antigravity IDE.exe", "Antigravity.exe"])
    ]

    all_passed = True
    for app_name, exes in test_targets:
        try:
            success = test_app_launch(app_name, exes)
            if not success:
                all_passed = False
        except Exception as err:
            print(f"  [❌] Failed on '{app_name}': {err}")
            all_passed = False

    print("\n" + "=" * 65)
    if all_passed:
        print("REAL APPLICATION LAUNCH VERIFICATION: ALL 4 APPS PASSED")
    else:
        print("REAL APPLICATION LAUNCH VERIFICATION: FAILED")
    print("=" * 65)
    return all_passed

if __name__ == "__main__":
    success = run_real_app_launch_tests()
    sys.exit(0 if success else 1)
