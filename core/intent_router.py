# core/intent_router.py
# Centralized Web-First Intent Router & Priority Classifier for JARVIS

import re
from typing import Dict, Any, Tuple, Optional
from actions.web_registry import KNOWN_WEBSITES, resolve_website_url

# Communication / Social / Web Patterns
WHATSAPP_VIDEO_CALL_PATTERNS = [
    r"\bvideo call\b.*\bwhatsapp\b",
    r"\bwhatsapp\b.*\bvideo call\b",
    r"\b[a-zA-Z0-9_\s]+ ko whatsapp (pe|par)? video call\b",
    r"\bvideo call [a-zA-Z0-9_\s]+ on whatsapp\b"
]

WHATSAPP_CALL_PATTERNS = [
    r"\bwhatsapp\b.*\b(call|voice call)\b",
    r"\bcall\b.*\bwhatsapp\b",
    r"\b[a-zA-Z0-9_\s]+ ko whatsapp (call|voice call)\b",
    r"\bwhatsapp pe [a-zA-Z0-9_\s]+ ko call\b",
    r"\b[a-zA-Z0-9_\s]+ ko call (karo|kar do|khol)\b",
    r"\bcall [a-zA-Z0-9_\s]+\b"
]

WHATSAPP_OPEN_CHAT_PATTERNS = [
    r"\b(open|kholo|khol)\b.*\bwhatsapp chat\b",
    r"\b[a-zA-Z0-9_\s]+ ki whatsapp chat (kholo|khol|open karo)\b"
]

WHATSAPP_END_CALL_PATTERNS = [
    r"\b(call kaat do|call end karo|end call|hang up|call disconnect)\b"
]

WHATSAPP_REPLY_PATTERNS = [
    r"\b(reply karo|reply kar do|iska reply|message ka reply)\b",
    r"\b[a-zA-Z0-9_\s]+ ko reply (karo|bhej|bhejo)\b"
]

WHATSAPP_AUTOREPLY_PATTERNS = [
    r"\bauto reply\b", r"\bwhatsapp auto reply\b"
]

WHATSAPP_READ_PATTERNS = [
    r"\bwhatsapp\b.*\b(read|unread|last message|messages|padh)\b",
    r"\b(read|unread|last message)\b.*\bwhatsapp\b",
    r"\bunread whatsapp messages\b",
    r"\bwhatsapp check karo\b",
    r"\bread (my\s+)?(latest\s+)?whatsapp message\b",
    r"\b(message|messages|msg)\s+(padh|padho|padh ke)\b",
    r"\bpadh ke (suna|bata|suno)\b"
]

WHATSAPP_SEND_PATTERNS = [
    r"\bwhatsapp\b.*\b(send|bhej|bhejo|tell|saying|say)\b",
    r"\b(send|bhej|bhejo|tell|say)\b.*\bwhatsapp\b",
    r"\b[a-zA-Z0-9_\s]+ ko whatsapp (pe|par) message\b",
    r"\b[a-zA-Z0-9_\s]+ ko (message|msg) (karo|bhej|bhejo)\b",
    r"\bmessage [a-zA-Z0-9_\s]+ on whatsapp\b",
    r"\bwhatsapp\s+[a-zA-Z0-9_\s]+\s+(and\s+)?(say|tell)\b"
]

EXPLICIT_WHATSAPP_WEB_PATTERNS = [
    r"\bwhatsapp web\b", r"\bwa web\b", r"open whatsapp web", r"whatsapp web khol",
    r"whatsapp web kholo", r"open whatsapp in chrome"
]

EXPLICIT_TELEGRAM_WEB_PATTERNS = [
    r"\btelegram web\b", r"open telegram web", r"telegram web khol", r"telegram web kholo"
]

TELEGRAM_PATTERNS = [
    r"\btelegram\b", r"open telegram", r"telegram khol", r"telegram kholo", r"telegram open karo"
]

INSTAGRAM_POST_PATTERNS = [
    r"\binstagram\b.*\b(post|photo|caption|upload|story|reel)\b",
    r"\bphoto instagram (pe|par) post\b",
    r"\bye photo instagram\b"
]

