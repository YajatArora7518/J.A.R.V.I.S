# agent/ambient_orchestrator.py
"""
Ambient Orchestrator for JARVIS Awareness & Proactive AI Companion.
Runs non-blocking background monitoring loops with independent fail-safe error handling and clean shutdown.
"""

import time
import threading
from typing import Optional, Callable
from agent.awareness.permissions import privacy_mode_manager
from agent.awareness.camera_provider import camera_provider
from agent.awareness.screen_provider import screen_provider
from agent.context_engine import context_engine
from agent.proactive_engine import proactive_decision_engine


class AmbientOrchestrator:
    """
    Manages non-blocking background awareness loops and proactive decision checks.
    Every provider fails independently without ever crashing JARVIS.
    """
    def __init__(self, speak_callback: Optional[Callable[[str], None]] = None):
        self.speak_callback = speak_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._ambient_loop, daemon=True, name="AmbientOrchestratorThread")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        camera_provider.cleanup()
        screen_provider.disable()

    def _ambient_loop(self) -> None:
        while self._running:
            try:
                time.sleep(10)
                if not self._running:
                    break

                self.tick()

            except Exception as ex:
                # Controlled error logging; awareness failure NEVER crashes JARVIS
                print(f"[AmbientOrchestrator] Worker note: {ex}")

    def tick(self):
        from agent.daily_planner import get_daily_planner, desktop_idle_seconds
        planner = get_daily_planner()
        planner.heartbeat()
        if privacy_mode_manager.is_privacy_mode_active() or not self.speak_callback:
            return None
        ctx = context_engine.get_current_context()
        event = None
        decision = proactive_decision_engine.evaluate_proactive_speech(ctx)
        if not decision:
            event = planner.next_check_in(idle_seconds=desktop_idle_seconds())
            if event:
                decision = proactive_decision_engine.evaluate_proactive_speech({'explicit_event': {
                    'type': 'DAILY_CHECK_IN', 'priority': 'MEDIUM', 'message': event['message']}})
        if decision and decision.get('message'):
            try:
                delivered = self.speak_callback(decision['message'])
            except Exception:
                proactive_decision_engine.delivery_failed(decision)
                raise
            if delivered is False:
                proactive_decision_engine.delivery_failed(decision)
                return None
            if event:
                planner.mark_delivered(event)
            return decision
        return None


ambient_orchestrator = AmbientOrchestrator()
