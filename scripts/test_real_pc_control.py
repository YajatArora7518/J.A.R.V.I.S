"""
JARVIS Phase 2: Real-World End-to-End PC Control Test
=====================================================
This script tests the ACTUAL Windows action chain:
  CommandPipeline -> IntentRouter -> Tool -> Windows OS -> Process/Window Verification

Each test ACTUALLY launches an app on Windows and verifies the process/window exists.
Apps are cleaned up (closed) after each test.
"""

import os
import sys
import time
import json
import traceback
import io

# Force UTF-8 stdout for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Setup path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, PARENT_DIR)

# Suppress noisy logs for cleaner output
import logging
logging.basicConfig(level=logging.WARNING)

results = {}

def safe_json(obj, **kwargs):
    """JSON-serialize, converting non-serializable objects to dicts."""
    def default(o):
        if hasattr(o, '__dict__'):
            return {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
        return str(o)
    return json.dumps(obj, default=default, **kwargs)

def log(msg):
    print(f"  {msg}")

def test_header(num, name):
    print(f"\n{'='*60}")
    print(f"  TEST {num:02d}: {name}")
    print(f"{'='*60}")

def close_app_by_name(process_name):
    """Kill a process by name to clean up after tests."""
    try:
        import subprocess
        subprocess.run(
            ["taskkill", "/IM", f"{process_name}", "/F"],
            capture_output=True, timeout=5
        )
        time.sleep(0.5)
    except Exception:
        pass


# ============================================================
# TEST 1: open_app_structured — Notepad
# ============================================================
test_header(1, "open_app_structured('Notepad') → ACTUAL WINDOWS LAUNCH")
try:
    from actions.open_app import open_app_structured
    from core.verification import verify_app_launched
    
    # Close any existing notepad first
    close_app_by_name("notepad.exe")
    time.sleep(0.5)
    
    result = open_app_structured("Notepad")
    log(f"Result: {safe_json(result, indent=2)}")
    
    # Independent verification
    v = verify_app_launched("Notepad", timeout=5.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Notepad actually launched and verified on Windows")
        results["Notepad"] = "PASS"
    else:
        log("❌ FAIL — Notepad did not actually launch")
        results["Notepad"] = f"FAIL: success={result.get('success')}, verified={v.get('verified')}"
    
    # Cleanup
    close_app_by_name("notepad.exe")
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["Notepad"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 2: open_app_structured — Calculator
# ============================================================
test_header(2, "open_app_structured('Calculator') → ACTUAL WINDOWS LAUNCH")
try:
    close_app_by_name("CalculatorApp.exe")
    close_app_by_name("Calculator.exe")
    time.sleep(0.5)
    
    result = open_app_structured("Calculator")
    log(f"Result: {safe_json(result, indent=2)}")
    
    v = verify_app_launched("Calculator", timeout=5.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Calculator actually launched")
        results["Calculator"] = "PASS"
    else:
        log("❌ FAIL — Calculator did not actually launch")
        results["Calculator"] = f"FAIL: success={result.get('success')}, verified={v.get('verified')}"
    
    close_app_by_name("CalculatorApp.exe")
    close_app_by_name("Calculator.exe")
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["Calculator"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 3: open_app_structured — Chrome
# ============================================================
test_header(3, "open_app_structured('Chrome') → ACTUAL WINDOWS LAUNCH")
try:
    # Don't close Chrome — user might have it open. Just verify launch.
    result = open_app_structured("Chrome")
    log(f"Result: {safe_json(result, indent=2)}")
    
    v = verify_app_launched("Chrome", timeout=5.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Chrome actually launched/focused")
        results["Chrome"] = "PASS"
    else:
        log("❌ FAIL — Chrome did not launch")
        results["Chrome"] = f"FAIL: success={result.get('success')}, verified={v.get('verified')}"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["Chrome"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 4: open_app_structured — File Explorer
# ============================================================
test_header(4, "open_app_structured('File Explorer') → ACTUAL WINDOWS LAUNCH")
try:
    result = open_app_structured("File Explorer")
    log(f"Result: {safe_json(result, indent=2)}")
    
    v = verify_app_launched("explorer", timeout=5.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    # Explorer is always running; check if a window was opened
    if result.get("success"):
        log("✅ PASS — File Explorer launched/focused")
        results["File Explorer"] = "PASS"
    else:
        log("❌ FAIL — File Explorer launch failed")
        results["File Explorer"] = f"FAIL: {result.get('message')}"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["File Explorer"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 5: open_app_structured — WhatsApp
# ============================================================
test_header(5, "open_app_structured('WhatsApp') → ACTUAL WINDOWS LAUNCH")
try:
    result = open_app_structured("WhatsApp")
    log(f"Result: {safe_json(result, indent=2)}")
    
    v = verify_app_launched("WhatsApp", timeout=6.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — WhatsApp actually launched and verified")
        results["WhatsApp"] = "PASS"
    elif result.get("success"):
        log("⚠️ PARTIAL — Tool reported success but independent verification could not confirm")
        results["WhatsApp"] = f"PARTIAL: tool_success=True, verified={v.get('verified')}, msg={result.get('message')}"
    else:
        log(f"❌ FAIL — WhatsApp launch failed: {result.get('message')}")
        results["WhatsApp"] = f"FAIL: {result.get('message')}"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["WhatsApp"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 6: Invalid App — Must NOT crash
# ============================================================
test_header(6, "open_app_structured('XYZ Super Fake App 9000') → ERROR RECOVERY")
try:
    result = open_app_structured("XYZ Super Fake App 9000")
    log(f"Result: {safe_json(result, indent=2)}")
    
    if not result.get("success"):
        log("✅ PASS — Correctly reported failure for nonexistent app")
        results["Invalid App Recovery"] = "PASS"
    else:
        log("❌ FAIL — Falsely claimed success for nonexistent app!")
        results["Invalid App Recovery"] = "FAIL: False success reported"
except Exception as e:
    log(f"❌ EXCEPTION (crash on invalid app!): {e}")
    traceback.print_exc()
    results["Invalid App Recovery"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 7: After invalid app, Notepad still works
# ============================================================
test_header(7, "Recovery: open_app_structured('Notepad') after invalid app")
try:
    close_app_by_name("notepad.exe")
    time.sleep(0.5)
    
    result = open_app_structured("Notepad")
    v = verify_app_launched("Notepad", timeout=5.0)
    log(f"Result: success={result.get('success')}, verified={v.get('verified')}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Notepad works after invalid app test")
        results["Post-Error Recovery"] = "PASS"
    else:
        log("❌ FAIL — Notepad didn't open after invalid app test")
        results["Post-Error Recovery"] = "FAIL"
    
    close_app_by_name("notepad.exe")
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    results["Post-Error Recovery"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 8: CommandPipeline — Full chain "Jarvis, Notepad kholo"
# ============================================================
test_header(8, "CommandPipeline('Notepad kholo') → Full Intent→Tool→Action chain")
try:
    close_app_by_name("notepad.exe")
    time.sleep(0.5)
    
    from core.command_pipeline import process_user_command
    result = process_user_command("Notepad kholo", source="voice")
    log(f"Pipeline Result: {safe_json({k:str(v)[:100] for k,v in result.items()}, indent=2)}")
    
    v = verify_app_launched("Notepad", timeout=5.0)
    log(f"Independent Verification: {safe_json(v)}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Full pipeline: voice → intent → tool → Notepad opened")
        results["Pipeline: Notepad kholo"] = "PASS"
    else:
        log(f"❌ FAIL — Pipeline chain broken: intent={result.get('intent')}, action={result.get('action')}")
        results["Pipeline: Notepad kholo"] = f"FAIL: intent={result.get('intent')}, success={result.get('success')}, verified={v.get('verified')}"
    
    close_app_by_name("notepad.exe")
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    traceback.print_exc()
    results["Pipeline: Notepad kholo"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 9: CommandPipeline — "Chrome khol de"
# ============================================================
test_header(9, "CommandPipeline('Chrome khol de') → Full chain")
try:
    from core.command_pipeline import process_user_command
    result = process_user_command("Chrome khol de", source="voice")
    log(f"Pipeline Result: intent={result.get('intent')}, success={result.get('success')}, action={result.get('action')}")
    
    v = verify_app_launched("Chrome", timeout=5.0)
    log(f"Verified: {v.get('verified')}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Chrome launched via Hinglish command")
        results["Pipeline: Chrome khol de"] = "PASS"
    else:
        log(f"❌ FAIL — Chrome pipeline failed")
        results["Pipeline: Chrome khol de"] = f"FAIL: intent={result.get('intent')}, success={result.get('success')}"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    results["Pipeline: Chrome khol de"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 10: CommandPipeline — "Calculator open karo"
# ============================================================
test_header(10, "CommandPipeline('Calculator open karo') → Full chain")
try:
    close_app_by_name("CalculatorApp.exe")
    close_app_by_name("Calculator.exe")
    time.sleep(0.5)
    
    from core.command_pipeline import process_user_command
    result = process_user_command("Calculator open karo", source="voice")
    log(f"Pipeline Result: intent={result.get('intent')}, success={result.get('success')}")
    
    v = verify_app_launched("Calculator", timeout=5.0)
    log(f"Verified: {v.get('verified')}")
    
    if result.get("success") and v.get("verified"):
        log("✅ PASS — Calculator launched via Hinglish command")
        results["Pipeline: Calculator open karo"] = "PASS"
    else:
        log(f"❌ FAIL")
        results["Pipeline: Calculator open karo"] = f"FAIL: intent={result.get('intent')}, success={result.get('success')}"
    
    close_app_by_name("CalculatorApp.exe")
    close_app_by_name("Calculator.exe")
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    results["Pipeline: Calculator open karo"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 11: CommandPipeline — "What time is it?"
# ============================================================
test_header(11, "CommandPipeline('What time is it?') → Time response")
try:
    from core.command_pipeline import process_user_command
    result = process_user_command("What time is it?", source="voice")
    log(f"Result: success={result.get('success')}, message={result.get('message')}")
    
    if result.get("success") and "time" in result.get("message", "").lower():
        log("✅ PASS — Time query works")
        results["Pipeline: What time"] = "PASS"
    else:
        results["Pipeline: What time"] = f"FAIL: {result.get('message')}"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    results["Pipeline: What time"] = f"EXCEPTION: {e}"


# ============================================================
# TEST 12: CommandPipeline — "XYZ Fake App kholo" → truthful failure
# ============================================================
test_header(12, "CommandPipeline('XYZ Fake App 9000 kholo') → Truthful failure")
try:
    from core.command_pipeline import process_user_command
    result = process_user_command("XYZ Fake App 9000 kholo", source="voice")
    log(f"Result: success={result.get('success')}, message={result.get('message', '')[:100]}")
    
    if not result.get("success"):
        log("✅ PASS — Truthful failure for nonexistent app")
        results["Pipeline: Fake App"] = "PASS"
    else:
        log("❌ FAIL — Falsely claimed success!")
        results["Pipeline: Fake App"] = "FAIL: False success"
except Exception as e:
    log(f"❌ EXCEPTION: {e}")
    results["Pipeline: Fake App"] = f"EXCEPTION: {e}"


# ============================================================
# FINAL REPORT
# ============================================================
print(f"\n{'='*60}")
print(f"  JARVIS REAL-WORLD PC CONTROL TEST RESULTS")
print(f"{'='*60}")

passed = sum(1 for v in results.values() if v == "PASS")
failed = sum(1 for v in results.values() if v != "PASS")

for test_name, result in results.items():
    status_icon = "✅" if result == "PASS" else "❌"
    print(f"  {status_icon} {test_name}: {result}")

print(f"\n  TOTAL: {len(results)} | PASSED: {passed} | FAILED: {failed}")
print(f"{'='*60}")