COLLEGE_PATTERNS = [
    r"\bclass\b", r"\bschedule\b", r"\btimetable\b", r"\blecture\b",
    r"today meri class", r"aaj meri class", r"kal kiski class", r"next class",
    r"meri next class", r"aaj 10 baje", r"monday ka schedule", r"professor kaun hai",
    r"abhi meri class", r"college schedule"
]

WEB_SEARCH_TRIGGERS = [
    r"google\s+search", r"search\s+(the\s+)?web", r"search\s+(the\s+)?internet",
    r"search\s+online", r"look\s+it\s+up", r"look\s+this\s+up", r"check\s+online",
    r"search\s+news", r"search\s+for", r"google\s+for", r"google\s+this", r"google\s+it",
    r"internet\s+pe\s+search", r"google\s+karke\s+bata", r"search\s+karo",
    r"latest\s+news", r"current\s+price", r"latest\s+price", r"today'?s\s+weather",
    r"live\s+score", r"latest\s+update", r"official\s+website",
    r"^search\s+[a-zA-Z0-9_\-\s]+\s+for"
]

def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]

WHATSAPP_VIDEO_CALL_COMPILED = _compile(WHATSAPP_VIDEO_CALL_PATTERNS)
WHATSAPP_CALL_COMPILED = _compile(WHATSAPP_CALL_PATTERNS)
WHATSAPP_OPEN_CHAT_COMPILED = _compile(WHATSAPP_OPEN_CHAT_PATTERNS)
WHATSAPP_END_CALL_COMPILED = _compile(WHATSAPP_END_CALL_PATTERNS)
WHATSAPP_REPLY_COMPILED = _compile(WHATSAPP_REPLY_PATTERNS)
WHATSAPP_AUTOREPLY_COMPILED = _compile(WHATSAPP_AUTOREPLY_PATTERNS)
WHATSAPP_READ_COMPILED = _compile(WHATSAPP_READ_PATTERNS)
WHATSAPP_SEND_COMPILED = _compile(WHATSAPP_SEND_PATTERNS)
EXPLICIT_WHATSAPP_WEB_COMPILED = _compile(EXPLICIT_WHATSAPP_WEB_PATTERNS)
EXPLICIT_TELEGRAM_WEB_COMPILED = _compile(EXPLICIT_TELEGRAM_WEB_PATTERNS)
TELEGRAM_COMPILED = _compile(TELEGRAM_PATTERNS)
INSTAGRAM_POST_COMPILED = _compile(INSTAGRAM_POST_PATTERNS)
COLLEGE_COMPILED = _compile(COLLEGE_PATTERNS)
WEB_SEARCH_TRIGGERS_COMPILED = _compile(WEB_SEARCH_TRIGGERS)


