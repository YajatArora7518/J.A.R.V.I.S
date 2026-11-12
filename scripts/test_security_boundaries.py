# scripts/test_security_boundaries.py
# Phase 2 Security Boundaries & User Data Protection Test

import sys
import os
import shutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.security import SecurityManager, RiskLevel

def run_security_boundary_tests():
    print("=" * 65)
    print("      PHASE 2: SECURITY BOUNDARY & DATA PROTECTION TEST")
    print("=" * 65)

    # 1. Ensure isolated test workspace
    test_workspace = REPO_DIR / "scratch" / "phase2_test_workspace"
    test_workspace.mkdir(parents=True, exist_ok=True)
    print(f"[-] Isolated Test Workspace: {test_workspace}")

    # Safety assertion: Workspace MUST NOT be User root or system directory
    bad_roots = [
        Path(os.environ.get("USERPROFILE", "C:\\Users\\Default")),
        Path(os.environ.get("SystemRoot", "C:\\Windows")),
        Path("C:\\Windows\\System32")
    ]
    for br in bad_roots:
        assert test_workspace.resolve() != br.resolve(), "CRITICAL: Test workspace points to real user/system root!"
    print("[+] Test workspace isolation confirmed (Safe isolated sandbox).")

    sec = SecurityManager()

    # 2. Test LOW-Risk Action
    print("\n[-] STEP 1: Testing LOW-Risk Action Authorization...")
    low_risk = sec.classify_risk("system_info", {})
    assert low_risk == RiskLevel.LOW, f"Expected LOW, got {low_risk}"
    auth, reason = sec.validate_and_authorize("system_info", {})
    assert auth is True, f"LOW risk action should be authorized immediately, reason: {reason}"
    print("  [+] LOW-Risk action ('system_info') authorized without blocking prompt.")

    # 3. Test MEDIUM-Risk Action
    print("\n[-] STEP 2: Testing MEDIUM-Risk Action Classification...")
    med_risk = sec.classify_risk("open_app", {"app_name": "notepad"})
    assert med_risk == RiskLevel.MEDIUM, f"Expected MEDIUM, got {med_risk}"
    auth, reason = sec.validate_and_authorize("open_app", {"app_name": "notepad"})
    assert auth is True, f"MEDIUM risk action should be authorized safely: {reason}"
    print("  [+] MEDIUM-Risk action ('open_app') classified and authorized.")

    # 4. Test HIGH-Risk Action: Confirmation Required BEFORE Execution
    print("\n[-] STEP 3: Testing HIGH-Risk Pre-Execution Confirmation...")
    mock_file = test_workspace / "mock_target_file.txt"
    mock_file.write_text("Mock test payload - safe for deletion", encoding="utf-8")
    assert mock_file.exists(), "Failed to create isolated mock file"

    high_params = {"action": "delete_file", "path": str(mock_file)}
    high_risk = sec.classify_risk("file_controller", high_params)
    assert high_risk == RiskLevel.HIGH, f"Expected HIGH, got {high_risk}"

    # Scenario A: User DENIES confirmation
    print("  [-] Scenario A: User REJECTS confirmation prompt")
    sec.set_confirmation_callback(lambda prompt: False)
    auth_denied, reason = sec.validate_and_authorize("file_controller", high_params)
    assert auth_denied is False, "HIGH risk action proceeded despite user denial!"
    assert mock_file.exists(), "Target was deleted despite user denial!"
    print(f"  [+] Denied correctly: {reason}")
    print("  [+] Verified: Mock target file was NOT deleted.")

    # Scenario B: User ACCEPTS confirmation
    print("  [-] Scenario B: User CONFIRMS action")
    sec.set_confirmation_callback(lambda prompt: True)
    auth_approved, reason = sec.validate_and_authorize("file_controller", high_params)
    assert auth_approved is True, f"HIGH risk action failed despite confirmation: {reason}"
    print("  [+] Authorized following explicit confirmation.")

    # 5. Test Protected System Directory Boundary (Hard Gate)
    print("\n[-] STEP 4: Testing Protected System Path Boundary Enforcement...")
    forbidden_targets = [
        "C:\\Windows\\System32\\kernel32.dll",
        "C:\\Windows\\system32\\config\\SAM",
        "C:\\Windows\\explorer.exe"
    ]
    for target in forbidden_targets:
        params = {"action": "delete_file", "path": target}
        # Even if user callback says TRUE, security manager MUST strictly reject system directory ops
        sec.set_confirmation_callback(lambda p: True)
        auth_blocked, block_reason = sec.validate_and_authorize("file_controller", params)
        assert auth_blocked is False, f"FAILED TO BLOCK operation on protected path: {target}"
        assert "strictly forbidden" in block_reason.lower() or "blocked" in block_reason.lower()
        print(f"  [+] Strictly blocked operation on '{target}': {block_reason}")

    # 6. Test CRITICAL-Risk Action Classification
    print("\n[-] STEP 5: Testing CRITICAL-Risk Action Classification...")
    crit_actions = ["format_drive", "delete_all", "disable_defender", "disable_firewall"]
    for act in crit_actions:
        r = sec.classify_risk("system_controller", {"action": act})
        assert r == RiskLevel.CRITICAL, f"Action '{act}' should be CRITICAL, got {r}"
        print(f"  [+] Action '{act}' -> CRITICAL (Verified)")

    # 7. Clean up isolated test files
    if mock_file.exists():
        mock_file.unlink()
    print("\n[-] Isolated mock test artifacts cleaned up.")

    print("\n" + "=" * 65)
    print("PHASE 2 SECURITY BOUNDARY TEST: PASSED")
    print("=" * 65)
    return True

if __name__ == "__main__":
    success = run_security_boundary_tests()
    sys.exit(0 if success else 1)
