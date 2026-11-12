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
_SENT_MESSAGES_DEDUP_CACHE: Dict[str, Dict[str, Any]] = {}  # hash -> attempt/result
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


def _type_text_safe(text: str) -> None:
    """Types text using clipboard for reliable Unicode/Hinglish/emoji support.
    Falls back to pyautogui.write() for pure ASCII."""
    import pyautogui
    try:
        # Check if text is pure ASCII
        text.encode("ascii")
        pyautogui.write(text, interval=0.001)
    except UnicodeEncodeError:
        # Non-ASCII: use clipboard paste strategy
        try:
            import pyperclip
            old_clip = ""
            try:
                old_clip = pyperclip.paste()
            except Exception:
                pass
            pyperclip.copy(text)
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)
            # Restore old clipboard if possible
            try:
                pyperclip.copy(old_clip)
            except Exception:
                pass
        except ImportError:
            # No pyperclip: fallback to ctypes clipboard
            try:
                import ctypes
                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                user32.OpenClipboard(0)
                user32.EmptyClipboard()
                h_mem = kernel32.GlobalAlloc(0x0042, (len(text) + 1) * 2)
                p_mem = kernel32.GlobalLock(h_mem)
                ctypes.cdll.msvcrt.wcscpy(ctypes.c_wchar_p(p_mem), text)
                kernel32.GlobalUnlock(h_mem)
                user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                time.sleep(0.05)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.05)
            except Exception:
                # Last resort: just try write
                pyautogui.write(text, interval=0.005)


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
    """Prefer the actual installed app root, not its covered WebView window."""
    import win32gui
    import win32process
    import psutil
    matches = []
    def collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).lower()
        if "whatsapp" not in title:
            return
        try:
            process = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1])
            if process.name().lower() in ("whatsapp.root.exe", "whatsapp.exe"):
                matches.append(hwnd)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
    win32gui.EnumWindows(collect, None)
    active = win32gui.GetForegroundWindow()
    if active in matches:
        return active
    return matches[0] if len(matches) == 1 else None


