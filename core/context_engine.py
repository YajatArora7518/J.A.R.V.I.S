# core/context_engine.py
# Unified Multi-source Context Engine for JARVIS

import time
import platform
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    import pygetwindow as gw
    _HAS_PYGETWINDOW = True
except Exception:
    _HAS_PYGETWINDOW = False


@dataclass
class UnifiedContext:
    user_name: str = "Yajat"
    active_app: str = ""
    active_window_title: str = ""
    current_task_goal: str = ""
    current_step_desc: str = ""
    screen_summary: str = ""
    camera_active: bool = False
    battery_percent: Optional[int] = None
    network_online: bool = True
    recent_actions: List[str] = field(default_factory=list)
    relevant_memory: Dict[str, Any] = field(default_factory=dict)
    permissions_level: str = "NORMAL"

    def update_active_window(self) -> None:
        """Queries Windows API for active foreground window."""
        if _HAS_PYGETWINDOW:
            try:
                active_win = gw.getActiveWindow()
                if active_win and active_win.title:
                    self.active_window_title = active_win.title.strip()
            except Exception:
                pass

        if _HAS_PSUTIL:
            try:
                # System battery check
                battery = psutil.sensors_battery()
                if battery:
                    self.battery_percent = int(battery.percent)
            except Exception:
                pass

    def add_action(self, action_summary: str) -> None:
        """Appends recent tool action to transient context memory."""
        self.recent_actions.append(f"[{time.strftime('%H:%M:%S')}] {action_summary}")
        if len(self.recent_actions) > 10:
            self.recent_actions.pop(0)

    def to_prompt_string(self) -> str:
        """Formats context block for LLM system prompts."""
        self.update_active_window()
        parts = [
            f"[CONTEXT ENGINE]",
            f"User: {self.user_name}",
            f"OS: {platform.system()} {platform.release()}",
            f"Active Window: {self.active_window_title or 'Desktop'}",
            f"Camera Status: {'ACTIVE' if self.camera_active else 'OFF'}",
        ]
        if self.battery_percent is not None:
            parts.append(f"Battery: {self.battery_percent}%")
        if self.current_task_goal:
            parts.append(f"Active Task Goal: {self.current_task_goal}")
            if self.current_step_desc:
                parts.append(f"Active Step: {self.current_step_desc}")
        if self.screen_summary:
            parts.append(f"Screen Context: {self.screen_summary[:200]}")
        if self.recent_actions:
            parts.append("Recent Actions:\n" + "\n".join(self.recent_actions[-3:]))

        return "\n".join(parts)


@dataclass
class ConversationState:
    """Rich continuous conversation state tracking for local reference resolution."""
    current_topic: str = ""
    last_contact: Optional[str] = None
    last_app: Optional[str] = None
    last_file: Optional[str] = None
    last_website: Optional[str] = None
    last_device: str = "pc"  # "pc", "phone", "tablet"
    last_intent: Optional[str] = None
    last_tool_result: Optional[str] = None
    pending_action: Optional[Dict[str, Any]] = None
    active_task: Optional[str] = None
    active_call: Optional[Dict[str, Any]] = None
    current_conversation_goal: str = ""

    def update(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self, k) and v is not None:
                setattr(self, k, v)

    def resolve_reference(self, text: str) -> Dict[str, Any]:
        """
        Resolves pronouns ('usko', 'usse', 'wahi', 'woh', 'same person', 'same app', etc.)
        against conversation state locally without LLM calls.
        """
        lower = text.lower().strip()
        result = {"resolved": False, "substituted_text": text, "target_type": None, "target_value": None}

        # Contact references
        if any(p in lower for p in ["usko", "usse", "same person", "same contact", "him", "her"]):
            if self.last_contact:
                sub = lower
                for p in ["usko", "usse", "same person", "same contact", "him", "her"]:
                    sub = sub.replace(p, self.last_contact)
                result.update({
                    "resolved": True,
                    "substituted_text": sub,
                    "target_type": "contact",
                    "target_value": self.last_contact
                })
                return result

        # App / Window references
        if any(p in lower for p in ["wahi app", "same app", "wahi kholo", "usme", "same window"]):
            if self.last_app:
                result.update({
                    "resolved": True,
                    "substituted_text": text.replace("wahi app", self.last_app).replace("wahi", self.last_app),
                    "target_type": "app",
                    "target_value": self.last_app
                })
                return result

        # File references
        if any(p in lower for p in ["wahi file", "same file", "woh file"]):
            if self.last_file:
                result.update({
                    "resolved": True,
                    "substituted_text": text.replace("wahi file", self.last_file).replace("woh file", self.last_file),
                    "target_type": "file",
                    "target_value": self.last_file
                })
                return result

        # Website references
        if any(p in lower for p in ["wahi site", "wahi website", "same site"]):
            if self.last_website:
                result.update({
                    "resolved": True,
                    "substituted_text": text.replace("wahi site", self.last_website).replace("same site", self.last_website),
                    "target_type": "website",
                    "target_value": self.last_website
                })
                return result

        return result


# Global singleton instances
default_context_engine = UnifiedContext()
conversation_state = ConversationState()
