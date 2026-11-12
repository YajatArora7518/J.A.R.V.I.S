"""Offline, observed text controls for Store WhatsApp without a debug port."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from actions.whatsapp_desktop_dom import failed


def recognize_image(path):
    script = Path(__file__).resolve().parent.parent / "scripts" / "windows_ocr.ps1"
    result = subprocess.run(["powershell", "-NoProfile", "-File", str(script), "-ImagePath", str(Path(path).resolve())],
        capture_output=True, encoding="utf-8", timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Windows offline text recognition unavailable.")
    return json.loads(result.stdout)["lines"]


def normalize(text):
    return re.sub(r"\s+", " ", text.strip()).casefold()


def exact_lines(lines, text):
    return [line for line in lines if normalize(line["text"]) == normalize(text)]


class WhatsAppObservation:
    def __init__(self, hwnd):
        from PIL import ImageGrab
        import win32gui
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError("WhatsApp lost foreground; action stopped.")
        self.hwnd = hwnd
        self.rect = win32gui.GetWindowRect(hwnd)
        self.width = self.rect[2] - self.rect[0]
        self.height = self.rect[3] - self.rect[1]
        if self.width < 700 or self.height < 450:
            raise RuntimeError("WhatsApp window ko bada karo; controls verify nahi ho rahe.")
        with tempfile.TemporaryDirectory(prefix="jarvis_ocr_") as directory:
            path = Path(directory) / "window.png"
            from PIL import Image
            image = ImageGrab.grab(bbox=self.rect)
            self.image = image
            scale = min(2.0, 2400 / max(image.size))
            enlarged = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
            # Give small bold recipient names a separate larger OCR view in the
            # same recognition call. Never resolve a person using fuzzy OCR.
            header_left = min(round(image.width * .25), 450)
            header_scale = 4
            header = image.crop((header_left, 35, min(header_left + 500, image.width), 110))
            header = header.resize((header.width * header_scale, header.height * header_scale), Image.Resampling.LANCZOS)
            combined = Image.new("RGB", (max(enlarged.width, header.width), enlarged.height + header.height), "black")
            combined.paste(enlarged, (0, 0))
            combined.paste(header, (0, enlarged.height))
            combined.save(path)
            self.lines = recognize_image(path)
            kept = []
            for line in self.lines:
                header_view = line["words"][0]["y"] >= enlarged.height
                for word in line["words"]:
                    if header_view:
                        word["x"] = word["x"] / header_scale + header_left
                        word["y"] = (word["y"] - enlarged.height) / header_scale + 35
                        word["width"] /= header_scale
                        word["height"] /= header_scale
                    else:
                        for field in ("x", "y", "width", "height"):
                            word[field] /= scale
                first = line["words"][0]
                if header_view or not (header_left <= first["x"] < header_left + 500 and 35 <= first["y"] < 110):
                    kept.append(line)
            self.lines = kept
        sidebar_heading = exact_lines(self.lines, "Chats")
        self.chat_left = (max(w["x"] + w["width"] for w in sidebar_heading[0]["words"]) + 280
                          if len(sidebar_heading) == 1 else self.width * .32)

    def click_line(self, line):
        import pyautogui
        import win32gui
        if win32gui.GetForegroundWindow() != self.hwnd or win32gui.GetWindowRect(self.hwnd) != self.rect:
            raise RuntimeError("WhatsApp focus/layout changed; action stopped.")
        words = line["words"]
        left = min(w["x"] for w in words)
        right = max(w["x"] + w["width"] for w in words)
        top = min(w["y"] for w in words)
        bottom = max(w["y"] + w["height"] for w in words)
        pyautogui.click(self.rect[0] + (left + right) / 2, self.rect[1] + (top + bottom) / 2)

    def chat_header_matches(self, recipient):
        return len([line for line in exact_lines(self.lines, recipient)
                    if line["words"][0]["x"] > self.chat_left and line["words"][0]["y"] < 110]) == 1

    def search_control(self):
        """Locate either a placeholder or an already populated search field."""
        sidebar = [line for line in self.lines if line['words'][0]['x'] < self.chat_left]
        placeholder = [line for line in sidebar
                       if normalize(line['text']).endswith('search or start a new chat')
                       and line['words'][0]['y'] < 180]
        if len(placeholder) == 1:
            return placeholder[0]
        headings = [line for line in exact_lines(sidebar, 'Chats')
                    if line['words'][0]['y'] < 120]
        filters = [line for line in sidebar if re.match(
            r'^(?:all|unread(?:\s+\d+)?|favourites|favorites|groups)(?:\s|$)', normalize(line['text']))
                   and line['words'][0]['y'] < 220]
        if len(headings) != 1 or not filters:
            return None
        lower = max(word['y'] + word['height'] for word in headings[0]['words']) + 10
        upper = min(line['words'][0]['y'] for line in filters) - 10
        heading_x = headings[0]['words'][0]['x']
        values = [line for line in sidebar if lower < line['words'][0]['y'] < upper
                  and line['words'][0]['x'] >= heading_x
                  and not (normalize(line['text']) in ('x', '×', '✕')
                           and line['words'][0]['x'] > heading_x + 200
                           and len(line['words']) == 1 and line['words'][0]['width'] < 25)]
        return values[0] if len(values) == 1 else None

    def composer_placeholder(self):
        matches = [line for line in self.lines if re.fullmatch(r"[tI|]?Type a message", line["text"], re.I)
                   if line["words"][0]["x"] > self.chat_left and line["words"][0]["y"] > self.height - 90]
        # A blinking caret can be recognized as an extra 't'. Distinguish grey
        # placeholder text from a real, brighter draft before permitting typing.
        if matches:
            import numpy as np
            words = matches[0]["words"][1:]
            if not words:
                return None
            crop = self.image.crop((min(w["x"] for w in words), min(w["y"] for w in words),
                max(w["x"] + w["width"] for w in words), max(w["y"] + w["height"] for w in words)))
            pixels = np.asarray(crop.convert("L"))
            text_pixels = pixels[pixels > 110]
            if not len(text_pixels) or float(np.median(text_pixels)) > 195:
                return None
        return matches[0] if len(matches) == 1 else None

    def messages(self):
        return [line for line in self.lines if line["words"][0]["x"] > self.chat_left
                and 115 < line["words"][0]["y"] < self.height - 90]

    def matching_outgoing(self, message):
        return [line for line in self.messages() if line["words"][0]["x"] > self.width * .55
                and normalize(re.sub(r"\s+\d{1,2}:\d{2}\s*(?:am|pm)?\s*[^\w]*$", "", line["text"], flags=re.I)) == normalize(message)]


def _paste(text, hwnd):
    import pyautogui
    import pyperclip
    import win32gui
    if win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError("WhatsApp lost focus before typing.")
    previous = pyperclip.paste()
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(.15)
    finally:
        pyperclip.copy(previous)


def execute_visual(action, recipient="", message="", limit=5):
    # The Qt process and its worker may use different Windows DPI contexts.
    # OCR pixel coordinates and cursor coordinates must use the same space.
    import ctypes
    from ctypes import wintypes
    setter = ctypes.windll.user32.SetThreadDpiAwarenessContext
    setter.argtypes = [wintypes.HANDLE]
    setter.restype = wintypes.HANDLE
    previous = setter(wintypes.HANDLE(-4))  # Per-monitor aware V2, this thread only.
    try:
        return _execute_visual(action, recipient, message, limit)
    finally:
        if previous:
            setter(previous)


def _focused_text_matches(text, hwnd):
    """Verify the focused editable text exactly; OCR can misread its caret."""
    import uuid
    import pyautogui
    import pyperclip
    import win32gui
    if win32gui.GetForegroundWindow() != hwnd:
        return False
    previous = pyperclip.paste()
    sentinel = 'jarvis-search-' + uuid.uuid4().hex
    try:
        pyperclip.copy(sentinel)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(.15)
        return (win32gui.GetForegroundWindow() == hwnd
                and pyperclip.paste() == text)
    finally:
        pyperclip.copy(previous)


def _search_query_matches(recipient, hwnd):
    return _focused_text_matches(recipient, hwnd)


def _execute_visual(action, recipient="", message="", limit=5):
    from actions.windows_whatsapp_desktop_executor import focus_installed_whatsapp_desktop, win32_find_whatsapp_hwnd
    import pyautogui
    import win32gui
    focused, reason = focus_installed_whatsapp_desktop()
    if not focused:
        return failed(reason, "DESKTOP_UNAVAILABLE")
    hwnd = win32_find_whatsapp_hwnd()
    attempted = False
    try:
        state = WhatsAppObservation(hwnd)
        if action in ("send", "voice_call", "video_call", "open_chat") and not recipient.strip():
            return failed("Exact WhatsApp contact name do.", "RECIPIENT_REQUIRED")
        if recipient and not state.chat_header_matches(recipient):
            # The observed search label gives the click location, never Tab order.
            search = state.search_control()
            if search is None:
                return failed("WhatsApp search control visible nahi hai.", "SEARCH_UNAVAILABLE")
            state.click_line(search)
            pyautogui.hotkey("ctrl", "a")
            _paste(recipient, hwnd)
            if not _search_query_matches(recipient, hwnd):
                return failed('Contact search field mein text verify nahi hua; message/call nahi kiya.', 'SEARCH_INPUT_UNVERIFIED')
            time.sleep(.5)
            state = WhatsAppObservation(hwnd)
            contacts = []
            for line in state.lines:
                # OCR can place a timestamp on the same line as a contact.
                name = re.sub(r"\s+(?:\d{1,2}:\d{2}\s*(?:am|pm)?|yesterday|today)$", "", line["text"], flags=re.I)
                if normalize(name) == normalize(recipient) and line["words"][0]["x"] < state.chat_left and line["words"][0]["y"] > 180:
                    contacts.append(line)
            if len(contacts) != 1:
                return failed("Exact unique WhatsApp contact verify nahi hua; message/call nahi kiya.", "RECIPIENT_NOT_RESOLVED")
            state.click_line(contacts[0])
            time.sleep(.35)
            for attempt in range(2):
                state = WhatsAppObservation(hwnd)
                if state.chat_header_matches(recipient):
                    break
                if attempt == 0:
                    time.sleep(.35)
            else:
                return failed("WhatsApp selected recipient verify nahi hua.", "RECIPIENT_UNVERIFIED")
        if action == "open_chat":
            return {"success": True, "verified": True, "message": f"{recipient} ki WhatsApp chat khol di."}
        if action == "read":
            messages = [line["text"] for line in state.messages()][-max(1, min(int(limit), 20)):]
            if not messages:
                return failed("Current chat mein readable text nahi mila.", "NO_VISIBLE_MESSAGES")
            return {"success": True, "verified": True, "status": "VISIBLE_TEXT_READ", "messages": messages, "message": "\n".join(messages), "reading_method": "Windows offline OCR"}
        if action == "send":
            if not message.strip():
                return failed("Message text do.", "MESSAGE_REQUIRED")
            composer = state.composer_placeholder()
            if not composer:
                return failed("Empty composer verify nahi hua; existing draft overwrite nahi kiya.", "COMPOSER_NOT_EMPTY")
            before = len(state.matching_outgoing(message))
            state.click_line(composer)
            _paste(message, hwnd)
            state = WhatsAppObservation(hwnd)
            # The already observed, focused composer can be copied exactly.
            # A blinking caret or OCR spacing must not reject the real draft.
            if not state.chat_header_matches(recipient) or not _focused_text_matches(message, hwnd):
                return failed("Draft/recipient verify nahi hua; Send press nahi kiya.", "DRAFT_UNVERIFIED")
            if win32gui.GetForegroundWindow() != hwnd:
                return failed("WhatsApp lost focus; send nahi kiya.")
            attempted = True
            pyautogui.press("enter")
            time.sleep(.4)
            state = WhatsAppObservation(hwnd)
            # An outgoing bubble plus emptied composer verifies submission only.
            outgoing = state.matching_outgoing(message)
            if len(outgoing) > before and state.composer_placeholder() and state.chat_header_matches(recipient):
                return {"success": True, "verified": True, "status": "SUBMITTED_UI_VERIFIED", "message": f"{recipient} ki WhatsApp chat mein message appear ho gaya. Delivery/read receipt confirm nahi hai.", "verification_method": "Windows offline OCR"}
            return failed("Send attempt hua, message verify nahi hua; automatically dobara nahi bheja.", "SEND_UNVERIFIED")
        # A named, observed call control is necessary; no guessed icon coordinates.
        labels = {"answer": ("Accept", "Answer", "Accept call"), "decline": ("Decline", "Reject", "Decline call"),
                  "end_call": ("End call", "Hang up"), "voice_call": ("Voice call", "Audio call"), "video_call": ("Video call",)}
        controls = [line for label in labels.get(action, ()) for line in exact_lines(state.lines, label)]
        if len(controls) != 1:
            return failed("WhatsApp call ka named control verify nahi hua. Is app version mein icon-only calls ke liye manual control chahiye.", "CALL_CONTROL_UNAVAILABLE")
        state.click_line(controls[0])
        return {"success": True, "verified": False, "status": "CALL_ACTION_REQUESTED", "message": "Call control activate hua; connection/answer state verify nahi hui."}
    except Exception as exc:
        return failed(f"WhatsApp action ruk gayi: {str(exc)[:120]}", "SEND_UNVERIFIED" if attempted else "DESKTOP_OBSERVATION_FAILED")
