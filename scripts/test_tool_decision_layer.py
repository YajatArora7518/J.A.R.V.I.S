# scripts/test_tool_decision_layer.py
# Phase 3E: Intelligent Tool Decision Layer Test

import sys
import os
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from core.intent_router import classify_intent

def run_tool_decision_layer_tests():
    print("=" * 65, flush=True)
    print("      PHASE 3E: INTELLIGENT TOOL DECISION LAYER TEST", flush=True)
    print("=" * 65, flush=True)

    test_cases = [
        # Direct Questions -> Must return OTHER with tool=None (Pure AI, no unnecessary tools)
        {
            "query": "Who is Tony Stark?",
            "expected_intent": "OTHER",
            "expected_tool": None,
            "description": "Factual / conversational question -> pure AI"
        },
        {
            "query": "What is Python?",
            "expected_intent": "OTHER",
            "expected_tool": None,
            "description": "General knowledge question -> pure AI"
        },
        {
            "query": "Tell me a joke, Jarvis",
            "expected_intent": "OTHER",
            "expected_tool": None,
            "description": "Casual conversation -> pure AI"
        },

        # Application Execution Intent -> Must return WINDOWS_APPLICATION with tool='open_app'
        {
            "query": "Open Notepad",
            "expected_intent": "WINDOWS_APPLICATION",
            "expected_tool": "open_app",
            "expected_target": "Notepad",
            "description": "App launch command"
        },
        {
            "query": "Launch Google Chrome",
            "expected_intent": "WINDOWS_APPLICATION",
            "expected_tool": "open_app",
            "expected_target": "Google Chrome",
            "description": "App launch command with alias"
        },

        # Screen Vision & Multimodal Observation Intents
        {
            "query": "What's on my screen?",
            "expected_intent": "SCREEN_ANALYSIS",
            "expected_tool": "screen_process",
            "description": "Screen analysis query"
        },
        {
            "query": "Screen par kya hai?",
            "expected_intent": "SCREEN_ANALYSIS",
            "expected_tool": "screen_process",
            "description": "Hinglish screen analysis query"
        },
        {
            "query": "Look at my screen and tell me the error",
            "expected_intent": "SCREEN_ANALYSIS",
            "expected_tool": "screen_process",
            "description": "Complex screen analysis query"
        },

        # Reminder & Schedule Intents
        {
            "query": "Remind me tomorrow at 9 AM to submit assignment",
            "expected_intent": "REMINDER",
            "expected_tool": "reminder",
            "description": "English reminder command"
        },
        {
            "query": "Mujhe yaad dilana kal subah project review hai",
            "expected_intent": "REMINDER",
            "expected_tool": "reminder",
            "description": "Hinglish reminder command"
        },
        {
            "query": "Set reminder for meeting at 4 PM",
            "expected_intent": "REMINDER",
            "expected_tool": "reminder",
            "description": "Explicit reminder command"
        }
    ]

    all_passed = True

    print(f"\n{'QUERY':<35} | {'INTENT':<20} | {'TOOL':<16} | {'RESULT'}")
    print("-" * 80)

    for case in test_cases:
        query = case["query"]
        res = classify_intent(query)
        actual_intent = res.get("intent")
        actual_tool = res.get("tool")

        intent_ok = (actual_intent == case["expected_intent"])
        tool_ok = (actual_tool == case["expected_tool"])
        target_ok = True
        if "expected_target" in case:
            target_ok = (res.get("target", "").lower() == case["expected_target"].lower())

        passed = intent_ok and tool_ok and target_ok

        status = "PASSED" if passed else "FAILED"
        if not passed:
            all_passed = False

        print(f"{query[:35]:<35} | {actual_intent:<20} | {str(actual_tool):<16} | {status}")
        assert passed, f"Failed for '{query}': Got ({actual_intent}, {actual_tool}), expected ({case['expected_intent']}, {case['expected_tool']})"

    print("\n" + "=" * 65, flush=True)
    print("PHASE 3E INTELLIGENT TOOL DECISION LAYER TEST: PASSED", flush=True)
    print("=" * 65, flush=True)
    return True

if __name__ == "__main__":
    success = run_tool_decision_layer_tests()
    sys.exit(0 if success else 1)