def win32_activate_hwnd(hwnd: int) -> bool:
    """Activates and brings HWND to foreground directly using User32 (1-5 ms)."""
    try:
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(.05)
        if user32.GetForegroundWindow() != hwnd:
            # A user-requested foreground switch can be gated by Windows until
            # keyboard input is seen. Verify the switch rather than assuming it.
            import pyautogui
            pyautogui.press("alt")
            user32.SetForegroundWindow(hwnd)
            time.sleep(.1)
        return user32.GetForegroundWindow() == hwnd
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
    After launching, VERIFIES actual window/process presence before returning success.
    """
    if not _WHATSAPP_USER_ACTION_REQUESTED:
        logger.warning("[WindowsWhatsAppDesktop] REJECTED launch_whatsapp: _WHATSAPP_USER_ACTION_REQUESTED is False.")
        return False, "Launch rejected: WhatsApp Desktop cannot be opened automatically without an explicit user command."

    installed, running, _ = is_whatsapp_installed_or_running()
    if not installed:
        logger.warning("[WindowsWhatsAppDesktop] WhatsApp Desktop is not installed.")
        return False, "WhatsApp Desktop is not installed on this system."

    # If already running, just focus it
    if running:
        ok, msg = focus_running_whatsapp()
        if ok:
            return True, msg

    # Strategy 1: explorer.exe shell:AppsFolder with confirmed AUMID
    _WHATSAPP_AUMIDS = [
        "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
        "5319275A.WhatsAppDesktop_531f527m5524g!App",
    ]
    for aumid in _WHATSAPP_AUMIDS:
        try:
            subprocess.run(
                f'explorer.exe shell:AppsFolder\\{aumid}',
                shell=True, capture_output=True, timeout=3.0
            )
            logger.info(f"[WindowsWhatsAppDesktop] Launch attempt via AUMID: {aumid}")
            # Wait and verify
            if _wait_for_whatsapp_window(timeout=5.0):
                return True, "Launched installed WhatsApp Desktop application."
        except Exception as e:
            logger.debug(f"[WindowsWhatsAppDesktop] AUMID launch failed ({aumid}): {e}")

    # Strategy 2: whatsapp: protocol
    try:
        os.startfile("whatsapp:")
        logger.info("[WindowsWhatsAppDesktop] Launch attempt via whatsapp: protocol")
        if _wait_for_whatsapp_window(timeout=5.0):
            return True, "Launched WhatsApp Desktop via protocol."
    except Exception as e:
        logger.debug(f"[WindowsWhatsAppDesktop] Protocol launch failed: {e}")

    # Strategy 3: PowerShell Start-Process
    try:
        subprocess.run(
            ['powershell', '-Command', 'Start-Process', f'shell:AppsFolder\\{_WHATSAPP_AUMIDS[0]}'],
            capture_output=True, timeout=5.0
        )
        if _wait_for_whatsapp_window(timeout=5.0):
            return True, "Launched WhatsApp Desktop via PowerShell."
    except Exception as e:
        logger.debug(f"[WindowsWhatsAppDesktop] PowerShell launch failed: {e}")

    return False, "WhatsApp Desktop launch attempted but window/process could not be verified."


def _wait_for_whatsapp_window(timeout: float = 5.0) -> bool:
    """Wait for WhatsApp window/process to appear after launch."""
    start = time.time()
    while time.time() - start < timeout:
        hwnd = win32_find_whatsapp_hwnd()
        if hwnd:
            global _CACHED_HWND
            _CACHED_HWND = hwnd
            return True
        # Also check process
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                pname = (proc.info.get('name') or '').lower()
                if 'whatsapp' in pname and 'chrome' not in pname and 'edge' not in pname:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


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


def _load_contact_config() -> Dict[str, Any]:
    """Loads contact configuration from config/important_contacts.json."""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "important_contacts.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"[WindowsWhatsAppDesktop] Contact config load failed: {e}")
    return {}


def resolve_contact_ambiguity(recipient_query: str) -> Dict[str, Any]:
    """
    Resolves contact from config/important_contacts.json with alias support.
    Returns status: RESOLVED, AMBIGUOUS_CONTACT, EMPTY, or NOT_FOUND.
    """
    if not recipient_query or not recipient_query.strip():
        return {"status": "EMPTY", "matches": []}

    q = recipient_query.strip().lower()
    # Strip conversational prefixes
    q = re.sub(r"^(?:ab|bhai|jarvis|please|zara|aur|fir|phir)\s+", "", q, flags=re.IGNORECASE).strip()
    config = _load_contact_config()
    contact_aliases = config.get("contact_aliases", {})
    important_contacts = config.get("important_contacts", [])

    from actions.contact_directory import resolve_saved_contact
    saved = resolve_saved_contact(recipient_query)
    if saved and saved.get('status') == 'AMBIGUOUS_CONTACT':
        return saved

    # 1. Check alias-based resolution
    alias_matches = []
    for canonical_name, info in contact_aliases.items():
        aliases = [a.lower() for a in info.get("aliases", [])]
        display = info.get("display_name", canonical_name)
        if q in aliases or q == canonical_name.lower() or q == display.lower():
            alias_matches.append({"name": display, "canonical": canonical_name})

    if len(alias_matches) == 1:
        directory_match = resolve_saved_contact(alias_matches[0]['name'])
        if directory_match and directory_match.get('status') == 'AMBIGUOUS_CONTACT':
            return directory_match
        return {"status": "RESOLVED", "contact": alias_matches[0]["name"]}
    if len(alias_matches) > 1:
        names = [m["name"] for m in alias_matches]
        return {
            "status": "AMBIGUOUS_CONTACT",
            "message": f"Kaunse {recipient_query.title()} ko WhatsApp message/call karna hai? ({', '.join(names)})",
            "matches": names,
            "requires_clarification": True
        }

    if saved:
        return saved

    # 2. Check important_contacts list (direct name match)
    ic_matches = [c for c in important_contacts if q in c.lower() or c.lower() in q]
    if len(ic_matches) == 1:
        return {"status": "RESOLVED", "contact": ic_matches[0]}
    if len(ic_matches) > 1:
        return {
            "status": "AMBIGUOUS_CONTACT",
            "message": f"Kaunse {recipient_query.title()} ko WhatsApp message/call karna hai? ({', '.join(ic_matches)})",
            "matches": ic_matches,
            "requires_clarification": True
        }

    # 3. Not found in config — pass through as-is (user may have typed exact WhatsApp display name)
    return {"status": "RESOLVED", "contact": recipient_query.strip()}


class WindowsWhatsAppDesktopExecutor:
    """
    Authoritative Installed Windows WhatsApp Desktop Application Executor.
    Strictly enforces execution_target == "WINDOWS_INSTALLED_WHATSAPP_DESKTOP".
    """

    def focus_installed_whatsapp_desktop(self) -> Tuple[bool, str]:
        """Direct entry point for focusing or launching installed WhatsApp Desktop."""
        return focus_installed_whatsapp_desktop()

    def execute_send_message(self, recipient, message, command_id=None, correlation_id=None, force_send=True):
        from actions.whatsapp_desktop_dom import desktop_action
        resolved = resolve_contact_ambiguity(recipient)
        if resolved.get("status") == "AMBIGUOUS_CONTACT":
            return {**resolved, "success": False, "verified": False, "execution_target": EXECUTION_TARGET_NAME}
        target = resolved.get("contact", recipient)
        key = _compute_message_hash(target, message)
        previous = _SENT_MESSAGES_DEDUP_CACHE.get(key)
        if previous and time.time() - previous["time"] < 60:
            return {**previous["result"], "duplicate_prevented": True}
        result = desktop_action("send", target, message)
        result.update(action="whatsapp_send", recipient=target, command_id=command_id, correlation_id=correlation_id)
        if result.get("success") or result.get("status") in ("SEND_UNVERIFIED", "SEND_ERROR"):
            _SENT_MESSAGES_DEDUP_CACHE[key] = {"time": time.time(), "result": dict(result)}
        return result

    def execute_voice_call(self, recipient):
        return self._call("voice_call", recipient)

    def execute_video_call(self, recipient):
        return self._call("video_call", recipient)

    def _call(self, action, recipient):
        from actions.whatsapp_desktop_dom import desktop_action
        resolved = resolve_contact_ambiguity(recipient)
        if resolved.get("status") == "AMBIGUOUS_CONTACT":
            return {**resolved, "success": False, "verified": False, "execution_target": EXECUTION_TARGET_NAME}
        target = resolved.get("contact", recipient)
        result = desktop_action(action, target)
        if result.get("success") and result.get("verified"):
            call_state_machine.transition_to(STATE_OUTGOING, target, "video" if action == "video_call" else "voice")
        return result

    def execute_answer_call(self):
        from actions.whatsapp_desktop_dom import desktop_action
        result = desktop_action("answer")
        if result.get("success") and result.get("verified"):
            call_state_machine.transition_to(STATE_ACTIVE)
        return result

    def execute_decline_call(self):
        from actions.whatsapp_desktop_dom import desktop_action
        result = desktop_action("decline")
        if result.get("success") and result.get("verified"):
            call_state_machine.transition_to(STATE_ENDED)
        return result

    def execute_end_call(self):
        from actions.whatsapp_desktop_dom import desktop_action
        result = desktop_action("end_call")
        if result.get("success") and result.get("verified"):
            call_state_machine.transition_to(STATE_ENDED)
        return result

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