def classify_intent(text: str) -> Dict[str, Any]:
    """
    Classifies user instruction according to App-First Priority Hierarchy:
    1. EXPLICIT_WEB_SEARCH (Explicit search commands)
    2. DIRECT_COMMUNICATION (WhatsApp Send / Call / Read / Reply)
    3. EXPLICIT_WEB_APP (Explicit WhatsApp Web / Telegram Web requests)
    4. WINDOWS_APPLICATION (App-First: Open WhatsApp / Chrome / Spotify / VS Code / Calculator / Notepad)
    5. KNOWN_WEBSITE (Domain URLs ending in .com / .org / .net)
    6. OTHER
    """
    raw_text = (text or "").strip()
    if not raw_text:
        return {"intent": "OTHER", "query": "", "target": ""}

    lower_text = raw_text.lower()

    # Normalize conversational addressing & wake-word prefixes (Boss / Sir / Jarvis)
    normalized_text = re.sub(r"^(boss|sir|jarvis|hey jarvis|hi jarvis|okay jarvis|ok jarvis)[,\s]+", "", lower_text, flags=re.IGNORECASE).strip()
    normalized_text = re.sub(r"[,\s]+(boss|sir|jarvis)$", "", normalized_text, flags=re.IGNORECASE).strip()
    if normalized_text:
        lower_text = normalized_text

    # 0. MICROPHONE SCOPED CONTROL INTENT CHECK
    mic_patterns = [
        "mic off", "mic on", "microphone off", "microphone on", "stop listening", "start listening",
        "jarvis mute", "jarvis unmute", "mic band", "mic bandh", "mic chalu", "turn my mic off", "turn mic off",
        "turn my mic on", "turn mic on", "turn off mic", "turn on mic", "mute my mic", "unmute my mic",
        "mute mic", "unmute mic", "jarvis mic", "jarvis microphone", "system mic", "windows mic", "laptop mic"
    ]
    if any(k in lower_text for k in mic_patterns):
        return {
            "intent": "MIC_CONTROL",
            "query": raw_text,
            "target": "mic",
            "tool": "mic_control"
        }

    # 0.1 SCREEN OBSERVATION & VISION ANALYSIS INTENTS ("Screen dekh", "Screen analyze karo", "What's on my screen?")
    screen_vision_patterns = [
        "screen dekh", "screen dekho", "screen dekhna", "screen analyze", "screen pe kya", "screen par kya",
        "screen check", "look at my screen", "look at the screen", "what's on my screen", "what is on my screen",
        "analyze my screen", "analyze screen", "can you see my screen", "ye screen pe kya", "screen par dekho",
        "dekh screen pe", "screen pe dekh", "screen dikhao", "read my screen", "screen reading", "screen observe",
        "webcam dekh", "camera dekh", "camera check", "look at camera", "what do you see in camera"
    ]
    if any(k in lower_text for k in screen_vision_patterns) or re.search(r"\b(screen|camera|webcam)\b.*\b(dekh|dekho|analyze|look|see|inspect|read|check)\b", lower_text) or re.search(r"\b(dekh|dekho|analyze|look at|inspect)\b.*\b(screen|camera|webcam)\b", lower_text):
        angle = "camera" if any(k in lower_text for k in ["camera", "webcam"]) else "screen"
        return {
            "intent": "SCREEN_ANALYSIS",
            "query": raw_text,
            "angle": angle,
            "target": "screen",
            "tool": "screen_process"
        }

    # 0.2 COMPUTATIONAL INTENT DETECTION ("Calculate 25 times 37", "What is 984 divided by 12?", "2^10", "sqrt(144)", "17% of 850", "125 + 378")
    math_patterns = [
        r"^\s*(?:calculate|compute|solve|evaluate)\b",
        r"\b(?:square\s+root\s+of|sqrt\s+of|sqrt\s*\()\b",
        r"\b\d+(?:\.\d+)?\s*(?:percent|%)\s+of\s+\d+",
        r"\b\d+(?:\.\d+)?\s*(?:\^|\*\*|raised\s+to|to\s+the\s+power\s+of)\s*\d+",
        r"\b\d+(?:\.\d+)?\s*(?:times|multiplied\s+by|into|divided\s+by|divided\s+with|plus|minus)\s+\d+",
        r"^\s*what(?:\'s|\s+is)\s+(?:the\s+)?(?:value\s+of\s+|result\s+of\s+)?\d+(?:\.\d+)?\s*[\+\-\*\/\^%]",
        r"^\s*what(?:\'s|\s+is)\s+(?:the\s+)?(?:square\s+root|sqrt|cube\s+root)\b",
        r"^\s*what(?:\'s|\s+is)\s+\d+(?:\.\d+)?\s*(?:percent|%)\s+of\b",
        r"^\s*what(?:\'s|\s+is)\s+\d+(?:\.\d+)?\s*(?:times|multiplied\s+by|into|divided\s+by|plus|minus)\b",
        r"^\s*\d+(?:\.\d+)?\s*[\+\-\*\/\^%]\s*\d+(?:\.\d+)?\s*$",
        r"^\s*sqrt\(\s*\d+(?:\.\d+)?\s*\)\s*$"
    ]
    if any(re.search(pat, lower_text) for pat in math_patterns):
        from core.safe_calculator import normalize_math_query
        expr = normalize_math_query(raw_text)
        return {
            "intent": "COMPUTATION",
            "query": raw_text,
            "expression": expr,
            "tool": "safe_calculator"
        }

    # 0.5 SYSTEM AWARENESS & HARDWARE TELEMETRY INTENT CHECKS (English + Hinglish)
    if any(k in lower_text for k in ["what cpu", "cpu kya", "cpu do i have", "processor kya", "cpu model", "cpu usage", "cpu info", "what is my cpu", "what's my cpu", "my cpu"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "cpu_info"}

    if any(k in lower_text for k in ["how much ram", "ram kitna", "ram free", "ram usage", "ram is free", "memory free", "ram do i have", "mera ram", "what is my ram", "what's my ram", "my ram"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "memory_info"}

    if any(k in lower_text for k in ["what gpu", "gpu kya", "gpu do i have", "graphics card"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "gpu_info"}

    if any(k in lower_text for k in ["battery percentage", "battery kitni", "charger connected", "charging", "battery percent", "battery info", "what is my battery", "what's my battery", "battery status", "how much battery", "my battery"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "battery_info"}

    if any(k in lower_text for k in ["disk space", "storage left", "drives do i have", "hard drive", "disk free", "storage space"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "disk_info"}

    if any(k in lower_text for k in ["network am i connected", "ip address", "ip status", "network status", "wifi status"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "network_info"}

    if any(k in lower_text for k in ["using my cpu", "using the most cpu", "using the most ram", "processes are using", "process cpu", "kaunsa process", "what's using my cpu", "what process"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "process_info"}

    if any(k in lower_text for k in ["apps are installed", "is discord installed", "is whatsapp installed", "where is vs code installed", "installed apps", "app installed"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "installed_apps_info"}

    if any(k in lower_text for k in ["windows are open", "open windows", "active windows", "what windows"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "active_windows_info"}

    if any(k in lower_text for k in ["microphone is active", "speakers are active", "active microphone", "active speaker", "sound devices"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "audio_devices_info"}

    if any(k in lower_text for k in ["files in downloads", "find my jarvis project", "find my python project", "open my documents", "find python files", "files modified today", "downloads folder", "downloads mein"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "filesystem_info"}

    if any(k in lower_text for k in ["what's happening on my laptop", "why is my laptop slow", "laptop slow", "system info", "system status", "computer info", "windows version", "pc ki ram", "disk mein kitni space"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "system_info"}

    # FILESYSTEM CREATION, READ, WRITE, RENAME, CLEAN INTENTS
    if any(k in lower_text for k in ["folder bana", "folder create", "directory create", "folder clean", "clean kar do", "file bana", "test.txt bana"]):
        return {"intent": "FILESYSTEM_CONTROL", "query": raw_text, "tool": "file_controller"}

    if any(k in lower_text for k in ["mein ... likho", "mein hello", "likho", "write to file", "append file", "padh ke batao", "file padho", "read file", "rename karo", "rename file"]):
        return {"intent": "FILESYSTEM_CONTROL", "query": raw_text, "tool": "file_controller"}

    # WINDOWS SERVICES INTENTS
    if any(k in lower_text for k in ["windows services", "service status", "services dikhao", "ye service running hai", "start service", "stop service", "restart service"]):
        return {"intent": "WINDOWS_SERVICE_CONTROL", "query": raw_text, "tool": "windows_service_control"}

    # SCRIPT CREATION & EXECUTION INTENTS
    if any(k in lower_text for k in ["script bana", "bat file bana", "python script bana", "powershell script bana", "is script ko run", "script execute", "run script"]):
        return {"intent": "SCRIPT_EXECUTION", "query": raw_text, "tool": "script_executor"}

    # STARTUP & PERSISTENCE INTENTS
    if any(k in lower_text for k in ["startup status", "startup mein enable", "startup se disable", "windows startup"]):
        return {"intent": "WINDOWS_STARTUP", "query": raw_text, "tool": "windows_startup"}

    # SCREENSHOT INTENTS
    if any(k in lower_text for k in ["screenshot le", "screenshot lo", "take screenshot", "capture screen", "screen shot"]):
        return {"intent": "SCREENSHOT", "query": raw_text, "tool": "computer_control"}

    # CLIPBOARD INTENTS
    if any(k in lower_text for k in ["clipboard padho", "clipboard mein kya", "copy to clipboard", "clipboard mein text"]):
        return {"intent": "CLIPBOARD", "query": raw_text, "tool": "windows_system_controller"}

    # NETWORK & INTERNET STATUS INTENTS
    if any(k in lower_text for k in ["wifi status", "internet status", "internet chal raha hai", "wifi active", "ip address"]):
        return {"intent": "SYSTEM_TELEMETRY", "query": raw_text, "tool": "network_info"}

    # WINDOW CONTROL INTENTS
    if any(k in lower_text for k in ["current window", "active window", "window minimize", "window maximize", "minimize karo", "maximize karo"]):
        return {"intent": "WINDOW_CONTROL", "query": raw_text, "tool": "windows_system_controller"}

    # 0.8 SAFE COMPUTER CONTROL / SETTINGS CHECKS
    if any(k in lower_text for k in ["brightness up", "brightness down", "brightness badhao", "brightness badha", "brightness kam", "brightness kam karo", "brightness increase", "brightness decrease"]):
        act = "brightness_up" if any(x in lower_text for x in ["up", "badha", "increase"]) else "brightness_down"
        return {"intent": "COMPUTER_SETTINGS", "query": raw_text, "action": act, "tool": "computer_settings"}

    if any(k in lower_text for k in ["volume up", "volume down", "volume badhao", "volume badha", "volume kam", "volume kam karo", "awaz badhao", "awaz badha", "awaz kam", "awaz kam karo", "volume increase", "volume decrease", "turn volume up", "turn volume down", "mute system", "unmute system", "open wifi settings", "open bluetooth settings", "open windows settings"]):
        act = "volume_up" if any(x in lower_text for x in ["up", "badha", "increase"]) else ("volume_down" if any(x in lower_text for x in ["down", "kam", "decrease"]) else ("mute" if "mute" in lower_text else "open_settings"))
        return {"intent": "COMPUTER_SETTINGS", "query": raw_text, "action": act, "tool": "computer_settings"}

    if any(k in lower_text for k in ["wifi on", "wifi off", "turn on wifi", "turn off wifi", "wifi chalu", "wifi band", "bluetooth on", "bluetooth off", "turn on bluetooth", "turn off bluetooth"]):
        act = "toggle_wifi" if "wifi" in lower_text else "open_settings"
        return {"intent": "COMPUTER_SETTINGS", "query": raw_text, "action": act, "tool": "computer_settings"}

    # TIMER & ALARM FAST-PATH INTENT CHECKS
    if any(k in lower_text for k in ["timer laga", "set timer", "timer set", "alarm laga", "set alarm", "alarm set"]):
        return {"intent": "REMINDER", "query": raw_text, "tool": "reminder"}

    # APPLICATION CLOSE FAST-PATH INTENT CHECK ("Chrome band karo", "close Chrome", "isko band karo")
    if lower_text.endswith((" band karo", " bandh karo", " close karo", " band kar")) or lower_text.startswith(("close ", "stop app ")):
        target_app = re.sub(r"\s+(band karo|bandh karo|close karo|band kar)$", "", raw_text, flags=re.IGNORECASE).strip()
        target_app = re.sub(r"^(close|stop app)\s+", "", target_app, flags=re.IGNORECASE).strip()
        return {
            "intent": "CLOSE_APPLICATION",
            "query": raw_text,
            "target": target_app or raw_text,
            "action": "close_app",
            "tool": "computer_settings"
        }

    # 0.9 MICROSOFT STORE SEARCH INTENT CHECK
    if any(k in lower_text for k in ["microsoft store", "store search", "find on store", "search store for", "on microsoft store"]):
        target = re.sub(r".*?(search|find|open)\s+(microsoft store\s+for|on microsoft store|store for)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
        return {
            "intent": "STORE_SEARCH",
            "query": raw_text,
            "target": target or raw_text,
            "tool": "store_search"
        }

    # 0.95 INSTALL APPLICATION INTENT CHECK
    if lower_text.startswith(("install ", "download ")) and not any(k in lower_text for k in ["update", "status"]):
        target = re.sub(r"^(install|download)\s+", "", raw_text, flags=re.IGNORECASE).strip()
        return {
            "intent": "INSTALL_APPLICATION",
            "query": raw_text,
            "target": target or raw_text,
            "tool": "install_app"
        }

    # 1. SPECIAL CASE: GOOGLE WEBSITE OPEN
    if lower_text in ["google kholo", "open google", "google open karo", "open google in chrome"]:
        return {"intent": "KNOWN_WEBSITE", "query": raw_text, "target": "https://www.google.com/", "service_name": "google", "tool": "web_registry"}

    # 2. EXPLICIT WEB SEARCH CHECK (e.g. "Search for Chrome", "Search Google for VS Code", "Find information about Spotify")
    if (lower_text.startswith(("search ", "google ")) and not lower_text.startswith("google khol")) or any(re.search(pat, lower_text) for pat in ["search youtube", "search instagram", "search whatsapp", "google search", "search web", "search internet", "online check", "find information about"]):
        clean_q = raw_text
        prefixes = [
            r"^google\s+search\s+for\s+",
            r"^google\s+this\s*",
            r"^search\s+[a-zA-Z0-9_\-]+\s+for\s+",
            r"^search\s+the\s+web\s+for\s+",
            r"^search\s+internet\s+for\s+",
            r"^search\s+online\s+for\s+",
            r"^search\s+for\s+",
            r"^search\s+",
            r"^google\s+for\s+",
            r"^search\s+this\s+on\s+(the\s+)?internet\s*",
            r"^find\s+official\s+website\s+of\s+",
            r"^find\s+information\s+about\s+",
            r"^internet\s+pe\s+search\s+karo\s+",
            r"^google\s+karke\s+bata\s+",
        ]
        for p in prefixes:
            clean_q = re.sub(p, "", clean_q, flags=re.IGNORECASE).strip()
        return {
            "intent": "WEB_SEARCH",
            "query": clean_q or raw_text,
            "target": "",
            "tool": "web_search"
        }

    # 2.7 UNIVERSAL COMMUNICATION & SERVICE DISCOVERY INTENTS
    if any(k in lower_text for k in ["which communication apps", "communication apps", "available services", "communication services", "social apps do i have", "apps do i have available"]):
        return {"intent": "SERVICE_DISCOVERY", "query": raw_text, "target": "", "tool": "service_discovery"}

    if any(k in lower_text for k in ["read notifications", "read my notifications", "important messages", "anything important", "check notifications", "unread messages", "unread notifications", "any new messages"]):
        return {"intent": "READ_NOTIFICATIONS", "query": raw_text, "target": "", "tool": "read_notifications"}

    if any(k in lower_text for k in ["who called me", "missed calls", "check call log", "call log"]):
        return {"intent": "READ_CALL_LOG", "query": raw_text, "target": "", "tool": "read_call_log"}

    if any(k in lower_text for k in ["send sms", "send an sms", "text message to"]):
        return {"intent": "SEND_SMS", "query": raw_text, "target": "", "tool": "send_sms"}

    if any(k in lower_text for k in ["read sms", "read my sms", "unread sms"]):
        return {"intent": "READ_SMS", "query": raw_text, "target": "", "tool": "read_sms"}

    if any(k in lower_text for k in ["all connections ka status", "connection status", "connection report", "all connections status", "connections status", "phone connected hai"]):
        return {"intent": "UNIFIED_CONNECTION_STATUS", "query": raw_text, "target": "", "tool": "unified_connection_status"}

    if any(k in lower_text for k in ["from my pc", "from my phone", "on my pc", "on my phone", "from phone to pc"]):
        return {"intent": "MOBILE_GATEWAY", "query": raw_text, "target": "", "tool": "mobile_gateway"}

    # 2.8 AWARENESS & PROACTIVE CONTROL INTENTS
    if any(k in lower_text for k in ["camera awareness", "screen awareness", "proactive mode", "companion mode", "pause all awareness", "resume awareness", "stop proactive"]):
        return {
            "intent": "AWARENESS_CONTROL",
            "query": raw_text,
            "target": "",
            "tool": "awareness_control"
        }

    if any(k in lower_text for k in ["what am i doing", "what's on my calendar", "what is on my calendar", "important emails", "what is happening on whatsapp", "why did you interrupt"]):
        return {
            "intent": "AWARENESS_QUERY",
            "query": raw_text,
            "target": "",
            "tool": "awareness_query"
        }

    # 2.8 DISCORD ACTION INTENTS
    if any(k in lower_text for k in ["discord connect", "connect karo", "discord voice join", "voice channel join", "discord join"]):
        return {"intent": "DISCORD_CONNECT", "query": raw_text, "target": "discord", "tool": "discord_connect_voice"}

    if any(k in lower_text for k in ["discord disconnect", "disconnect karo", "leave voice", "vc leave"]):
        return {"intent": "DISCORD_DISCONNECT", "query": raw_text, "target": "discord", "tool": "discord_disconnect_voice"}

    if any(k in lower_text for k in ["discord mute", "discord unmute", "discord ka mic"]):
        return {"intent": "DISCORD_MUTE", "query": raw_text, "target": "discord", "tool": "discord_mute"}

    # 3. WHATSAPP COMMUNICATION ACTIONS (MESSAGE / VOICE CALL / VIDEO CALL / OPEN CHAT / READ / REPLY / AUTOREPLY)
    for pat in WHATSAPP_END_CALL_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_END_CALL", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp"}

    for pat in WHATSAPP_VIDEO_CALL_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_VIDEO_CALL", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_video_call"}

    for pat in WHATSAPP_CALL_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_CALL", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_voice_call"}

    for pat in WHATSAPP_OPEN_CHAT_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_OPEN_CHAT", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_open_chat"}

    for pat in WHATSAPP_REPLY_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_REPLY", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_reply"}

    for pat in WHATSAPP_AUTOREPLY_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_AUTOREPLY", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp"}

    for pat in WHATSAPP_SEND_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_MESSAGE", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_send_message"}

    for pat in WHATSAPP_READ_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_READ", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp_read_messages"}

    # 4. EXPLICIT WEB APPLICATION REQUESTS (e.g. "open WhatsApp Web", "WhatsApp Web kholo")
    for pat in EXPLICIT_WHATSAPP_WEB_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_WEB", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp"}

    for pat in EXPLICIT_TELEGRAM_WEB_COMPILED:
        if pat.search(lower_text):
            return {"intent": "TELEGRAM_WEB", "query": raw_text, "target": "https://web.telegram.org/", "tool": "telegram"}

    # 5. TELEGRAM & INSTAGRAM INTENTS
    for pat in INSTAGRAM_POST_COMPILED:
        if pat.search(lower_text):
            return {"intent": "INSTAGRAM_POST", "query": raw_text, "target": "https://www.instagram.com/", "tool": "instagram"}

    # 6. COLLEGE SCHEDULE INTENTS
    for pat in COLLEGE_COMPILED:
        if pat.search(lower_text):
            return {"intent": "COLLEGE_QUERY", "query": raw_text, "target": "", "tool": "college_mode"}

    # 7. GENERAL EXPLICIT WEB SEARCH
    if any(pat.search(lower_text) for pat in WEB_SEARCH_TRIGGERS_COMPILED):
        return {"intent": "WEB_SEARCH", "query": raw_text, "target": "", "tool": "web_search"}

    # 8. WINDOWS APPLICATION INTENTS (APP-FIRST: "open chrome", "launch vs code", "start spotify", "run notepad", "open antigravity", etc.)
    if lower_text.startswith(("open ", "launch ", "start ", "run ")) or lower_text.endswith((" kholo", " khol", " open karo")):
        app_name = re.sub(r"^(open|launch|start|run)\s+", "", raw_text, flags=re.IGNORECASE).strip()
        app_name = re.sub(r"\s+(kholo|khol|open karo)$", "", app_name, flags=re.IGNORECASE).strip()
        
        # Remove trailing "application" or "app"
        app_name = re.sub(r"\s+(application|app)$", "", app_name, flags=re.IGNORECASE).strip()

        # Explicit web URL check (.com, .org, .net)
        if any(app_name.lower().endswith(ext) for ext in [".com", ".org", ".net", ".io"]):
            web_record = resolve_website_url(app_name)
            if web_record:
                return {
                    "intent": "SOCIAL_WEB" if web_record.get("category") == "social_web" else "KNOWN_WEBSITE",
                    "query": raw_text,
                    "target": web_record["url"],
                    "service_name": web_record["name"],
                    "tool": "web_registry"
                }

        return {
            "intent": "WINDOWS_APPLICATION",
            "query": raw_text,
            "target": app_name or raw_text,
            "tool": "open_app"
        }

    # 9. KNOWN WEBSITES / SOCIAL WEB FALLBACK
    web_record = resolve_website_url(raw_text)
    if web_record:
        return {
            "intent": "SOCIAL_WEB" if web_record.get("category") == "social_web" else "KNOWN_WEBSITE",
            "query": raw_text,
            "target": web_record["url"],
            "service_name": web_record["name"],
            "tool": "web_registry"
        }

    return {
        "intent": "OTHER",
        "query": raw_text,
        "target": "",
        "tool": None
    }

