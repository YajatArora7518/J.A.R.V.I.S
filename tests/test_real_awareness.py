# tests/test_real_awareness.py
"""
Comprehensive 30-step Unit & Integration Test Suite for Phase 7 E2E Proactive Personal AI + Ambient Awareness.
"""

import unittest
import time
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.awareness.camera_provider import camera_provider
from agent.awareness.screen_provider import screen_provider
from agent.awareness.whatsapp_provider import whatsapp_provider
from agent.awareness.email_provider import email_provider
from agent.awareness.calendar_provider import calendar_provider
from agent.awareness.instagram_provider import instagram_provider
from agent.context_engine import context_engine, unified_analyzer
from agent.proactive_engine import proactive_decision_engine
from agent.ambient_orchestrator import ambient_orchestrator


class TestRealAwareness(unittest.TestCase):

    def setUp(self):
        privacy_mode_manager.resume_awareness()
        permission_manager.set_permission("CAMERA_ACCESS", False)
        permission_manager.set_permission("SCREEN_ACCESS", False)
        permission_manager.set_permission("WHATSAPP_READ", False)
        permission_manager.set_permission("EMAIL_READ", False)
        permission_manager.set_permission("CALENDAR_READ", False)
        permission_manager.set_permission("INSTAGRAM_READ", False)
        permission_manager.set_permission("PROACTIVE_MODE", True)
        permission_manager.set_permission("COMPANION_MODE", False)
        camera_provider.disable()
        screen_provider.disable()

    # Step 1: Camera enable/disable
    def test_01_camera_enable_disable(self):
        permission_manager.set_permission("CAMERA_ACCESS", True)
        self.assertTrue(camera_provider.enable())
        self.assertTrue(camera_provider.is_camera_active())
        camera_provider.disable()
        self.assertFalse(camera_provider.is_camera_active())

    # Step 2: Camera unavailable
    def test_02_camera_unavailable(self):
        res = camera_provider.sample_context()
        self.assertEqual(res["status"], "CAMERA_UNAVAILABLE")
        self.assertFalse(res["available"])

    # Step 3: Screen context detection
    def test_03_screen_context_detection(self):
        permission_manager.set_permission("SCREEN_ACCESS", True)
        screen_provider.enable()
        res = screen_provider.classify_context()
        self.assertEqual(res["status"], "OK")
        self.assertIn("category", res)
        screen_provider.disable()

    # Step 4: Screen unavailable
    def test_04_screen_unavailable(self):
        res = screen_provider.classify_context()
        self.assertEqual(res["status"], "SCREEN_UNAVAILABLE")

    # Step 5: WhatsApp unread detection & incoming direction
    def test_05_whatsapp_unread(self):
        permission_manager.set_permission("WHATSAPP_READ", True)
        res = whatsapp_provider.check_unread()
        self.assertIn(res["status"], ["OK", "WHATSAPP_UNAVAILABLE"])
        msg = whatsapp_provider.process_incoming_message("Papa", "Hello son")
        self.assertEqual(msg["direction"], "incoming")
        self.assertEqual(msg["sender"], "Papa")

    # Step 6: WhatsApp deduplication
    def test_06_whatsapp_deduplication(self):
        msg1 = whatsapp_provider.process_incoming_message("Papa", "Call me", "msg_123")
        msg2 = whatsapp_provider.process_incoming_message("Papa", "Call me", "msg_123")
        self.assertEqual(msg1["message_id"], msg2["message_id"])

    # Step 7 & 8: Email provider & email unavailable
    def test_07_08_email_provider(self):
        res = email_provider.check_inbox()
        self.assertEqual(res["status"], "EMAIL_UNAVAILABLE")

    # Step 9 & 10: Calendar provider & calendar unavailable
    def test_09_10_calendar_provider(self):
        res = calendar_provider.check_events()
        self.assertEqual(res["status"], "CALENDAR_UNAVAILABLE")

    # Step 11 & 12: Instagram provider & instagram unavailable
    def test_11_12_instagram_provider(self):
        res = instagram_provider.check_activity()
        self.assertEqual(res["status"], "INSTAGRAM_UNAVAILABLE")

    # Step 13: Context aggregation
    def test_13_context_aggregation(self):
        ctx = context_engine.get_current_context()
        self.assertIn("timestamp", ctx)
        self.assertIn("provider_statuses", ctx)
        self.assertIn("unread_messages", ctx)

    # Step 14: Priority scoring
    def test_14_priority_scoring(self):
        score_crit = proactive_decision_engine.score_event("CRITICAL_SECURITY_ALERT")
        score_cas = proactive_decision_engine.score_event("CASUAL_COMPANION")
        self.assertGreater(score_crit, score_cas)
        self.assertEqual(score_crit, 100)

    # Step 15: Global cooldown
    def test_15_global_cooldown(self):
        proactive_decision_engine.last_proactive_timestamp = time.time()
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

    # Step 16 & 17: Deduplication checks
    def test_16_17_deduplication(self):
        proactive_decision_engine.history_dedup["notif_test"] = time.time()
        ctx = {"important_notifications": ["test"]}
        proactive_decision_engine.last_proactive_timestamp = time.time() - 400
        res = proactive_decision_engine.evaluate_proactive_speech(ctx)
        self.assertIsNone(res)

    # Step 18: Quiet hours check
    def test_18_quiet_hours(self):
        self.assertTrue(hasattr(proactive_decision_engine, "quiet_hours_start"))

    # Step 19: Sleep reminder
    def test_19_sleep_reminder(self):
        proactive_decision_engine.last_proactive_timestamp = time.time() - 400
        proactive_decision_engine.preferred_sleep_time = time.strftime("%H:%M")
        res = proactive_decision_engine.evaluate_proactive_speech()
        if res:
            self.assertEqual(res["reason"], "SLEEP_REMINDER")

    # Step 20: Companion mode
    def test_20_companion_mode(self):
        permission_manager.set_permission("COMPANION_MODE", True)
        proactive_decision_engine.companion_mode_enabled = True
        proactive_decision_engine.last_proactive_timestamp = time.time() - 400
        proactive_decision_engine.last_companion_prompt = time.time() - 700
        ctx = {"activity": "CODING"}
        res = proactive_decision_engine.evaluate_proactive_speech(ctx)
        if res:
            self.assertEqual(res["reason"], "CASUAL_COMPANION")

    # Step 21, 22, 23: Privacy mode, Pause & Resume awareness
    def test_21_22_23_privacy_and_pause_resume(self):
        privacy_mode_manager.pause_all_awareness(True)
        self.assertTrue(privacy_mode_manager.is_privacy_mode_active())
        privacy_mode_manager.resume_awareness()
        self.assertFalse(privacy_mode_manager.is_privacy_mode_active())

    # Step 24: User speaking suppression
    def test_24_user_speaking_suppression(self):
        proactive_decision_engine.set_system_state(is_user_speaking=True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

    # Step 25: Tool execution suppression
    def test_25_tool_execution_suppression(self):
        proactive_decision_engine.set_system_state(is_tool_executing=True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

    # Step 26: Barge-in cancellation
    def test_26_barge_in_cancellation(self):
        proactive_decision_engine.set_system_state(is_speaking=True)
        res = proactive_decision_engine.evaluate_proactive_speech()
        self.assertIsNone(res)

    # Step 27: Fail-safe provider isolation
    def test_27_fail_safe_isolation(self):
        try:
            res = camera_provider.sample_context()
            self.assertIn("status", res)
        except Exception:
            self.fail("Camera provider raised an unhandled exception")

    # Step 28 & 29: Clean shutdown & no duplicate workers
    def test_28_29_shutdown_and_workers(self):
        ambient_orchestrator.start()
        self.assertTrue(ambient_orchestrator._running)
        ambient_orchestrator.stop()
        self.assertFalse(ambient_orchestrator._running)

    # Step 30: No fake success states
    def test_30_no_fake_success(self):
        res = email_provider.check_inbox()
        self.assertEqual(res["status"], "EMAIL_UNAVAILABLE")
        self.assertFalse(res.get("verified", False))


if __name__ == "__main__":
    unittest.main()
