# core/proactive_event_bus.py
# Safe Proactive Event Intelligence & Alert Bus for JARVIS
# Manages system, application, network, and gateway events with priority classification,
# deduplication, cooldowns, and user-interruption protection.

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger("JARVIS.ProactiveEventBus")


@dataclass
class SystemEvent:
    id: str
    event_type: str  # "battery_critical", "process_crash", "whatsapp_call", "task_completed", "reminder", "gateway_disconnect"
    source: str
    title: str
    message: str
    priority: str = "MEDIUM"  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    dedup_key: str = ""

    def __post_init__(self):
        if not self.dedup_key:
            self.dedup_key = f"{self.event_type}:{self.source}:{self.title}"


class ProactiveEventBus:
    """
    Authoritative Proactive Event Bus for JARVIS.
    Filters low-priority noise, enforces cooldowns, prevents event spamming,
    and coordinates user notifications safely.
    """
    def __init__(self):
        self._listeners: List[Callable[[SystemEvent], None]] = []
        self._event_history: List[SystemEvent] = []
        self._dedup_cooldowns: Dict[str, float] = {}
        self._quiet_mode: bool = False
        self._is_user_speaking: bool = False

    def set_quiet_mode(self, quiet: bool) -> None:
        self._quiet_mode = quiet
        logger.info(f"[ProactiveEventBus] Quiet mode: {quiet}")

    def set_user_speaking(self, speaking: bool) -> None:
        self._is_user_speaking = speaking

    def register_listener(self, listener: Callable[[SystemEvent], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def publish_event(
        self,
        event_type: str,
        source: str,
        title: str,
        message: str,
        priority: str = "MEDIUM",
        payload: Optional[Dict[str, Any]] = None,
        cooldown_sec: float = 30.0
    ) -> Optional[SystemEvent]:
        """
        Publishes a system event if not rate-limited by cooldown.
        Priority Rules:
        - CRITICAL: Always emitted immediately.
        - HIGH: Emitted unless user is actively speaking.
        - MEDIUM / LOW: Queued or suppressed if quiet_mode or active conversation.
        """
        dedup_key = f"{event_type}:{source}:{title}"
        now = time.time()

        if dedup_key in self._dedup_cooldowns:
            if now - self._dedup_cooldowns[dedup_key] < cooldown_sec:
                logger.debug(f"[ProactiveEventBus] Suppressed duplicate event '{dedup_key}' within cooldown.")
                return None

        self._dedup_cooldowns[dedup_key] = now

        p_norm = priority.upper().strip()
        if p_norm not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            p_norm = "MEDIUM"

        event = SystemEvent(
            id=f"evt_{int(now * 1000)}",
            event_type=event_type,
            source=source,
            title=title,
            message=message,
            priority=p_norm,
            timestamp=now,
            payload=payload or {},
            dedup_key=dedup_key
        )

        self._event_history.append(event)
        if len(self._event_history) > 100:
            self._event_history.pop(0)

        # Interruption Guard Evaluation
        if p_norm in ["LOW", "MEDIUM"] and (self._quiet_mode or self._is_user_speaking):
            logger.info(f"[ProactiveEventBus] Event '{title}' queued due to quiet_mode/active user conversation.")
            return event

        logger.info(f"[ProactiveEventBus] Event Published [{p_norm}]: {title} - {message}")

        for callback in self._listeners:
            try:
                callback(event)
            except Exception as err:
                logger.warning(f"[ProactiveEventBus] Listener callback error: {err}")

        return event

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [
            {
                "id": e.id,
                "type": e.event_type,
                "source": e.source,
                "title": e.title,
                "message": e.message,
                "priority": e.priority,
                "timestamp": e.timestamp
            }
            for e in self._event_history[-limit:]
        ]


# Global Singleton Instance
proactive_event_bus = ProactiveEventBus()
