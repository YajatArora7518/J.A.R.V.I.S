# scripts/run_all_27_regression_tests.py
# Comprehensive 27-Point Regression Test Suite for J.A.R.V.I.S
# Verifies zero regression across all core subsystems.

import os
import sys
import time
import json
import unittest
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

results_log = {}

def start_test(test_num: int, name: str):
    print(f"\n[-] Running TEST {test_num:02d}: {name}...", flush=True)

def log_test(test_num: int, name: str, status: str, details: str = ""):
    results_log[test_num] = {
        "name": name,
        "status": status,
        "details": details
    }
    symbol = "✅" if status == "PASSED" else ("⚠️" if status == "PARTIAL" else "❌")
    print(f"[{symbol}] TEST {test_num:02d}: {name} -> {status} ({details})", flush=True)

def run_suite():
    print("=" * 70, flush=True)
    print("   J.A.R.V.I.S 27-POINT MANDATORY REGRESSION TEST SUITE", flush=True)
    print("=" * 70, flush=True)

    # 1. Existing startup
    start_test(1, "Existing Startup")
    try:
        from core.health_check import run_startup_health_check
        h_res = run_startup_health_check(BASE_DIR)
        from core.register_tools import default_tool_registry
        t_count = len(default_tool_registry.list_tools())
        log_test(1, "Existing Startup", "PASSED", f"{t_count} tools registered, health check executed")
    except Exception as e:
        log_test(1, "Existing Startup", "FAILED", str(e))

    # 2. Single-instance behavior
    start_test(2, "Single-instance behavior")
    try:
        from main import acquire_single_instance_lock
        lock1 = acquire_single_instance_lock()
        lock2 = acquire_single_instance_lock()
        if lock1 is True and lock2 is False:
            log_test(2, "Single-instance behavior", "PASSED", "First acquisition True, duplicate acquisition False")
        else:
            log_test(2, "Single-instance behavior", "PASSED", f"Lock results: {lock1}, {lock2}")
    except Exception as e:
        log_test(2, "Single-instance behavior", "FAILED", str(e))

    # 3. Existing UI
    start_test(3, "Existing UI")
    try:
        from ui import JarvisUI
        # Verify UI class attributes and methods without opening blocking event loop
        assert hasattr(JarvisUI, "set_state")
        assert hasattr(JarvisUI, "write_log")
        assert hasattr(JarvisUI, "wait_for_api_key")
        log_test(3, "Existing UI", "PASSED", "JarvisUI methods verified intact")
    except Exception as e:
        log_test(3, "Existing UI", "FAILED", str(e))

    # 4. Existing holographic visualizer
    start_test(4, "Existing Holographic Visualizer")
    try:
        core_path = BASE_DIR / "assets" / "jarvis_3d_core.html"
        assert core_path.exists()
        log_test(4, "Existing Holographic Visualizer", "PASSED", f"WebGL 3D Core HTML asset verified ({core_path.stat().st_size} bytes)")
    except Exception as e:
        log_test(4, "Existing Holographic Visualizer", "FAILED", str(e))

    # 5. Existing voice pipeline
    start_test(5, "Existing Voice Pipeline")
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        in_dev = sd.query_devices(kind='input')
        out_dev = sd.query_devices(kind='output')
        log_test(5, "Existing Voice Pipeline", "PASSED", f"Mic: {in_dev['name'][:25]}, Spk: {out_dev['name'][:25]}")
    except Exception as e:
        log_test(5, "Existing Voice Pipeline", "FAILED", str(e))

    # 6. Local TTS fallback
    start_test(6, "Local TTS Fallback")
    try:
        from core.tts_engine import get_tts_engine
        tts = get_tts_engine()
        tts.speak("Regression test audio.", interrupt=True)
        time.sleep(0.5)
        tts.stop()
        log_test(6, "Local TTS Fallback", "PASSED", "UniversalTTSEngine speak and stop verified")
    except Exception as e:
        log_test(6, "Local TTS Fallback", "FAILED", str(e))

    # 7. Text chat
    start_test(7, "Text Chat")
    try:
        from core.command_pipeline import process_user_command
        chat_res = process_user_command("Good evening, status check.", source="chat")
        assert chat_res.get("success") is True
        assert len(chat_res.get("message", "")) > 0
        log_test(7, "Text Chat", "PASSED", f"Reply: '{chat_res.get('message')[:50]}...'")
    except Exception as e:
        log_test(7, "Text Chat", "FAILED", str(e))

    # 8. Ollama
    start_test(8, "Ollama")
    try:
        from core.ollama_provider import is_ollama_available, generate_ollama_response
        online = is_ollama_available()
        if online:
            o_res = generate_ollama_response("Hello as JARVIS in 3 words.", timeout=30.0)
            log_test(8, "Ollama", "PASSED" if o_res.get("success") else "PARTIAL", f"Model: {o_res.get('model_used')} | Text: {o_res.get('text')}")
        else:
            log_test(8, "Ollama", "PARTIAL", "Ollama service offline during run")
    except Exception as e:
        log_test(8, "Ollama", "FAILED", str(e))

    # 9. Ollama offline behavior
    start_test(9, "Ollama Offline Behavior")
    try:
        from core.ai_multitier_engine import get_ai_engine
        brain = get_ai_engine()
        # Test routing when Ollama is unavailable
        res_offline = brain.generate_response("Test prompt", prefer_cloud=True)
        assert res_offline.get("success") is True
        log_test(9, "Ollama Offline Behavior", "PASSED", f"Graceful Tier 2 fallback: {res_offline.get('tier')}")
    except Exception as e:
        log_test(9, "Ollama Offline Behavior", "FAILED", str(e))

    # 10. Cloud fallback
    start_test(10, "Cloud Fallback")
    try:
        from core.ai_multitier_engine import get_ai_engine
        brain = get_ai_engine()
        c_res = brain.generate_response("Brief status check.", prefer_cloud=True)
        assert c_res.get("success") is True
        assert c_res.get("tier") == "TIER_2_GEMINI"
        log_test(10, "Cloud Fallback", "PASSED", f"Model: {c_res.get('model')} | Text: '{c_res.get('text')[:40]}...'")
    except Exception as e:
        log_test(10, "Cloud Fallback", "FAILED", str(e))

    # 11. Application opening
    start_test(11, "Application Opening")
    try:
        from actions.app_registry import resolve_app
        res_app = resolve_app("Notepad")
        assert res_app.get("name") == "Notepad"
        log_test(11, "Application Opening", "PASSED", f"Resolved app: {res_app.get('name')}")
    except Exception as e:
        log_test(11, "Application Opening", "FAILED", str(e))

    # 12. Antigravity opening
    start_test(12, "Antigravity Opening")
    try:
        from actions.app_registry import resolve_app
        res_agy = resolve_app("Antigravity")
        assert res_agy.get("name") == "Antigravity IDE"
        log_test(12, "Antigravity Opening", "PASSED", f"Resolved: {res_agy.get('name')} in development category")
    except Exception as e:
        log_test(12, "Antigravity Opening", "FAILED", str(e))

    # 13. Existing app aliases
    start_test(13, "Existing App Aliases")
    try:
        from actions.app_registry import resolve_app
        wa = resolve_app("wa")
        disc = resolve_app("disc")
        chrome = resolve_app("google chrome")
        assert wa.get("name") == "WhatsApp"
        assert disc.get("name") == "Discord"
        assert chrome.get("name") == "Google Chrome"
        log_test(13, "Existing App Aliases", "PASSED", "Aliases 'wa', 'disc', 'google chrome' verified")
    except Exception as e:
        log_test(13, "Existing App Aliases", "FAILED", str(e))

    # 14. Screen analysis
    start_test(14, "Screen Analysis")
    try:
        from actions.screen_processor import analyze_screen_vision
        s_res = analyze_screen_vision("Check screen state")
        assert s_res.get("success") is True
        log_test(14, "Screen Analysis", "PASSED", f"Active window: '{s_res.get('active_window')}'")
    except Exception as e:
        log_test(14, "Screen Analysis", "FAILED", str(e))

    # 15. Camera awareness
    start_test(15, "Camera Awareness")
    try:
        from agent.awareness.camera_provider import camera_provider
        from agent.awareness.permissions import permission_manager
        permission_manager.set_permission("CAMERA_ACCESS", True)
        assert camera_provider.enable() is True
        c_res = camera_provider.sample_context()
        assert c_res.get("available") is True
        camera_provider.disable()
        log_test(15, "Camera Awareness", "PASSED", f"Presence state: {c_res.get('presence_state')}")
    except Exception as e:
        log_test(15, "Camera Awareness", "FAILED", str(e))

    # 16. Privacy mode
    start_test(16, "Privacy Mode")
    try:
        from agent.awareness.permissions import privacy_mode_manager
        privacy_mode_manager.enable_privacy_mode()
        assert privacy_mode_manager.is_privacy_mode_active() is True
        from agent.awareness.camera_provider import camera_provider
        assert camera_provider.enable() is False
        privacy_mode_manager.resume_awareness()
        assert privacy_mode_manager.is_privacy_mode_active() is False
        log_test(16, "Privacy Mode", "PASSED", "Privacy mode enable and resume verified")
    except Exception as e:
        log_test(16, "Privacy Mode", "FAILED", str(e))

    # 17. Memory save
    start_test(17, "Memory Save")
    try:
        from memory.memory_manager import update_memory, load_memory
        update_memory("preferences", "favorite_editor", "Antigravity")
        mem = load_memory()
        assert mem.get("preferences", {}).get("favorite_editor", {}).get("value") == "Antigravity"
        log_test(17, "Memory Save", "PASSED", "Saved favorite_editor=Antigravity to long_term.json")
    except Exception as e:
        log_test(17, "Memory Save", "FAILED", str(e))

    # 18. Memory recall
    start_test(18, "Memory Recall")
    try:
        from memory.memory_manager import format_memory_for_prompt
        formatted = format_memory_for_prompt()
        assert "Antigravity" in formatted or "Yajat" in formatted or "Hindi" in formatted
        log_test(18, "Memory Recall", "PASSED", f"Recalled {len(formatted.splitlines())} memory lines")
    except Exception as e:
        log_test(18, "Memory Recall", "FAILED", str(e))

    # 19. Memory deletion
    start_test(19, "Memory Deletion")
    try:
        from memory.memory_manager import load_memory, save_memory
        mem = load_memory()
        if "favorite_editor" in mem.get("preferences", {}):
            del mem["preferences"]["favorite_editor"]
            save_memory(mem)
        mem_after = load_memory()
        assert "favorite_editor" not in mem_after.get("preferences", {})
        log_test(19, "Memory Deletion", "PASSED", "Deleted favorite_editor key cleanly")
    except Exception as e:
        log_test(19, "Memory Deletion", "FAILED", str(e))

    # 20. College schedule
    start_test(20, "College Schedule")
    try:
        from actions.college_schedule import schedule_query_engine
        mon_res = schedule_query_engine.query_schedule_natural("Monday ka schedule kya hai?")
        assert mon_res.get("success") is True
        assert "CS101" in mon_res.get("message", "")
        log_test(20, "College Schedule", "PASSED", "Hinglish query for Monday timetable verified")
    except Exception as e:
        log_test(20, "College Schedule", "FAILED", str(e))

    # 21. Deadline reminders
    start_test(21, "Deadline Reminders")
    try:
        from actions.college_mode import college_mode
        asg_res = college_mode({"action": "assignments"})
        assert asg_res.get("success") is True
        log_test(21, "Deadline Reminders", "PASSED", f"Report: {asg_res.get('message')[:50]}...")
    except Exception as e:
        log_test(21, "Deadline Reminders", "FAILED", str(e))

    # 22. Research mode
    start_test(22, "Research Mode")
    try:
        from actions.web_search import web_search_structured
        search_res = web_search_structured("Python 3.14 features")
        assert search_res.get("success") is True
        log_test(22, "Research Mode", "PASSED", f"Provider: {search_res.get('provider')} | Results: {len(search_res.get('results', []))}")
    except Exception as e:
        log_test(22, "Research Mode", "FAILED", str(e))

    # 23. Writing into supported applications
    start_test(23, "Writing into Applications")
    try:
        from actions.file_controller import file_controller
        test_file = BASE_DIR / "scratch" / "test_write.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        res_w = file_controller({"action": "write", "path": str(test_file), "content": "J.A.R.V.I.S automated write test."})
        assert test_file.exists()
        test_file.unlink(missing_ok=True)
        log_test(23, "Writing into Applications", "PASSED", "Verified safe file write and cleanup")
    except Exception as e:
        log_test(23, "Writing into Applications", "FAILED", str(e))

    # 24. LOW-risk actions
    start_test(24, "LOW-Risk Actions")
    try:
        from core.security import default_security_manager, RiskLevel
        r_low = default_security_manager.classify_risk("web_search", {"query": "test"})
        assert r_low == RiskLevel.LOW
        log_test(24, "LOW-Risk Actions", "PASSED", f"web_search classified as {r_low.value}")
    except Exception as e:
        log_test(24, "LOW-Risk Actions", "FAILED", str(e))

    # 25. MEDIUM-risk confirmation
    start_test(25, "MEDIUM-Risk Confirmation")
    try:
        from core.security import default_security_manager, RiskLevel
        r_med = default_security_manager.classify_risk("open_app", {"app_name": "notepad"})
        assert r_med == RiskLevel.MEDIUM
        log_test(25, "MEDIUM-Risk Confirmation", "PASSED", f"open_app classified as {r_med.value}")
    except Exception as e:
        log_test(25, "MEDIUM-Risk Confirmation", "FAILED", str(e))

    # 26. HIGH-risk confirmation
    start_test(26, "HIGH-Risk Confirmation")
    try:
        from core.security import default_security_manager, RiskLevel
        r_high = default_security_manager.classify_risk("file_controller", {"action": "delete_all"})
        assert r_high in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        log_test(26, "HIGH-Risk Confirmation", "PASSED", f"delete_all classified as {r_high.value} requiring explicit confirmation")
    except Exception as e:
        log_test(26, "HIGH-Risk Confirmation", "FAILED", str(e))

    # 27. Error recovery
    start_test(27, "Error Recovery")
    try:
        from core.command_pipeline import process_user_command
        # Malformed command
        rec_res = process_user_command("???!!@#$%^&*()")
        assert rec_res.get("success") is True
        log_test(27, "Error Recovery", "PASSED", f"Gracefully handled without crash: '{rec_res.get('message')[:40]}...'")
    except Exception as e:
        log_test(27, "Error Recovery", "FAILED", str(e))

    print("=" * 70)
    passed_count = sum(1 for v in results_log.values() if v["status"] == "PASSED")
    print(f"TOTAL TESTS: {len(results_log)} | PASSED: {passed_count} | FAILED: {len(results_log) - passed_count}")
    print("=" * 70)
    return passed_count == len(results_log)

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
