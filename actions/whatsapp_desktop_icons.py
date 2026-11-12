"""Locate the observed WhatsApp phone glyph; never reuse fixed click positions."""
from pathlib import Path
import re
import tempfile
import time


def find_voice_icon(state):
    import cv2
    import numpy as np
    template = cv2.imread(str(Path(__file__).resolve().parent.parent / "assets" / "whatsapp_voice_call.png"), cv2.IMREAD_GRAYSCALE)
    if template is None:
        return None
    frame = cv2.cvtColor(np.asarray(state.image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    region = frame[40:110, int(state.chat_left):]
    peaks = []
    for scale in (.8, 1.0, 1.25, 1.5):
        glyph = cv2.resize(template, None, fx=scale, fy=scale)
        if glyph.shape[0] >= region.shape[0] or glyph.shape[1] >= region.shape[1]:
            continue
        score = cv2.matchTemplate(region, glyph, cv2.TM_CCOEFF_NORMED)
        _, confidence, _, point = cv2.minMaxLoc(score)
        if confidence >= .90:
            masked = score.copy()
            x, y = point
            masked[max(0, y-glyph.shape[0]):y+glyph.shape[0], max(0, x-glyph.shape[1]):x+glyph.shape[1]] = -1
            if cv2.minMaxLoc(masked)[1] >= .90:
                return None
            center = (int(state.chat_left) + point[0] + glyph.shape[1] / 2, 40 + point[1] + glyph.shape[0] / 2)
            peaks.append((confidence, center))
    if not peaks:
        return None
    # Require a unique match, including separate occurrences at the same scale.
    confidence, center = max(peaks)
    for _, alternative in peaks:
        if abs(alternative[0] - center[0]) > 24 or abs(alternative[1] - center[1]) > 24:
            return None
    return {"x": center[0], "y": center[1], "confidence": confidence}


def _owned_window(hwnd):
    import psutil
    import win32process
    process = psutil.Process(win32process.GetWindowThreadProcessId(hwnd)[1])
    name = process.name().casefold()
    return name in ("whatsapp.root.exe", "whatsapp.exe") or name == "msedgewebview2.exe" and any(arg.casefold() == "--webview-exe-name=whatsapp.root.exe" for arg in process.cmdline())


def _call_text(hwnd):
    import win32gui
    from PIL import ImageGrab
    from actions.whatsapp_desktop_visual import recognize_image
    if win32gui.GetForegroundWindow() != hwnd or not _owned_window(hwnd):
        return []
    with tempfile.TemporaryDirectory(prefix="jarvis_call_ocr_") as directory:
        path = Path(directory) / "call.png"
        ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd)).save(path)
        return [line["text"].strip() for line in recognize_image(path)]


def color_call_button(image, color):
    """Require one solid, pill-shaped call control in the bottom toolbar."""
    import cv2
    import numpy as np
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 0] < 12) | (hsv[:, :, 0] > 170)) if color == "red" else ((hsv[:, :, 0] > 35) & (hsv[:, :, 0] < 90))
    mask = (mask & (hsv[:, :, 1] > 130) & (hsv[:, :, 2] > 110)).astype("uint8") * 255
    mask[:int(image.height * .7)] = 0
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    matches = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if 40 <= w <= 180 and 25 <= h <= 80 and 1.2 <= w/h <= 4 and cv2.contourArea(contour)/(w*h) > .65:
            matches.append((x+w/2, y+h/2))
    return matches[0] if len(matches) == 1 else None


def _capture_call(hwnd):
    import win32gui
    from PIL import ImageGrab
    from actions.whatsapp_desktop_visual import recognize_image
    if win32gui.GetForegroundWindow() != hwnd or not _owned_window(hwnd):
        return None
    rect = win32gui.GetWindowRect(hwnd)
    image = ImageGrab.grab(bbox=rect)
    with tempfile.TemporaryDirectory(prefix="jarvis_call_control_") as directory:
        path = Path(directory)/"call.png"
        image.save(path)
        texts = [line["text"].strip() for line in recognize_image(path)]
    if any("search or start a new chat" in text.casefold() for text in texts):
        return None  # The ordinary chat window is not a call-control dialog.
    incoming = any(re.search(r"\b(incoming (?:voice |video )?call|is calling)\b", text, re.I) for text in texts)
    timer = any(re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text) for text in texts)
    pending = any(text.casefold() in ("calling...", "calling…", "ringing...", "ringing…") for text in texts)
    return {"hwnd": hwnd, "rect": rect, "incoming": incoming, "active": timer or pending,
            "red": color_call_button(image, "red"), "green": color_call_button(image, "green")}


