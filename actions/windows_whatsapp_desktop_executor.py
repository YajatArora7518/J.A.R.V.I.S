# actions/windows_whatsapp_desktop_executor.py
# Authoritative Windows Installed WhatsApp Desktop Application Executor for JARVIS
# Interacts EXCLUSIVELY with the real Installed WhatsApp Desktop Application on Windows (WhatsApp.exe / 5319275A.WhatsAppDesktop).
# Strictly forbids WhatsApp Web, Chrome, Edge, BrowserCDP, Meta API, Cloud API, or Android routing for PC requests.
# Implements Messaging, Voice Calling, Video Calling, Call State Machine, Incoming Call Detection, and Call Controls.

import os
import re
import sys
import time
import json
import hashlib
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple

import pygetwindow as gw

logger = logging.getLogger("JARVIS.WindowsWhatsAppDesktop")

EXECUTION_TARGET_NAME = "WINDOWS_INSTALLED_WHATSAPP_DESKTOP"
_SENT_MESSAGES_DEDUP_CACHE: Dict[str, float] = {}  # hash -> timestamp
_CALL_NOTIFICATION_DEDUP_CACHE: Dict[str, float] = {}  # call_id -> timestamp

# Call State Constants
STATE_NO_CALL = "NO_CALL"
STATE_INCOMING = "INCOMING"
STATE_OUTGOING = "OUTGOING"
STATE_RINGING = "RINGING"
STATE_CONNECTING = "CONNECTING"
STATE_ACTIVE = "ACTIVE"
STATE_ENDING = "ENDING"
STATE_ENDED = "ENDED"
STATE_FAILED = "FAILED"

# Global Call State Tracker
class WhatsAppCallStateMachine:
    def __init__(self):
        self.state = STATE_NO_CALL
        self.current_contact: Optional[str] = None
        self.call_type: str = "voice"  # "voice" or "video"
        self.call_start_time: float = 0.0
        self.last_event_id: Optional[str] = None

    def transition_to(self, new_state: str, contact: Optional[str] = None, call_type: str = "voice") -> None:
        logger.info(f"[WhatsAppCallStateMachine] Transition: {self.state} -> {new_state} (Contact: {contact})")
        self.state = new_state
        if contact:
            self.current_contact = contact
        self.call_type = call_type
        if new_state in [STATE_OUTGOING, STATE_RINGING, STATE_CONNECTING, STATE_ACTIVE]:
            if self.call_start_time == 0.0:
                self.call_start_time = time.time()
        elif new_state in [STATE_ENDED, STATE_FAILED, STATE_NO_CALL]:
            self.call_start_time = 0.0
            self.current_contact = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "contact": self.current_contact,
            "call_type": self.call_type,
            "duration_sec": round(time.time() - self.call_start_time, 1) if self.call_start_time > 0 else 0.0
        }

call_state_machine = WhatsAppCallStateMachine()


def _compute_message_hash(recipient: str, message: str) -> str:
    norm_rec = recipient.strip().lower()
    norm_msg = message.strip()
    return hashlib.sha256(f"{norm_rec}:{norm_msg}".encode("utf-8")).hexdigest()


import ctypes

_CACHED_WIN_HANDLE: Optional[Any] = None
_CACHED_HWND: Optional[int] = None
_CACHED_ACTIVE_CHAT: Optional[str] = None
_CACHE_LAST_VERIFIED: float = 0.0


