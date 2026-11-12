# scripts/test_memory_quality.py
# Phase 3F: Structured Memory Quality & Backward Compatibility Test

import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from memory.memory_manager import (
    load_memory,
    save_memory,
    update_memory,
    prune_expired_memories
)

def run_memory_quality_tests():
    print("=" * 65, flush=True)
    print("      PHASE 3F: STRUCTURED MEMORY QUALITY & COMPATIBILITY TEST", flush=True)
    print("=" * 65, flush=True)

    # 1. Backward Compatibility with Existing entry["value"] Pattern
    print("\n[-] STEP 1: Verify Existing entry['value'] Compatibility", flush=True)
    mem = load_memory()
    for cat, items in mem.items():
        if isinstance(items, dict):
            for k, entry in items.items():
                if isinstance(entry, dict):
                    assert "value" in entry, f"Missing 'value' in existing memory entry: {cat}/{k}"
    print("  [+] Backward compatibility verified: All existing entries expose 'value'.", flush=True)

    # 2. Additive Structured Metadata
    print("\n[-] STEP 2: Verify Additive Structured Metadata Fields", flush=True)
    test_update = {
        "preferences": {
            "test_editor": {
                "value": "Antigravity",
                "category": "developer_tools",
                "confidence": 0.98,
                "source": "user_explicit",
                "expiry": None
            }
        }
    }
    updated_mem = update_memory(test_update)
    entry = updated_mem["preferences"]["test_editor"]
    
    assert entry["value"] == "Antigravity", f"Value mismatch: {entry['value']}"
    assert entry.get("category") == "developer_tools", f"Category missing or mismatch: {entry.get('category')}"
    assert entry.get("confidence") == 0.98, f"Confidence missing or mismatch: {entry.get('confidence')}"
    assert entry.get("source") == "user_explicit", f"Source missing: {entry.get('source')}"
    assert "created_at" in entry, "created_at missing from structured entry"
    assert "last_accessed" in entry, "last_accessed missing from structured entry"
    print(f"  [+] Structured metadata verified: {entry}", flush=True)

    # 3. Temporary Context Expiry vs Stable Preference Preservation
    print("\n[-] STEP 3: Temporary Context Expiry vs Stable Preservation", flush=True)
    past_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    expiry_test_update = {
        "notes": {
            "temp_meeting_note": {
                "value": "Meeting tomorrow at 10 AM",
                "category": "calendar_temp",
                "source": "temporary_context",
                "expiry": past_date  # Expired
            },
            "future_project_deadline": {
                "value": "Submit project by next week",
                "category": "deadlines",
                "source": "calendar",
                "expiry": future_date  # Active
            }
        }
    }
    update_memory(expiry_test_update)

    # Execute safe non-destructive prune
    mem_before_prune = load_memory()
    assert "temp_meeting_note" in mem_before_prune["notes"]
    assert "future_project_deadline" in mem_before_prune["notes"]

    pruned_mem, count = prune_expired_memories()
    print(f"  [+] Pruned count: {count}", flush=True)
    assert count >= 1, "Expected at least 1 expired note to be pruned!"

    mem_after_prune = load_memory()
    # Expired entry should be gone
    assert "temp_meeting_note" not in mem_after_prune.get("notes", {}), "Expired temporary note was not pruned!"
    # Active future entry MUST remain
    assert "future_project_deadline" in mem_after_prune.get("notes", {}), "Future entry was mistakenly pruned!"
    # Stable explicit preference MUST remain intact
    assert "test_editor" in mem_after_prune.get("preferences", {}), "Stable preference was accidentally pruned!"
    print("  [+] Expiry precision verified: Expired temp context pruned; active deadline and stable preference preserved.", flush=True)

    # 4. Clean up test entries
    print("\n[-] STEP 4: Clean Up Test Entries", flush=True)
    mem_clean = load_memory()
    if "test_editor" in mem_clean.get("preferences", {}):
        del mem_clean["preferences"]["test_editor"]
    if "future_project_deadline" in mem_clean.get("notes", {}):
        del mem_clean["notes"]["future_project_deadline"]
    save_memory(mem_clean)
    print("  [+] Test entries cleaned up safely.", flush=True)

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3F STRUCTURED MEMORY QUALITY TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_memory_quality_tests()
    sys.exit(0 if success else 1)
