# agent/awareness/permissions.py
"""
Granular Permission & Privacy Manager for JARVIS Ambient Awareness Subsystem.
Enforces strict read/write authorization and global Privacy Mode controls.
"""

import json
import threading
from typing import Dict, Any
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "awareness.json"

class PermissionManager:
    """
    Manages granular permissions for all awareness providers and companion features.
    Loads and persists permissions from config/awareness.json safely.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._permissions: Dict[str, bool] = {
            "CAMERA_ACCESS": False,
            "SCREEN_ACCESS": False,
            "WHATSAPP_READ": False,
            "WHATSAPP_WRITE": False,
            "EMAIL_READ": False,
            "EMAIL_WRITE": False,
            "CALENDAR_READ": False,
            "CALENDAR_WRITE": False,
            "INSTAGRAM_READ": False,
            "INSTAGRAM_WRITE": False,
            "COMPANION_MODE": False,
            "PROACTIVE_MODE": False,
        }
        self.load_config()

    def load_config(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                with self._lock:
                    self._permissions["CAMERA_ACCESS"] = bool(cfg.get("camera", False))
                    self._permissions["SCREEN_ACCESS"] = bool(cfg.get("screen", False))
                    self._permissions["WHATSAPP_READ"] = bool(cfg.get("whatsapp_read", False))
                    self._permissions["EMAIL_READ"] = bool(cfg.get("email_read", False))
                    self._permissions["CALENDAR_READ"] = bool(cfg.get("calendar_read", False))
                    self._permissions["INSTAGRAM_READ"] = bool(cfg.get("instagram_read", False))
                    self._permissions["PROACTIVE_MODE"] = bool(cfg.get("proactive_mode", False))
                    self._permissions["COMPANION_MODE"] = bool(cfg.get("companion_mode", False))
            except Exception:
                pass

    def save_config(self) -> None:
        try:
            with self._lock:
                cfg = {
                    "camera": self._permissions.get("CAMERA_ACCESS", False),
                    "screen": self._permissions.get("SCREEN_ACCESS", False),
                    "whatsapp_read": self._permissions.get("WHATSAPP_READ", False),
                    "email_read": self._permissions.get("EMAIL_READ", False),
                    "calendar_read": self._permissions.get("CALENDAR_READ", False),
                    "instagram_read": self._permissions.get("INSTAGRAM_READ", False),
                    "proactive_mode": self._permissions.get("PROACTIVE_MODE", False),
                    "companion_mode": self._permissions.get("COMPANION_MODE", False),
                    "sleep_reminder": True,
                    "sleep_time": "01:00",
                    "global_cooldown_seconds": 300
                }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def is_granted(self, permission_name: str) -> bool:
        with self._lock:
            return self._permissions.get(permission_name, False)

    def set_permission(self, permission_name: str, granted: bool) -> None:
        with self._lock:
            if permission_name in self._permissions:
                self._permissions[permission_name] = bool(granted)
        self.save_config()

    def get_all_permissions(self) -> Dict[str, bool]:
        with self._lock:
            return dict(self._permissions)


class PrivacyModeManager:
    """
    Global Privacy Mode controller.
    When activated, immediately halts camera, screen, external service analysis,
    and proactive companion notifications.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._privacy_mode = False
        self._paused = False

    def is_privacy_mode_active(self) -> bool:
        with self._lock:
            return self._privacy_mode or self._paused

    def set_privacy_mode(self, active: bool) -> None:
        with self._lock:
            self._privacy_mode = bool(active)

    def enable_privacy_mode(self) -> None:
        self.set_privacy_mode(True)

    def disable_privacy_mode(self) -> None:
        self.set_privacy_mode(False)

    def pause_all_awareness(self, paused: bool = True) -> None:
        with self._lock:
            self._paused = bool(paused)

    def resume_awareness(self) -> None:
        with self._lock:
            self._privacy_mode = False
            self._paused = False


# Global singleton instances
permission_manager = PermissionManager()
privacy_mode_manager = PrivacyModeManager()
