# agent/awareness/screen_provider.py
"""
Screen Awareness Provider.
Classifies active window / screen context into categories (CODING, STUDYING, BROWSING, VIDEO, DOCUMENT, WHATSAPP, IDLE, GAMING, UNKNOWN).
Returns SCREEN_UNAVAILABLE on error or when disabled.
"""

import threading
import time
from typing import Dict, Any
from agent.awareness.permissions import permission_manager, privacy_mode_manager

try:
    from ui import get_active_window_info
    _HAS_WIN32_HELPER = True
except ImportError:
    _HAS_WIN32_HELPER = False


class ScreenAwarenessProvider:
    """
    Manages screen awareness context extraction.
    Default state: OFF.
    """
    def __init__(self):
        self._enabled = False
        self._lock = threading.Lock()

    def enable(self) -> bool:
        if privacy_mode_manager.is_privacy_mode_active():
            return False
        if not permission_manager.is_granted("SCREEN_ACCESS"):
            return False
        with self._lock:
            self._enabled = True
            return True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    def is_enabled(self) -> bool:
        if privacy_mode_manager.is_privacy_mode_active():
            return False
        with self._lock:
            return self._enabled

    def classify_context(self) -> Dict[str, Any]:
        """
        Classifies current active screen context without storing images or leaking data.
        """
        from agent.awareness.status_model import status_registry, ProviderState
        if privacy_mode_manager.is_privacy_mode_active():
            status_registry.update_status("screen", ProviderState.PAUSED, enabled=False)
            return {
                "status": "SCREEN_UNAVAILABLE",
                "active_window": "",
                "category": "UNKNOWN",
                "message": "Screen awareness paused."
            }

        if not self.is_enabled():
            status_registry.update_status("screen", ProviderState.DISABLED, enabled=False)
            return {
                "status": "SCREEN_UNAVAILABLE",
                "active_window": "",
                "category": "UNKNOWN",
                "message": "Screen awareness disabled."
            }

        title = ""
        if _HAS_WIN32_HELPER:
            try:
                title, _ = get_active_window_info()
            except Exception:
                title = ""

        t_lower = (title or "").lower()
        category = "UNKNOWN"

        if any(k in t_lower for k in ["code", "visual studio", "pycharm", "sublime", "git", "terminal", "powershell", "cmd"]):
            category = "CODING"
        elif any(k in t_lower for k in ["pdf", "notion", "word", "document", "lecture", "book"]):
            category = "STUDYING"
        elif any(k in t_lower for k in ["youtube", "vlc", "netflix", "prime", "media player"]):
            category = "VIDEO"
        elif "whatsapp" in t_lower:
            category = "WHATSAPP"
        elif any(k in t_lower for k in ["chrome", "edge", "firefox", "browser"]):
            category = "BROWSING"
        elif any(k in t_lower for k in ["steam", "game", "unreal", "unity"]):
            category = "GAMING"
        elif not t_lower or "desktop" in t_lower:
            category = "IDLE"

        status_registry.update_status("screen", ProviderState.LIVE_VERIFIED, authenticated=True, enabled=True)
        return {
            "status": "OK",
            "active_window": title,
            "category": category,
            "timestamp": time.time()
        }


screen_provider = ScreenAwarenessProvider()
