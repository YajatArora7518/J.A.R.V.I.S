# agent/proactive_engine.py
"""
Proactive Decision Engine & Companion Mode Controller for JARVIS.
Evaluates context, priority, permissions, quiet hours, anti-spam deduplication, and sleep reminders.
Guarantees zero interruption during active commands/speech and routes all write actions through SecurityManager.
"""

import time
import threading
from datetime import datetime, timedelta
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

    def is_in_quiet_hours(self, hour: Optional[int] = None) -> bool:
        """
        Quiet hours: 11 PM – 7 AM (23:00 to 07:00).
        During quiet hours, normal spoken interruptions are completely suppressed.
        """
        if hour is None:
            hour = int(time.strftime("%H"))
        return hour >= 23 or hour < 7

    def score_event(self, event_type: str) -> int:
        scores = {
            "CRITICAL_SECURITY_ALERT": 100,
            "ASSIGNMENT_DUE_SOON": 95,
            "CALENDAR_UPCOMING_5MIN": 90,
            "CLASS_STARTING_SOON": 85,
            "IMPORTANT_WHATSAPP": 80,
            "IMPORTANT_TASK": 75,
            "USER_RETURNED_ABSENCE": 70,
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

    def evaluate_proactive_speech(self, context: Optional[Dict[str, Any]] = None, current_hour: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Evaluates whether JARVIS should speak proactively based on strong evidence:
        - Quiet hours (11 PM - 7 AM): suppresses non-urgent spoken notifications
        - Active-user gating: prevents interruptions while user or assistant is busy
        - Global cooldown & anti-spam deduplication: never repeatedly states identical messages
        """
        with self._lock:
            # 1. Proactive mode enabled check
            if not self.proactive_enabled:
                return None

            try:
                if not permission_manager.is_granted("PROACTIVE_MODE"):
                    return None
            except Exception:
                pass

            # 2. Privacy mode check
            try:
                if privacy_mode_manager.is_privacy_mode_active():
                    return None
            except Exception:
                pass

            # 3. Active-user gating (zero interruption during active conversation or execution)
            if self.is_user_speaking or self.is_speaking or self.is_command_executing or self.is_tool_executing or self.is_user_busy:
                return None

            now = time.time()
            # 4. Global cooldown check
            if (now - self.last_proactive_timestamp) < self.global_cooldown_seconds:
                return None

            # 5. Quiet hours check (11 PM - 7 AM)
            in_quiet = self.is_in_quiet_hours(hour=current_hour)

            if context is None:
                try:
                    context = context_engine.get_current_context()
                except Exception:
                    context = {}

            # Helper for deduplication & dispatch
            def _dispatch(ev_type: str, priority: str, message: str, is_urgent: bool = False) -> Optional[Dict[str, Any]]:
                if in_quiet and not is_urgent and priority not in ["CRITICAL", "URGENT"]:
                    return None  # Suppress normal spoken interruptions during quiet hours

                event_key = f"{ev_type}_{hash(message)}"
                last_time = self.history_dedup.get(event_key, 0.0)
                if (now - last_time) < 86400:  # 24h anti-spam deduplication
                    return None

                self.history_dedup[event_key] = now
                self.last_proactive_timestamp = now
                score = self.score_event(ev_type)
                return {
                    "type": ev_type,
                    "priority": priority,
                    "score": score,
                    "should_interrupt": True,
                    "reason": ev_type,
                    "message": message,
                    "_event_key": event_key, "_dispatch_ts": now
                }

            # Check 1: Explicit high-evidence event passed in context
            explicit_event = context.get("explicit_event")
            if explicit_event and isinstance(explicit_event, dict):
                ev_type = explicit_event.get("type", "NOTIFICATION")
                prio = explicit_event.get("priority", "HIGH")
                msg = explicit_event.get("message", "")
                is_urg = bool(explicit_event.get("urgent", False))
                return _dispatch(ev_type, prio, msg, is_urgent=is_urg)

            # Check 2: Return after meaningful absence (>10 mins)
            presence = context.get("presence_state")
            absence_sec = context.get("absence_duration_seconds", 0)
            if presence == "USER_RETURNED" and absence_sec >= 600:
                res = _dispatch(
                    "USER_RETURNED_ABSENCE",
                    "MEDIUM",
                    "Wapas aa gaya? Kya chal raha tha, busy tha ya break liya?"
                )
                if res:
                    return res

            # Check 3: Assignment due soon
            try:
                from agent.task_manager import default_task_manager
                pending = default_task_manager.get_pending_tasks()
                for t in pending:
                    if t.category == "assignment" and t.priority in ["HIGH", "CRITICAL"]:
                        # Only a real upcoming deadline warrants a "due soon" alert.
                        try:
                            due = datetime.fromisoformat(t.due_at or "")
                            if len(t.due_at) == 10:
                                due = due.replace(hour=23, minute=59, second=59)
                            current = datetime.now(due.tzinfo)
                            if not current <= due <= current + timedelta(days=1):
                                continue
                        except (ValueError, TypeError):
                            continue
                        res = _dispatch(
                            "ASSIGNMENT_DUE_SOON",
                            "HIGH",
                            f"Boss, reminder: your assignment '{t.title}' is due soon ({t.due_at or 'today'})."
                        )
                        if res:
                            return res
            except Exception:
                pass

            # Check 4: Class starting soon
            class_alert = context.get("class_starting_soon")
            if class_alert:
                res = _dispatch("CLASS_STARTING_SOON", "HIGH", f"Boss, {class_alert} starts in a few minutes.")
                if res:
                    return res

            # Check 5: Sleep Reminder (1 AM)
            current_hhmm = time.strftime("%H:%M")
            if current_hhmm == self.preferred_sleep_time:
                res = _dispatch(
                    "SLEEP_REMINDER",
                    "MEDIUM",
                    "Boss, it's 1 AM. You should probably get some sleep. What are you still working on?"
                )
                if res:
                    return res

            return None

    def delivery_failed(self, decision):
        """Do not count a declined/failed queue delivery as an actual check-in."""
        with self._lock:
            key, stamp = decision.get('_event_key'), decision.get('_dispatch_ts')
            if key and self.history_dedup.get(key) == stamp:
                self.history_dedup.pop(key, None)
            if self.last_proactive_timestamp == stamp:
                self.last_proactive_timestamp = 0.0


proactive_decision_engine = ProactiveDecisionEngine()
proactive_engine = proactive_decision_engine