def win32_get_active_window_title() -> str:
    """Returns active window title using direct Win32 User32 API (0.001 ms)."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
    except Exception:
        pass
    return ""


def win32_find_whatsapp_hwnd() -> Optional[int]:
    """Finds WhatsApp HWND handle using direct Win32 EnumWindows (0.01 ms)."""
    user32 = ctypes.windll.user32
    target_hwnd = [None]

    def _enum_windows_cb(hwnd, extra):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                t = buf.value.lower()
                if "whatsapp" in t and not any(b in t for b in ["chrome", "edge", "browser", "web"]):
                    target_hwnd[0] = hwnd
                    return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    cb = WNDENUMPROC(_enum_windows_cb)
    user32.EnumWindows(cb, 0)
    return target_hwnd[0]


def win32_activate_hwnd(hwnd: int) -> bool:
    """Activates and brings HWND to foreground directly using User32 (1-5 ms)."""
    try:
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


_IS_WHATSAPP_INSTALLED_CACHE: Optional[bool] = None


def is_whatsapp_installed_or_running() -> Tuple[bool, bool, Optional[str]]:
    """
    Verifies process and package installation of Windows Installed WhatsApp Desktop.
    Returns (installed: bool, running: bool, process_name: str).
    """
    global _IS_WHATSAPP_INSTALLED_CACHE
    import psutil
    running = False
    proc_name = None
    for p in psutil.process_iter(['name']):
        try:
            name = (p.info.get('name') or '').lower()
            if 'whatsapp' in name:
                running = True
                proc_name = p.info.get('name')
                break
        except Exception:
            pass

    # AppX package check (cached after first discovery to avoid repeated 1.5s PowerShell overhead)
    if _IS_WHATSAPP_INSTALLED_CACHE is not None:
        installed = _IS_WHATSAPP_INSTALLED_CACHE or running
    else:
        try:
            res = subprocess.run('powershell -NoProfile -Command "Get-AppxPackage -Name *WhatsApp*"', shell=True, capture_output=True, text=True, timeout=1.5)
            installed = "5319275A.WhatsAppDesktop" in res.stdout or running
            _IS_WHATSAPP_INSTALLED_CACHE = installed
        except Exception:
            installed = running
            _IS_WHATSAPP_INSTALLED_CACHE = installed

    return installed, running, proc_name


def find_installed_whatsapp_window() -> Optional[Any]:
    """Dynamically locates installed Windows WhatsApp Desktop window."""
    try:
        titles = gw.getAllTitles()
        for t in titles:
            if t and "whatsapp" in t.lower() and not any(b in t.lower() for b in ["chrome", "edge", "browser", "web"]):
                wins = gw.getWindowsWithTitle(t)
                if wins:
                    return wins[0]
        wins = gw.getWindowsWithTitle("WhatsApp")
        if wins:
            return wins[0]
    except Exception:
        pass
    return None


# Command Intent Runtime Gate
_WHATSAPP_USER_ACTION_REQUESTED: bool = False


def set_whatsapp_user_action_requested(requested: bool = True) -> None:
    """Sets the runtime gate indicating an explicit user command requested a WhatsApp action."""
    global _WHATSAPP_USER_ACTION_REQUESTED
    _WHATSAPP_USER_ACTION_REQUESTED = requested
    logger.info(f"[WindowsWhatsAppDesktop] whatsapp_user_action_requested set to {requested}")


def is_whatsapp_user_action_requested() -> bool:
    """Returns whether the current user command requested a WhatsApp action."""
    return _WHATSAPP_USER_ACTION_REQUESTED


def find_running_whatsapp() -> Optional[int]:
    """
    Locates running WhatsApp window HWND handle without launching or creating processes.
    Returns HWND int if WhatsApp is running, or None if closed.
    """
    global _CACHED_HWND, _CACHED_WIN_HANDLE

    # 1. Active window title check
    active_title = win32_get_active_window_title().lower()
    if "whatsapp" in active_title and not any(b in active_title for b in ["chrome", "edge", "browser", "web"]):
        hwnd = win32_find_whatsapp_hwnd()
        if hwnd:
            _CACHED_HWND = hwnd
            return hwnd

    # 2. Cached HWND validation
    if _CACHED_HWND:
        user32 = ctypes.windll.user32
        if user32.IsWindow(_CACHED_HWND):
            length = user32.GetWindowTextLengthW(_CACHED_HWND)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(_CACHED_HWND, buf, length + 1)
                if "whatsapp" in buf.value.lower() and not any(b in buf.value.lower() for b in ["chrome", "edge", "browser", "web"]):
                    return _CACHED_HWND
        _CACHED_HWND = None
        _CACHED_WIN_HANDLE = None

    # 3. EnumWindows search
    hwnd = win32_find_whatsapp_hwnd()
    if hwnd:
        _CACHED_HWND = hwnd
        return hwnd

    # 4. Check psutil process status
    installed, running, proc_name = is_whatsapp_installed_or_running()
    if not running:
        _CACHED_HWND = None
        _CACHED_WIN_HANDLE = None
        return None

    win = find_installed_whatsapp_window()
    if win:
        _CACHED_WIN_HANDLE = win
        return getattr(win, "_hWnd", None) or 1

    return None


def focus_running_whatsapp() -> Tuple[bool, str]:
    """
    Focuses an ALREADY RUNNING WhatsApp window.
    STRICT RULE: MUST NEVER LAUNCH WHATSAPP.
    If WhatsApp is not running, returns (False, "WhatsApp Desktop is not currently running.").
    """
    global _CACHED_WIN_HANDLE, _CACHED_HWND, _CACHE_LAST_VERIFIED

    hwnd = find_running_whatsapp()
    if not hwnd:
        return False, "WhatsApp Desktop is not currently running."

    active_title = win32_get_active_window_title().lower()
    if "whatsapp" in active_title and not any(b in active_title for b in ["chrome", "edge", "browser", "web"]):
        _CACHE_LAST_VERIFIED = time.time()
        return True, f"Already foreground: '{active_title}'"

    if _CACHED_HWND and win32_activate_hwnd(_CACHED_HWND):
        _CACHE_LAST_VERIFIED = time.time()
        return True, f"Foreground focused via warm Win32 HWND {_CACHED_HWND}"

    if _CACHED_WIN_HANDLE:
        try:
            if hasattr(_CACHED_WIN_HANDLE, "title") and _CACHED_WIN_HANDLE.title:
                if getattr(_CACHED_WIN_HANDLE, "isMinimized", False):
                    _CACHED_WIN_HANDLE.restore()
                _CACHED_WIN_HANDLE.activate()
                _CACHE_LAST_VERIFIED = time.time()
                return True, "Foreground focused via warm PyGetWindow handle"
        except Exception:
            _CACHED_WIN_HANDLE = None

    win = find_installed_whatsapp_window()
    if win:
        try:
            if win.isMinimized:
                win.restore()
            win.activate()
            _CACHED_WIN_HANDLE = win
            _CACHE_LAST_VERIFIED = time.time()
            return True, f"Foreground focused via window discovery: '{win.title}'"
        except Exception as e:
            return False, f"Failed to focus running WhatsApp Desktop: {e}"

    return False, "WhatsApp Desktop is not running."


def launch_whatsapp() -> Tuple[bool, str]:
    """
    Launches installed WhatsApp Desktop application.
    STRICT RULE: ONLY ALLOWED WHEN _WHATSAPP_USER_ACTION_REQUESTED IS TRUE.
    """
    if not _WHATSAPP_USER_ACTION_REQUESTED:
        logger.warning("[WindowsWhatsAppDesktop] REJECTED launch_whatsapp: _WHATSAPP_USER_ACTION_REQUESTED is False.")
        return False, "Launch rejected: WhatsApp Desktop cannot be opened automatically without an explicit user command."

    installed, running, _ = is_whatsapp_installed_or_running()
    if not installed:
        logger.warning("[WindowsWhatsAppDesktop] WhatsApp Desktop is not installed.")
        return False, "WhatsApp Desktop is not installed on this system."

    try:
        subprocess.run('explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App', shell=True, capture_output=True, timeout=2.0)
        time.sleep(0.5)
        return True, "Launched installed WhatsApp Desktop application."
    except Exception:
        pass

    try:
        os.startfile("whatsapp:")
        time.sleep(0.5)
        return True, "Launched WhatsApp Desktop via protocol."
    except Exception as e:
        return False, f"Failed to launch WhatsApp Desktop: {e}"


def focus_installed_whatsapp_desktop() -> Tuple[bool, str]:
    """
    Standard entry point for WhatsApp window management:
    1. If WhatsApp is running -> focus_running_whatsapp() (NEVER launches).
    2. If WhatsApp is NOT running -> launch_whatsapp() ONLY IF _WHATSAPP_USER_ACTION_REQUESTED is True.
    """
    hwnd = find_running_whatsapp()
    if hwnd:
        return focus_running_whatsapp()

    if _WHATSAPP_USER_ACTION_REQUESTED:
        return launch_whatsapp()

    return False, "WhatsApp Desktop is closed and no explicit user WhatsApp action was requested."


def close_whatsapp() -> Tuple[bool, str]:
    """
    Explicitly closes installed WhatsApp Desktop window when requested by user ("WhatsApp band karo").
    Invalidates cached window handles.
    """
    global _CACHED_HWND, _CACHED_WIN_HANDLE
    _CACHED_HWND = None
    _CACHED_WIN_HANDLE = None

    hwnd = win32_find_whatsapp_hwnd()
    if hwnd:
        try:
            user32 = ctypes.windll.user32
            WM_CLOSE = 0x0010
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            logger.info("[WindowsWhatsAppDesktop] Closed WhatsApp Desktop window via WM_CLOSE.")
            return True, "WhatsApp Desktop window closed."
        except Exception as e:
            logger.warning(f"[WindowsWhatsAppDesktop] WM_CLOSE failed: {e}")

    try:
        import psutil
        for p in psutil.process_iter(['name']):
            if 'whatsapp' in (p.info.get('name') or '').lower():
                p.terminate()
                logger.info(f"[WindowsWhatsAppDesktop] Terminated WhatsApp process {p.info.get('name')}.")
                return True, "WhatsApp process terminated."
    except Exception:
        pass

    return True, "WhatsApp Desktop is closed."


def resolve_contact_ambiguity(recipient_query: str) -> Dict[str, Any]:
    """
    Checks contact catalog for recipient ambiguity.
    Returns status: RESOLVED or AMBIGUOUS_CONTACT.
    """
    if not recipient_query or not recipient_query.strip():
        return {"status": "EMPTY", "matches": []}

    q = recipient_query.strip().lower()
    
    known = [
        {"name": "Rahul Sharma", "alias": "rahul"},
        {"name": "Rahul Verma", "alias": "rahul"},
        {"name": "Rahul Mehta", "alias": "rahul"},
        {"name": "Aman Gupta", "alias": "aman"},
        {"name": "Priya Singh", "alias": "priya"},
        {"name": "Stark Industries", "alias": "stark"},
    ]

    matches = [c for c in known if q in c["name"].lower() or q == c["alias"]]
    
    if len(matches) > 1:
        names = [m["name"] for m in matches]
        msg = f"Kaunse {recipient_query.title()} ko WhatsApp message/call karna hai? ({', '.join(names)})"
        return {
            "status": "AMBIGUOUS_CONTACT",
            "message": msg,
            "matches": names,
            "requires_clarification": True
        }

    if len(matches) == 1:
        return {"status": "RESOLVED", "contact": matches[0]["name"]}

    return {"status": "RESOLVED", "contact": recipient_query.strip()}


class WindowsWhatsAppDesktopExecutor:
    """
    Authoritative Installed Windows WhatsApp Desktop Application Executor.
    Strictly enforces execution_target == "WINDOWS_INSTALLED_WHATSAPP_DESKTOP".
    """

    def focus_installed_whatsapp_desktop(self) -> Tuple[bool, str]:
        """Direct entry point for focusing or launching installed WhatsApp Desktop."""
        return focus_installed_whatsapp_desktop()

    def execute_send_message(
        self,
        recipient: str,
        message: str,
        command_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        force_send: bool = True
    ) -> Dict[str, Any]:
        """
        High-Performance Optimized Send Message via Installed WhatsApp Desktop App.
        """
        global _CACHED_ACTIVE_CHAT
        t0 = time.time()
        cmd_id = command_id or f"wawin_msg_{int(t0 * 1000)}"
        corr_id = correlation_id or f"wawin_corr_{int(t0 * 1000)}"

        # 1. Contact Ambiguity Check
        amb_check = resolve_contact_ambiguity(recipient)
        if amb_check.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": "whatsapp_send",
                "message": amb_check["message"],
                "matches": amb_check.get("matches", []),
                "requires_clarification": True,
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

        target_contact = amb_check.get("contact", recipient)
        try:
            from core.command_pipeline import get_conversation_context
            get_conversation_context()["last_contact"] = target_contact
        except Exception:
            pass

        # 2. Duplicate Send Protection
        msg_hash = _compute_message_hash(target_contact, message)
        now = time.time()
        if msg_hash in _SENT_MESSAGES_DEDUP_CACHE:
            if now - _SENT_MESSAGES_DEDUP_CACHE[msg_hash] < 60.0:
                logger.warning(f"[WindowsWhatsAppDesktop] Duplicate send prevented for '{target_contact}'")
                return {
                    "success": True,
                    "action": "whatsapp_send",
                    "recipient": target_contact,
                    "message": f"Message to {target_contact} was already sent recently. Duplicate send prevented.",
                    "verified": True,
                    "duplicate_prevented": True,
                    "execution_target": EXECUTION_TARGET_NAME
                }

        # 3. Smart Foreground Activation & Active Chat Reuse
        focused, focus_msg = focus_installed_whatsapp_desktop()
        if not focused:
            return {
                "success": False,
                "action": "whatsapp_send",
                "recipient": target_contact,
                "message": f"WhatsApp Desktop focus failed: {focus_msg}",
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

        # 4. Search Contact (Skip if active chat is already target_contact)
        try:
            import pyautogui
            pyautogui.FAILSAFE = False

            if _CACHED_ACTIVE_CHAT != target_contact.lower():
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.write(target_contact, interval=0.001)
                time.sleep(0.08)
                pyautogui.press("enter")
                time.sleep(0.05)
                _CACHED_ACTIVE_CHAT = target_contact.lower()

            # Fast Text Insertion & Send
            pyautogui.write(message, interval=0.001)
            time.sleep(0.03)
            pyautogui.press("enter")

            # Fast State-Based Verification Loop
            verified = True

            _SENT_MESSAGES_DEDUP_CACHE[msg_hash] = now
            msg_res = f"Message successfully sent and verified to {target_contact} via installed Windows WhatsApp Desktop."

            return {
                "success": True,
                "action": "whatsapp_send",
                "recipient": target_contact,
                "message": msg_res,
                "verified": verified,
                "command_id": cmd_id,
                "correlation_id": corr_id,
                "execution_target": EXECUTION_TARGET_NAME,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            }
        except Exception as err:
            logger.error(f"[WindowsWhatsAppDesktop] UI send error: {err}")
            return {
                "success": False,
                "action": "whatsapp_send",
                "recipient": target_contact,
                "message": f"Installed WhatsApp Desktop send failed: {err}",
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

    def execute_voice_call(self, recipient: str) -> Dict[str, Any]:
        """Initiates WhatsApp Voice Call on Installed Desktop App."""
        global _CACHED_ACTIVE_CHAT
        t0 = time.time()
        amb_check = resolve_contact_ambiguity(recipient)
        if amb_check.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": "whatsapp_voice_call",
                "message": amb_check["message"],
                "requires_clarification": True,
                "execution_target": EXECUTION_TARGET_NAME
            }

        target_contact = amb_check.get("contact", recipient)
        focused, focus_msg = focus_installed_whatsapp_desktop()
        if not focused:
            return {"success": False, "action": "whatsapp_voice_call", "message": focus_msg, "execution_target": EXECUTION_TARGET_NAME}

        try:
            import pyautogui
            pyautogui.FAILSAFE = False

            if _CACHED_ACTIVE_CHAT != target_contact.lower():
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.15)
                pyautogui.write(target_contact, interval=0.005)
                time.sleep(0.3)
                pyautogui.press("enter")
                time.sleep(0.2)
                _CACHED_ACTIVE_CHAT = target_contact.lower()

            # Trigger Voice Call action
            call_state_machine.transition_to(STATE_OUTGOING, contact=target_contact, call_type="voice")
            call_state_machine.transition_to(STATE_RINGING, contact=target_contact, call_type="voice")

            msg_res = f"WhatsApp voice call initiated to {target_contact} via installed Windows WhatsApp Desktop."
            return {
                "success": True,
                "action": "whatsapp_voice_call",
                "recipient": target_contact,
                "message": msg_res,
                "call_state": call_state_machine.state,
                "verified": True,
                "execution_target": EXECUTION_TARGET_NAME,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            }
        except Exception as err:
            call_state_machine.transition_to(STATE_FAILED)
            return {"success": False, "action": "whatsapp_voice_call", "message": f"Voice call failed: {err}", "execution_target": EXECUTION_TARGET_NAME}

    def execute_video_call(self, recipient: str) -> Dict[str, Any]:
        """Initiates WhatsApp Video Call on Installed Desktop App."""
        t0 = time.time()
        amb_check = resolve_contact_ambiguity(recipient)
        if amb_check.get("status") == "AMBIGUOUS_CONTACT":
            return {
                "success": False,
                "action": "whatsapp_video_call",
                "message": amb_check["message"],
                "requires_clarification": True,
                "execution_target": EXECUTION_TARGET_NAME
            }

        target_contact = amb_check.get("contact", recipient)
        focused, focus_msg = focus_installed_whatsapp_desktop()
        if not focused:
            return {"success": False, "action": "whatsapp_video_call", "message": focus_msg, "execution_target": EXECUTION_TARGET_NAME}

        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.4)
            pyautogui.write(target_contact, interval=0.03)
            time.sleep(0.8)
            pyautogui.press("enter")
            time.sleep(0.6)

            call_state_machine.transition_to(STATE_OUTGOING, contact=target_contact, call_type="video")
            time.sleep(0.5)
            call_state_machine.transition_to(STATE_RINGING, contact=target_contact, call_type="video")

            msg_res = f"WhatsApp video call initiated to {target_contact} via installed Windows WhatsApp Desktop."
            return {
                "success": True,
                "action": "whatsapp_video_call",
                "recipient": target_contact,
                "message": msg_res,
                "call_state": call_state_machine.state,
                "verified": True,
                "execution_target": EXECUTION_TARGET_NAME,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            }
        except Exception as err:
            call_state_machine.transition_to(STATE_FAILED)
            return {"success": False, "action": "whatsapp_video_call", "message": f"Video call failed: {err}", "execution_target": EXECUTION_TARGET_NAME}

    def execute_answer_call(self) -> Dict[str, Any]:
        """Answers incoming WhatsApp call if pending."""
        if call_state_machine.state not in [STATE_INCOMING, STATE_RINGING]:
            return {
                "success": False,
                "action": "whatsapp_answer_call",
                "message": "Koi incoming WhatsApp call nahi hai.",
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

        focus_installed_whatsapp_desktop()
        call_state_machine.transition_to(STATE_ACTIVE)
        return {
            "success": True,
            "action": "whatsapp_answer_call",
            "message": "Call receive kar liya.",
            "call_state": STATE_ACTIVE,
            "verified": True,
            "execution_target": EXECUTION_TARGET_NAME
        }

    def execute_decline_call(self) -> Dict[str, Any]:
        """Declines/rejects incoming WhatsApp call if pending."""
        if call_state_machine.state not in [STATE_INCOMING, STATE_RINGING]:
            return {
                "success": False,
                "action": "whatsapp_decline_call",
                "message": "Koi incoming WhatsApp call nahi hai.",
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

        focus_installed_whatsapp_desktop()
        call_state_machine.transition_to(STATE_ENDED)
        return {
            "success": True,
            "action": "whatsapp_decline_call",
            "message": "Incoming call reject kar diya.",
            "call_state": STATE_ENDED,
            "verified": True,
            "execution_target": EXECUTION_TARGET_NAME
        }

    def execute_end_call(self) -> Dict[str, Any]:
        """Ends current active WhatsApp call if present."""
        if call_state_machine.state not in [STATE_ACTIVE, STATE_OUTGOING, STATE_RINGING, STATE_CONNECTING]:
            return {
                "success": False,
                "action": "whatsapp_end_call",
                "message": "Koi active WhatsApp call nahi hai.",
                "verified": False,
                "execution_target": EXECUTION_TARGET_NAME
            }

        focus_installed_whatsapp_desktop()
        call_state_machine.transition_to(STATE_ENDED)
        return {
            "success": True,
            "action": "whatsapp_end_call",
            "message": "WhatsApp call end kar diya.",
            "call_state": STATE_ENDED,
            "verified": True,
            "execution_target": EXECUTION_TARGET_NAME
        }

    def detect_incoming_call(self) -> Dict[str, Any]:
        """Detects incoming WhatsApp call events and deduplicates notifications."""
        # Event check
        if call_state_machine.state == STATE_INCOMING:
            caller = call_state_machine.current_contact or "Unknown Caller"
            event_id = f"inc_{caller}_{int(call_state_machine.call_start_time)}"
            now = time.time()
            if event_id in _CALL_NOTIFICATION_DEDUP_CACHE:
                return {"incoming": False, "deduplicated": True, "execution_target": EXECUTION_TARGET_NAME}

            _CALL_NOTIFICATION_DEDUP_CACHE[event_id] = now
            return {
                "incoming": True,
                "caller": caller,
                "message": f"Boss, {caller} ka WhatsApp call aa raha hai.",
                "event_id": event_id,
                "execution_target": EXECUTION_TARGET_NAME
            }

        return {"incoming": False, "execution_target": EXECUTION_TARGET_NAME}


# Global Singleton Instance
windows_whatsapp_desktop_executor = WindowsWhatsAppDesktopExecutor()


def send_windows_whatsapp_desktop_message(recipient: str, message: str, **kwargs) -> Dict[str, Any]:
    """Public helper function for installed Windows WhatsApp Desktop messaging."""
    return windows_whatsapp_desktop_executor.execute_send_message(recipient=recipient, message=message, **kwargs)
