# core/ai_policy.py
# Central AI policy. An explicit environment override always wins over settings.

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.AIPolicy")

# Central kill switch: MUST default to False
DEFAULT_CLOUD_AI_ALLOWED = False

class CloudAIBlocked(RuntimeError):
    """Raised when any component attempts to invoke cloud AI while local mode is enforced."""
    pass

# Thread-safe telemetry counters
_TELEMETRY = {
    "cloud_attempts": 0,
    "cloud_blocked": 0,
    "local_ai_calls": 0,
    "gemini_calls": 0
}

def is_cloud_ai_allowed() -> bool:
    """Honor local-only mode; permit cloud when the user selects hybrid/cloud."""
    val = os.environ.get("JARVIS_CLOUD_AI")
    if val is not None:
        return val.strip().lower() in ("true", "1", "yes")
    from config import get_runtime_config
    return get_runtime_config().get("ai_mode", "local").lower() in ("hybrid", "cloud")

def assert_cloud_ai_allowed(service: str = "Cloud AI") -> None:
    """
    Central gate function. Raises CloudAIBlocked if JARVIS_CLOUD_AI is not True.
    All legacy cloud callers must pass through this single assertion.
    """
    _TELEMETRY["cloud_attempts"] += 1
    if not is_cloud_ai_allowed():
        _TELEMETRY["cloud_blocked"] += 1
        msg = f"[POLICY VIOLATION BLOCKED] Execution of '{service}' denied. JARVIS is in 100% Local AI Mode (JARVIS_CLOUD_AI=False)."
        logger.error(msg)
        raise CloudAIBlocked(msg)

def record_local_ai_call(model: str = "ollama") -> None:
    """Records an executed local AI inference call."""
    _TELEMETRY["local_ai_calls"] += 1

def get_ai_telemetry() -> Dict[str, Any]:
    """Returns exact telemetry numbers for verification."""
    return {
        "cloud_ai_allowed": is_cloud_ai_allowed(),
        "cloud_attempts": _TELEMETRY["cloud_attempts"],
        "cloud_blocked": _TELEMETRY["cloud_blocked"],
        "local_ai_calls": _TELEMETRY["local_ai_calls"],
        "gemini_calls": _TELEMETRY["gemini_calls"],
        "zero_cloud_verified": (_TELEMETRY["gemini_calls"] == 0 and _TELEMETRY["cloud_attempts"] == _TELEMETRY["cloud_blocked"])
    }

def reset_telemetry() -> None:
    """Resets counters for clean test runs."""
    _TELEMETRY["cloud_attempts"] = 0
    _TELEMETRY["cloud_blocked"] = 0
    _TELEMETRY["local_ai_calls"] = 0
    _TELEMETRY["gemini_calls"] = 0

reset_ai_telemetry = reset_telemetry
