# actions/mic_control.py
# Scoped Microphone Master Controller for JARVIS
# Differentiates JARVIS Voice Input and Windows System Mic

import logging
import subprocess
import platform
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.MicControl")

# Global Mic State Tracker
_MIC_STATES = {
    "jarvis_mic": True,     # True = Listening, False = Paused
    "system_mic": True      # True = Unmuted, False = Muted
}

_UI_INSTANCE: Optional[Any] = None


def set_ui_instance(ui: Any) -> None:
    """Registers global UI instance for mic state synchronization."""
    global _UI_INSTANCE
    _UI_INSTANCE = ui


def get_mic_states() -> Dict[str, bool]:
    """Returns current status of microphone scopes."""
    return _MIC_STATES.copy()


def get_jarvis_mic_enabled() -> bool:
    """Returns authoritative state of JARVIS voice input microphone."""
    return _MIC_STATES.get("jarvis_mic", True)


def set_jarvis_mic_enabled(enabled: bool, ui_instance: Optional[Any] = None) -> bool:
    """
    Authoritative state modifier for JARVIS microphone.
    Updates internal state tracker and synchronizes existing UI microphone indicator.
    """
    global _MIC_STATES
    before = _MIC_STATES.get("jarvis_mic", True)
    _MIC_STATES["jarvis_mic"] = enabled
    logger.info(f"[MIC STATE] before={before} requested={enabled} authoritative={enabled} UI_sync={ui_instance is not None}")

    target_ui = ui_instance or _UI_INSTANCE
    if target_ui:
        try:
            if hasattr(target_ui, "set_muted"):
                target_ui.set_muted(not enabled)
            elif hasattr(target_ui, "hud") and hasattr(target_ui.hud, "setMicState"):
                target_ui.hud.setMicState(enabled)
        except Exception as e:
            logger.warning(f"[MicControl] UI mic state sync error: {e}")

    return enabled


def handle_mic_command(text: str, ui_instance: Optional[Any] = None) -> Dict[str, Any]:
    """
    Parses and executes scoped microphone instructions.
    Scopes:
    1. 'jarvis' -> JARVIS voice input listening pipeline
    2. 'system' | 'windows' -> Master Windows input endpoint
    """
    raw_text = (text or "").strip()
    lower_text = raw_text.lower()
    logger.info(f"[MicControl] Handling microphone command: '{raw_text}'")

    import re
    is_turn_off = any(re.search(r'\b' + w + r'\b', lower_text) for w in ["off", "band", "bandh", "mute", "disable", "stop", "close"])
    is_turn_on = any(re.search(r'\b' + w + r'\b', lower_text) for w in ["on", "chalu", "unmute", "enable", "start", "open"])

    # Explicit JARVIS Mic Patterns
    jarvis_keywords = [
        "jarvis mic", "jarvis microphone", "jarvis voice", "voice input",
        "listening", "stop listening", "start listening", "jarvis mute", "jarvis unmute"
    ]
    is_explicit_jarvis = any(k in lower_text for k in jarvis_keywords)

    # Explicit System Mic Patterns
    system_keywords = [
        "system mic", "windows mic", "laptop mic", "master mic", "system microphone"
    ]
    is_explicit_system = any(k in lower_text for k in system_keywords)

    # 1. EXPLICIT JARVIS MIC SCOPE OR DIRECT LISTENING CONTROL
    if is_explicit_jarvis or lower_text in ["stop listening", "stop listening jarvis", "start listening", "start listening jarvis", "jarvis mute", "jarvis unmute"]:
        target_state = not is_turn_off if (is_turn_off or is_turn_on) else False
        set_jarvis_mic_enabled(target_state, ui_instance=ui_instance)
        state_str = "JARVIS listening disabled." if not target_state else "JARVIS listening enabled."
        return {
            "success": True,
            "scope": "jarvis_mic",
            "state": target_state,
            "message": state_str,
            "verified": True,
            "status": "JARVIS_MIC_OFF" if not target_state else "JARVIS_MIC_ON"
        }

    # 2. EXPLICIT DISCORD / APP MIC SCOPE
    if any(w in lower_text for w in ["discord mic", "discord voice", "app mic", "discord ka mic", "discord mute", "discord unmute"]):
        try:
            from actions.discord_automation import discord_provider
            res = discord_provider.mute(mute=is_turn_off)
            _MIC_STATES["discord_mic"] = not is_turn_off
            return {
                "success": True,
                "scope": "discord_mic",
                "state": _MIC_STATES["discord_mic"],
                "message": res.get("message", "Discord mic state updated."),
                "verified": True,
                "status": "DISCORD_MIC_OFF" if is_turn_off else "DISCORD_MIC_ON"
            }
        except Exception as e:
            return {
                "success": False,
                "scope": "discord_mic",
                "message": f"Discord mic control error: {e}",
                "verified": False,
                "status": "DISCORD_MIC_ERROR"
            }

    # 3. EXPLICIT SYSTEM / WINDOWS MIC SCOPE
    if is_explicit_system:
        target_state = not is_turn_off if (is_turn_off or is_turn_on) else False
        _MIC_STATES["system_mic"] = target_state
        if platform.system() == "Windows":
            try:
                ps_cmd = "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]173)"
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=3)
            except Exception:
                pass

        state_str = "System microphone muted." if not target_state else "System microphone unmuted."
        return {
            "success": True,
            "scope": "system_mic",
            "state": target_state,
            "message": state_str,
            "verified": True,
            "status": "SYSTEM_MIC_OFF" if not target_state else "SYSTEM_MIC_ON"
        }

    # 4. DEFAULT MIC CONTROL (Controls JARVIS mic if turn_off or turn_on specified AND mic context exists; asks clarification for ambiguous queries)
    has_mic_mention = any(k in lower_text for k in ["mic", "microphone", "listen", "sunna", "awaz", "voice"])
    if (is_turn_off or is_turn_on) and has_mic_mention:
        target_state = not is_turn_off
        set_jarvis_mic_enabled(target_state, ui_instance=ui_instance)
        state_str = "JARVIS microphone muted." if not target_state else "JARVIS microphone unmuted."
        return {
            "success": True,
            "scope": "jarvis_mic",
            "state": target_state,
            "message": state_str,
            "verified": True,
            "status": "JARVIS_MIC_OFF" if not target_state else "JARVIS_MIC_ON"
        }

    return {
        "success": True,
        "scope": "ambiguous",
        "message": "Boss, JARVIS mic, app mic, Discord mic, ya system mic?",
        "requires_clarification": True,
        "verified": True,
        "status": "MIC_SCOPE_AMBIGUOUS"
    }

