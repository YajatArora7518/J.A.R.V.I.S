"""Named native WhatsApp call controls using the installed UIA backend.

Never uses guessed coordinates, keyboard shortcuts, browser tabs or other apps.
An attempted action is never retried through a second backend.
"""
import re
import time
import threading

_inventory_lock = threading.Lock()
_inventory_thread = None

CALL_ACTIONS = ("voice_call", "video_call", "answer", "decline", "end_call")
LABELS = {
    "voice_call": ("Voice call", "Audio call", "Start voice call"),
    "video_call": ("Video call", "Start video call"),
    "answer": ("Accept", "Answer", "Accept call", "Answer call"),
    "decline": ("Decline", "Reject", "Decline call", "Reject call"),
    "end_call": ("End call", "Hang up"),
}


def _name(control):
    return re.sub(r"\s*\((?:Ctrl|Control|Alt|Shift)[^)]*\)\s*$", "", control.window_text(), flags=re.I).strip().casefold()


def _collect_inventory():
    from pywinauto import Desktop
    import psutil
    windows = []
    for window in Desktop(backend="uia").windows():
        try:
            process = psutil.Process(window.element_info.process_id)
            name = process.name().casefold()
            owned = name in ("whatsapp.exe", "whatsapp.root.exe")
            if name == "msedgewebview2.exe":
                owned = any(arg.casefold() == "--webview-exe-name=whatsapp.root.exe" for arg in process.cmdline())
            if owned and window.is_visible():
                buttons = [button for button in window.descendants(control_type="Button") if button.is_visible() and button.is_enabled()]
                windows.append({"window": window, "buttons": buttons})
        except (psutil.Error, RuntimeError):
            continue
    return windows


def _inventory():
    """Bound read-only UIA scanning; a stalled provider must never delay input.

    Only one scan may remain in flight. The worker performs no actions, so a
    timeout cannot trigger a delayed call or duplicate backend attempt.
    """
    global _inventory_thread
    result = []
    def collect():
        import pythoncom
        pythoncom.CoInitialize()
        try:
            result.extend(_collect_inventory())
        except Exception:
            pass  # The observed native backend may still be available.
        finally:
            pythoncom.CoUninitialize()
    with _inventory_lock:
        if _inventory_thread and _inventory_thread.is_alive():
            return []
        worker = threading.Thread(target=collect, daemon=True, name='WhatsAppUIAScan')
        _inventory_thread = worker
        worker.start()
    worker.join(timeout=2)
    return [] if worker.is_alive() else result


def _buttons(windows, action):
    names = {name.casefold() for name in LABELS[action]}
    return [(entry, button) for entry in windows for button in entry["buttons"] if _name(button) in names]


def execute_accessible_call(action, recipient=""):
    from actions.whatsapp_desktop_dom import failed
    if action not in CALL_ACTIONS:
        return failed("Unsupported native call action.", "UNSUPPORTED")
    attempted = False
    try:
        windows = _inventory()
        if not windows:
            return failed("Native WhatsApp accessibility unavailable.", "ACCESSIBILITY_CONTROL_UNAVAILABLE")
        if action in ("voice_call", "video_call"):
            if not recipient.strip():
                return failed("Exact WhatsApp contact name do.", "RECIPIENT_REQUIRED")
            from actions.whatsapp_desktop_visual import execute_visual
            selected = execute_visual("open_chat", recipient)
            if not selected.get("success") or not selected.get("verified"):
                return selected
        windows = _inventory()
        if action in ("voice_call", "video_call") and _buttons(windows, "end_call"):
            return failed("WhatsApp call pehle se active hai; doosri call nahi ki.", "CALL_ALREADY_ACTIVE")
        controls = _buttons(windows, action)
        if len(controls) != 1:
            return failed("Exact unique native WhatsApp call control nahi mila.", "ACCESSIBILITY_CONTROL_UNAVAILABLE")
        entry, button = controls[0]
        if action in ("voice_call", "video_call"):
            # Recheck the selected conversation immediately before invoking.
            from actions.windows_whatsapp_desktop_executor import win32_find_whatsapp_hwnd
            from actions.whatsapp_desktop_visual import WhatsAppObservation
            if not WhatsAppObservation(win32_find_whatsapp_hwnd()).chat_header_matches(recipient):
                return failed("Call recipient badal gaya; call nahi ki.", "RECIPIENT_UNVERIFIED")
        attempted = True
        button.invoke()
        for _ in range(12):
            state = _inventory()
            ends = _buttons(state, "end_call")
            if action in ("end_call", "decline"):
                if state and not ends and not _buttons(state, "answer"):
                    return {"success": True, "verified": True, "status": "CALL_ENDED", "message": "WhatsApp call controls band ho gaye."}
            elif len(ends) == 1 and (action != "answer" or not _buttons(state, "answer")):
                return {"success": True, "verified": True, "status": "CALL_UI_ACTIVE", "message": "WhatsApp call controls active hain. Peer connection abhi confirm nahi hai."}
            time.sleep(.25)
        return failed("Native call control invoke hua, lekin state verify nahi hui; dobara automatically attempt nahi kiya.", "CALL_UNVERIFIED")
    except Exception as exc:
        return failed(f"Native WhatsApp call control unavailable: {type(exc).__name__}", "CALL_UNVERIFIED" if attempted else "ACCESSIBILITY_CONTROL_UNAVAILABLE")
