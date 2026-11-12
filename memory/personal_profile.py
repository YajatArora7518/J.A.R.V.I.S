"""
memory/personal_profile.py
Persistent Personal Profile for J.A.R.V.I.S.

Tracks user preferences, communication style, and personal info.
Only learns when user explicitly provides information — never invents data.
Each field has: value, source, timestamp, confidence, user_confirmed.
Integrates with adaptive_intelligence.py as a data source.
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("JARVIS.PersonalProfile")

BASE_DIR = Path(__file__).resolve().parent.parent
PROFILE_FILE = BASE_DIR / "memory" / "personal_profile.json"

DEFAULT_PROFILE_FIELDS = [
    "name", "nickname", "language_preference", "communication_style",
    "hobbies", "projects", "coding_preferences", "productivity_preferences",
    "routines", "favorite_apps", "music_preference", "study_topics",
    "college", "branch", "year", "timezone",
]


class ProfileField:
    """A single tracked field in the personal profile."""
    def __init__(self, value: Any = None, source: str = "unknown", timestamp: float = 0.0, confidence: float = 0.0, user_confirmed: bool = False):
        self.value = value
        self.source = source  # "user_explicit" | "inferred" | "unknown"
        self.timestamp = timestamp or time.time()
        self.confidence = confidence
        self.user_confirmed = user_confirmed

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "user_confirmed": self.user_confirmed,
        }

    @staticmethod
    def from_dict(data: dict) -> "ProfileField":
        return ProfileField(
            value=data.get("value"),
            source=data.get("source", "unknown"),
            timestamp=data.get("timestamp", 0.0),
            confidence=data.get("confidence", 0.0),
            user_confirmed=data.get("user_confirmed", False),
        )


class PersonalProfile:
    """Manages persistent personal profile data."""

    def __init__(self):
        self._fields: Dict[str, ProfileField] = {}
        self._load()

    def _load(self):
        """Load profile from disk."""
        try:
            if PROFILE_FILE.exists():
                data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
                for key, field_data in data.get("fields", {}).items():
                    self._fields[key] = ProfileField.from_dict(field_data)
                logger.info(f"[PersonalProfile] Loaded {len(self._fields)} fields.")
        except Exception as e:
            logger.warning(f"[PersonalProfile] Could not load: {e}")

    def _save(self):
        """Persist profile to disk."""
        try:
            PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"fields": {k: v.to_dict() for k, v in self._fields.items()}}
            PROFILE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[PersonalProfile] Save failed: {e}")

    def set_field(self, key: str, value: Any, source: str = "user_explicit", confidence: float = 1.0) -> Dict[str, Any]:
        """Set or update a profile field."""
        key = key.lower().strip().replace(" ", "_")
        self._fields[key] = ProfileField(
            value=value,
            source=source,
            timestamp=time.time(),
            confidence=confidence,
            user_confirmed=(source == "user_explicit"),
        )
        self._save()
        logger.info(f"[PersonalProfile] Set '{key}' = '{value}' (source={source})")
        return {"success": True, "message": f"Noted: {key} = {value}"}

    def get_field(self, key: str) -> Optional[Any]:
        """Get a profile field value."""
        key = key.lower().strip().replace(" ", "_")
        field = self._fields.get(key)
        return field.value if field else None

    def get_field_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get full field metadata."""
        key = key.lower().strip().replace(" ", "_")
        field = self._fields.get(key)
        return field.to_dict() if field else None

    def get_all(self) -> Dict[str, Any]:
        """Return all profile fields as a simple dict."""
        return {k: v.value for k, v in self._fields.items() if v.value is not None}

    def get_summary(self) -> str:
        """Human-readable profile summary."""
        if not self._fields:
            return "No personal profile data saved yet."
        lines = []
        for k, v in self._fields.items():
            if v.value is not None:
                label = k.replace("_", " ").title()
                lines.append(f"- {label}: {v.value}")
        return "Personal Profile:\n" + "\n".join(lines) if lines else "No personal profile data saved yet."

    def delete_field(self, key: str) -> bool:
        """Delete a profile field (privacy control)."""
        key = key.lower().strip().replace(" ", "_")
        if key in self._fields:
            del self._fields[key]
            self._save()
            logger.info(f"[PersonalProfile] Deleted field: {key}")
            return True
        return False

    def clear_all(self) -> Dict[str, Any]:
        """Clear entire profile (privacy mode)."""
        count = len(self._fields)
        self._fields.clear()
        self._save()
        return {"success": True, "message": f"Cleared {count} profile fields."}


# Global singleton
_PERSONAL_PROFILE: Optional[PersonalProfile] = None

def get_personal_profile() -> PersonalProfile:
    global _PERSONAL_PROFILE
    if _PERSONAL_PROFILE is None:
        _PERSONAL_PROFILE = PersonalProfile()
    return _PERSONAL_PROFILE


def personal_profile_tool(
    parameters: Optional[Dict[str, Any]] = None,
    response: Any = None,
    player: Any = None,
    session_memory: Any = None,
    speak: Any = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Standard tool entry point for PersonalProfile."""
    params = dict(parameters) if isinstance(parameters, dict) else {}
    if kwargs:
        for k, v in kwargs.items():
            if k not in ("speak", "player", "response", "session_memory") and k not in params:
                params[k] = v

    action = params.get("action", "get").lower()
    profile = get_personal_profile()

    if action == "set":
        key = params.get("key", params.get("field", ""))
        value = params.get("value", "")
        if not key:
            return {"success": False, "message": "No field key provided."}
        return profile.set_field(key, value, source="user_explicit")

    elif action == "get":
        key = params.get("key", params.get("field", ""))
        if key:
            info = profile.get_field_info(key)
            if info:
                return {"success": True, "message": f"{key}: {info['value']}", "data": info}
            return {"success": False, "message": f"Field '{key}' not found in profile."}
        return {"success": True, "message": profile.get_summary()}

    elif action == "summary":
        return {"success": True, "message": profile.get_summary()}

    elif action == "delete":
        key = params.get("key", params.get("field", ""))
        ok = profile.delete_field(key)
        return {"success": ok, "message": f"Deleted '{key}'." if ok else f"Field '{key}' not found."}

    elif action == "clear":
        return profile.clear_all()

    return {"success": False, "message": f"Unknown profile action: {action}"}
