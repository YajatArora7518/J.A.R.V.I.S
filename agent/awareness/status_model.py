# agent/awareness/status_model.py
"""
Unified Provider Status Data Model & Registry for JARVIS Ambient Awareness Subsystem.
Provides a single authoritative status source for providers and UI displays.
"""

import time
import threading
from typing import Dict, Any, Optional

class ProviderState:
    LIVE_VERIFIED = "LIVE_VERIFIED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    HARDWARE_UNAVAILABLE = "HARDWARE_UNAVAILABLE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DISABLED = "DISABLED"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


class ProviderStatus:
    def __init__(self, provider: str, state: str = ProviderState.DISABLED):
        self.provider = provider
        self.state = state
        self.last_checked = time.time()
        self.error_code = ""
        self.error_message = ""
        self.authenticated = False
        self.enabled = False
        self.last_success = 0.0
        self.latency_ms = 0.0

    def update(self, state: str, authenticated: bool = False, enabled: bool = False, error_msg: str = "", latency_ms: float = 0.0) -> None:
        self.state = state
        self.last_checked = time.time()
        self.authenticated = authenticated
        self.enabled = enabled
        self.error_message = error_msg
        self.latency_ms = latency_ms
        if state == ProviderState.LIVE_VERIFIED:
            self.last_success = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state,
            "last_checked": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_checked)),
            "authenticated": self.authenticated,
            "enabled": self.enabled,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms
        }


class StatusRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._statuses: Dict[str, ProviderStatus] = {
            "camera": ProviderStatus("camera"),
            "screen": ProviderStatus("screen"),
            "whatsapp": ProviderStatus("whatsapp"),
            "email": ProviderStatus("email"),
            "calendar": ProviderStatus("calendar"),
            "instagram": ProviderStatus("instagram"),
        }

    def update_status(self, provider: str, state: str, authenticated: bool = False, enabled: bool = False, error_msg: str = "") -> None:
        with self._lock:
            if provider in self._statuses:
                self._statuses[provider].update(state, authenticated, enabled, error_msg)

    def get_status(self, provider: str) -> Optional[ProviderStatus]:
        with self._lock:
            return self._statuses.get(provider)

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._statuses.items()}

    def get_summary_string(self) -> str:
        with self._lock:
            parts = []
            symbol_map = {
                ProviderState.LIVE_VERIFIED: "● LIVE",
                ProviderState.AUTHENTICATION_REQUIRED: "◐ AUTH",
                ProviderState.CONFIGURATION_REQUIRED: "○ CFG",
                ProviderState.HARDWARE_UNAVAILABLE: "× UNAVAIL",
                ProviderState.SERVICE_UNAVAILABLE: "× UNAVAIL",
                ProviderState.DISABLED: "○ OFF",
                ProviderState.PAUSED: "Ⅱ PAUSED",
                ProviderState.ERROR: "× ERR"
            }
            for p, name in [("camera", "CAM"), ("screen", "SCREEN"), ("whatsapp", "WA"), ("email", "MAIL"), ("calendar", "CAL"), ("instagram", "IG")]:
                st = self._statuses[p].state
                lbl = symbol_map.get(st, st)
                parts.append(f"{name} {lbl}")
            return "◈ AWARENESS: " + " | ".join(parts)


status_registry = StatusRegistry()