def execute_call_control(action):
    from actions.whatsapp_desktop_dom import failed
    import win32gui
    import pyautogui
    from actions.windows_whatsapp_desktop_executor import win32_activate_hwnd
    windows = []
    def collect(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd) and _owned_window(hwnd):
                windows.append(hwnd)
        except Exception:
            pass
    win32gui.EnumWindows(collect, None)
    selected = None
    for hwnd in windows[:4]:
        if not win32_activate_hwnd(hwnd):
            continue
        snapshot = _capture_call(hwnd)
        if snapshot and snapshot["red"] and (snapshot["active"] or snapshot["incoming"]):
            selected = snapshot
            break
    if not selected:
        return failed("Native call ki active/incoming window verify nahi hui.", "ICON_CONTROL_UNAVAILABLE")
    if action in ("answer", "decline") and not selected["incoming"]:
        return failed("Incoming call verify nahi hui; control click nahi kiya.", "NO_INCOMING_CALL")
    point = selected["green"] if action == "answer" else selected["red"]
    if not point or win32gui.GetForegroundWindow() != selected["hwnd"] or win32gui.GetWindowRect(selected["hwnd"]) != selected["rect"]:
        return failed("Call control/window badal gaya; click nahi kiya.", "CALL_CONTROL_UNAVAILABLE")
    pyautogui.click(selected["rect"][0]+point[0], selected["rect"][1]+point[1])
    time.sleep(.5)
    if not win32gui.IsWindow(selected["hwnd"]) and action in ("end_call", "decline"):
        return {"success": True, "verified": True, "status": "CALL_ENDED", "message": "WhatsApp call window band ho gayi."}
    after = _capture_call(selected["hwnd"])
    if after and action == "answer" and after["active"] and not after["incoming"]:
        return {"success": True, "verified": True, "status": "CALL_UI_ACTIVE", "message": "Incoming call ka active state verify hua."}
    if after and action in ("end_call", "decline") and not after["red"] and not after["incoming"] and not after["active"]:
        return {"success": True, "verified": True, "status": "CALL_ENDED", "message": "Call ke active controls band ho gaye."}
    return failed("Call control click hua, state verify nahi hui; dobara attempt nahi kiya.", "CALL_UNVERIFIED")


def execute_icon_call(action, recipient=""):
    from actions.whatsapp_desktop_dom import failed
    if action in ("answer", "decline", "end_call"):
        try:
            return execute_call_control(action)
        except Exception as exc:
            return failed(f"Native call state unavailable: {type(exc).__name__}", "CALL_UNVERIFIED")
    if action != "voice_call":
        return failed("Observed native icon is only for voice calls.", "ICON_CONTROL_UNAVAILABLE")
    attempted = False
    try:
        import win32gui
        import pyautogui
        from actions.whatsapp_desktop_visual import execute_visual, WhatsAppObservation, normalize
        from actions.windows_whatsapp_desktop_executor import win32_find_whatsapp_hwnd
        selected = execute_visual("open_chat", recipient)
        if not selected.get("success") or not selected.get("verified"):
            return selected
        hwnd = win32_find_whatsapp_hwnd()
        state = WhatsAppObservation(hwnd)
        icon = find_voice_icon(state)
        if not icon:
            return failed("Exact unique phone icon verify nahi hua.", "ICON_CONTROL_UNAVAILABLE")
        if not state.chat_header_matches(recipient) or win32gui.GetForegroundWindow() != hwnd or win32gui.GetWindowRect(hwnd) != state.rect:
            return failed("WhatsApp recipient/window badal gaya; call nahi ki.", "RECIPIENT_UNVERIFIED")
        attempted = True
        pyautogui.click(state.rect[0] + icon["x"], state.rect[1] + icon["y"])
        time.sleep(.5)
        # A call popup can appear after the first frame. Poll observations only;
        # never click again or interpret ordinary chat timestamps as call timers.
        deadline = time.monotonic() + 5
        for _ in range(4):
            popup = win32gui.GetForegroundWindow()
            texts = _call_text(popup)
            caller_verified = any(normalize(text) == normalize(recipient) for text in texts)
            pending = any(normalize(text) in ("calling...", "calling…", "ringing...", "ringing…") for text in texts)
            counter = any(re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text) for text in texts)
            if caller_verified and popup != hwnd and (pending or counter):
                return {"success": True, "verified": True, "status": "CALL_UI_ACTIVE", "message": f"{recipient} ki WhatsApp call window verify hui. Peer connection {'confirm nahi hai' if pending else 'duration counter dikh raha hai'}.", "verification_method": "observed icon and offline call OCR"}
            if time.monotonic() >= deadline:
                break
            time.sleep(.25)
        return failed("Call icon click hua, lekin call state verify nahi hui. Dobara automatically call nahi ki.", "CALL_UNVERIFIED")
    except Exception as exc:
        return failed(f"Native call control: {type(exc).__name__}", "CALL_UNVERIFIED" if attempted else "ICON_CONTROL_UNAVAILABLE")
