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

                if privacy_mode_manager.is_privacy_mode_active():
                    continue

                ctx = context_engine.get_current_context()
                decision = proactive_decision_engine.evaluate_proactive_speech(ctx)

                if decision and decision.get("message") and self.speak_callback:
                    self.speak_callback(decision["message"])

            except Exception as ex:
                # Controlled error logging; awareness failure NEVER crashes JARVIS
                print(f"[AmbientOrchestrator] Worker note: {ex}")


ambient_orchestrator = AmbientOrchestrator()
