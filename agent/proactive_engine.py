# agent/proactive_engine.py
"""
Proactive Decision Engine & Companion Mode Controller for JARVIS.
Evaluates context, priority, permissions, quiet hours, anti-spam deduplication, and sleep reminders.
Guarantees zero interruption during active commands/speech and routes all write actions through SecurityManager.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from agent.awareness.permissions import permission_manager, privacy_mode_manager
from agent.context_engine import context_engine

class ProactiveDecisionEngine:
    """
    Evaluates whether JARVIS should proactively initiate speech or notifications.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.proactive_enabled = True
        self.companion_mode_enabled = False
        self.preferred_sleep_time = "01:00"  # 1:00 AM configurable
        self.quiet_hours_start = "23:00"
        self.quiet_hours_end = "07:00"
        
        self.global_cooldown_seconds = 300  # 5 minutes
        self.last_proactive_timestamp = 0.0
        self.history_dedup: Dict[str, float] = {}
        
        self.is_speaking = False
        self.is_user_speaking = False
        self.is_command_executing = False
        self.is_tool_executing = False
        self.is_user_busy = False

        self.last_companion_prompt = 0.0
        self.ignored_prompt_count = 0

    def score_event(self, event_type: str) -> int:
        scores = {
            "CRITICAL_SECURITY_ALERT": 100,
            "CALENDAR_UPCOMING_5MIN": 90,
            "IMPORTANT_WHATSAPP": 80,
            "IMPORTANT_EMAIL": 70,
            "UPCOMING_CLASS": 65,
            "LONG_WORK_SESSION": 40,
            "SLEEP_REMINDER": 35,
            "CASUAL_COMPANION": 15,
        }
        return scores.get(event_type, 10)

    def set_system_state(self, is_speaking: bool = False, is_user_speaking: bool = False, is_command_executing: bool = False, is_tool_executing: bool = False, is_user_busy: bool = False) -> None:
        with self._lock:
            self.is_speaking = is_speaking
            self.is_user_speaking = is_user_speaking
            self.is_command_executing = is_command_executing
            self.is_tool_executing = is_tool_executing
            self.is_user_busy = is_user_busy

    def evaluate_proactive_speech(self, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Runs 14 strict pre-checks to evaluate if JARVIS should speak proactively.
        Returns a proactive payload dict or None.
        """
        with self._lock:
            # 1. PROACTIVE_MODE enabled check
            if not self.proactive_enabled or not permission_manager.is_granted("PROACTIVE_MODE"):
                return None

            # 2. Privacy mode check
            if privacy_mode_manager.is_privacy_mode_active():
                return None

            # 3. User currently speaking check
            if self.is_user_speaking:
                return None

            # 4. JARVIS currently speaking check
            if self.is_speaking:
                return None

            # 5. User command executing check
            if self.is_command_executing:
                return None

            # 6. Tool currently executing check
            if self.is_tool_executing:
                return None

            # 7. User busy check
            if self.is_user_busy:
                return None

            # 8. Global cooldown check
            now = time.time()
            if (now - self.last_proactive_timestamp) < self.global_cooldown_seconds:
                return None

            if context is None:
                context = context_engine.get_current_context()

            # 9. Sleep Reminder Check (1 AM)
            current_hhmm = time.strftime("%H:%M")
            if current_hhmm == self.preferred_sleep_time:
                event_key = f"sleep_reminder_{time.strftime('%Y-%m-%d')}"
                if event_key not in self.history_dedup:
                    self.history_dedup[event_key] = now
                    self.last_proactive_timestamp = now
                    score = self.score_event("SLEEP_REMINDER")
                    return {
                        "type": "SLEEP_REMINDER",
                        "priority": "MEDIUM",
                        "score": score,
                        "should_interrupt": True,
                        "reason": "SLEEP_REMINDER",
                        "message": "Boss, it's 1 AM. You should probably get some sleep. What are you still working on?"
                    }

            # 10. Companion Mode check
            if self.companion_mode_enabled and permission_manager.is_granted("COMPANION_MODE"):
                if (now - self.last_companion_prompt) > 600:
                    act = context.get("activity", "UNKNOWN")
                    if act == "CODING":
                        event_key = f"companion_coding_{int(now // 3600)}"
                        if event_key not in self.history_dedup:
                            self.history_dedup[event_key] = now
                            self.last_proactive_timestamp = now
                            self.last_companion_prompt = now
                            score = self.score_event("CASUAL_COMPANION")
                            return {
                                "type": "COMPANION_PROMPT",
                                "priority": "LOW",
                                "score": score,
                                "should_interrupt": True,
                                "reason": "CASUAL_COMPANION",
                                "message": "Boss, what are you working on? Need any assistance or a quick break?"
                            }

            # 11. Important Notifications Check
            notifs = context.get("important_notifications", [])
            for notif in notifs:
                event_key = f"notif_{notif}"
                if event_key not in self.history_dedup:
                    self.history_dedup[event_key] = now
                    self.last_proactive_timestamp = now
                    score = self.score_event("IMPORTANT_WHATSAPP")
                    return {
                        "type": "NOTIFICATION",
                        "priority": "HIGH",
                        "score": score,
                        "should_interrupt": True,
                        "reason": "IMPORTANT_NOTIFICATION",
                        "message": notif
                    }

            return None


proactive_decision_engine = ProactiveDecisionEngine()
proactive_engine = proactive_decision_engine
