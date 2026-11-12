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
    r"\bvideo call [a-zA-Z0-9_\s]+ on whatsapp\b",
    # Hinglish: "X ko video call laga" / "X ko video call kar"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+video\s+call\s+(?:laga|lagao|kar|karo|kar\s*do)\b",
]

WHATSAPP_CALL_PATTERNS = [
    r"\bwhatsapp\b.*\b(call|voice call)\b",
    r"\bcall\b.*\bwhatsapp\b",
    r"\b[a-zA-Z0-9_\s]+ ko whatsapp (call|voice call)\b",
    r"\bwhatsapp pe [a-zA-Z0-9_\s]+ ko call\b",
    r"\b[a-zA-Z0-9_\s]+ ko call (karo|kar do|khol)\b",
    r"\bcall [a-zA-Z0-9_\s]+\b",
    # Hinglish: "X ko call laga" / "X ko call kar" / "X ko voice call laga"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+(?:voice\s+)?call\s+(?:laga|lagao|kar|karo|kar\s*do)\b",
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
    r"\bwhatsapp\s+[a-zA-Z0-9_\s]+\s+(and\s+)?(say|tell)\b",
    # Hinglish: "X ko Y bhej" / "X ko Y send kar" / "X ko Y bhej de"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+.+\s+(bhej|bhej\s*de|bhejo|send\s+kar|send\s+karo)\s*$",
    # Hinglish: "X ko bol Y" / "X ko bolo Y"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+(bol|bolo|bol\s*de|bolna)\s+.+",
    # Hinglish: "X ko ping kar"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+ping\s+(kar|karo)\b",
    # Hinglish: "X ko message kar Y"
    r"\b[a-zA-Z0-9_\s]+\s+ko\s+(message|msg)\s+(kar|karo|kar\s*do)\s+.+",
    # Hinglish: "X ko hello bhej" simplified
    r"\b\w+\s+ko\s+\w+\s+bhej\b",
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
    r"\b(?:chrome|edge|firefox|brave|browser|browsers)\b.*\b(?:search\s+(?:engine|settings|preferences)|default\s+(?:search|engine)|default\s+kar\s+do|change\s+search\s+engine|preferences|settings)\b",
    r"\bsearch\s+(?:settings|preferences)\b.*\b(?:chrome|edge|firefox|brave|browser)\b",
    r"\b(?:sab\s+)?browsers?\b.*\b(?:settings|preferences)\b",
    r"\b(?:chrome|edge|firefox|brave)\b.*\b(?:google|bing|duckduckgo|brave search|yahoo)\b.*\b(?:use|set|default|use karo|set karo)\b",
    r"\b(?:chrome|edge|firefox|brave)\b.*\b(?:search|dhundho|dhoondho)\b",
    r"google\s+search", r"search\s+(the\s+)?web", r"search\s+(the\s+)?internet",
    r"search\s+online", r"look\s+it\s+up", r"look\s+this\s+up", r"check\s+online",
    r"search\s+news", r"search\s+for", r"google\s+for", r"google\s+this", r"google\s+it",
    r"internet\s+pe\s+search", r"google\s+karke\s+bata", r"search\s+karo",
    r"latest\s+news", r"current\s+price", r"latest\s+price", r"today'?s\s+weather",
    r"live\s+score", r"latest\s+update", r"official\s+website",
    r"\blatest\b", r"\bcurrent\s+(?:price|news|score|weather|exchange rate|stock)\b",
    r"\b(?:internet|web|online)\s+(?:se|pe|par)\s+(?:dhund|dhoond|search|dekh|check)",
    r"\b(?:aaj|abhi)\b.*\b(?:score|news|price|rate|weather|mausam|khabar)\b",
    r"इंटरनेट.*(?:खोज|ढूंढ|सर्च)", r"(?:ताज़ा|ताजा|आज का).*(?:समाचार|खबर|स्कोर|मौसम)",
    r"\b(?:centuries|hundreds|odi runs|wickets|squad|rankings?|ceo|president|prime minister)\b",
    r"\b(?:standings?|points\s+tables?|team\s+rankings?|tournament\s+rankings?|cricket\s+results?)\b",
    r"\b(?:points|rank|position)\b.*\b(?:kitne|kitni|number|position|rank)\b",
    r"\b(?:how many|kitne|kitni|total)\b.*\b(?:runs|matches|centur|shatak|hundred|goals|wins)\w*",
    r"(?:शतक|टीम.*घोषणा|कप्तान|प्रधानमंत्री|राष्ट्रपति)",
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


def normalize_command_prefix(text: str) -> str:
    """Remove leading conversational words while preserving the message body."""
    command = (text or "").strip()
    pattern = r"^(?:(?:hey|hi|hello|ok|okay|ओके|हे|हेलो)[,\s]+)?(?:jarvis|jervis|जार्विस|जारविस|जर्विस|boss|sir|bhaiya|bhai|yaar|dost)\b(?:[,\s:!?।]+|$)|^(?:please|pls|can you|could you|would you|kindly|zara|ek baar|ab|phir|fir|now|then|aur|and|next)\s+"
    for _ in range(5):
        clean = re.sub(pattern, "", command, count=1, flags=re.I).strip()
        if clean == command:
            break
        command = clean
    return command


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

    clean_raw = normalize_command_prefix(raw_text).rstrip(".?!,;: ")
    clean_raw = re.sub(r"[,\s]+(boss|sir|jarvis|bhai|yaar)$", "", clean_raw, flags=re.IGNORECASE).strip()
    if not clean_raw:
        clean_raw = raw_text.rstrip(".?!,;: ")
    lower_text = clean_raw.casefold()

    from agent.task_manager import parse_assignment
    if parse_assignment(clean_raw):
        return {'intent': 'TASK_MANAGER', 'query': clean_raw, 'target': '', 'tool': 'task_manager'}

    # Drafting is a conversation task, never text injection into the active app.
    drafting = (re.search(r'\b(?:email|e-mail|mail|letter|application|cover letter|reply|message)\b', lower_text)
                and re.search(r'\b(?:draft|compose|write|likh|likho|likhna|likhni|bana|banao|banado)\b', lower_text))
    if drafting and not re.match(r'^(?:type|isme|yahan|paste)\b', lower_text):
        return {'intent': 'DRAFT_TEXT', 'query': raw_text, 'target': '', 'tool': 'ai_brain'}

    # Explicit social platforms take priority over generic WhatsApp patterns.
    from actions.social_chat import parse_social_command
    social = parse_social_command(clean_raw)
    if social:
        return {"intent": "SOCIAL_CHAT", "tool": "social_chat", "query": raw_text, **social}

    from actions.youtube_browser import parse_youtube_request
    communication = parse_social_command(clean_raw, include_whatsapp=True)
    from actions.model_3d import parse_model_request
    model_request = parse_model_request(clean_raw) if not communication else None
    if model_request:
        return {'intent': 'MODEL_3D', 'tool': 'model_3d', **model_request}
    from core.study_documents import attachment_request
    study = attachment_request(clean_raw) if not communication else None
    if study:
        return {'intent': 'STUDY_DOCUMENT', 'tool': 'study_document', **study}
    youtube = parse_youtube_request(clean_raw) if not communication else None
    if youtube:
        return {'intent': 'YOUTUBE_VIDEO', 'tool': 'youtube_video', **youtube}
    contacts_control = re.fullmatch(r'(connect|sync|refresh|import|status) (?:google |gmail )?contacts(?: (?:karo|kar))?|(?:google |gmail )?contacts (connect|sync|refresh|import|status)(?: (?:karo|kar))?', lower_text)
    if contacts_control:
        action = contacts_control[1] or contacts_control[2]
        return {'intent': 'CONTACT_DIRECTORY', 'tool': 'contact_directory', 'action': 'sync' if action == 'refresh' else action}
    if (not communication and re.search(r'\bcontacts\b', lower_text)
            and re.search(r'\b(?:gmail|google)\b', lower_text)
            and re.search(r'\b(?:sync|refresh|connect|import)\b', lower_text)):
        action = 'import' if re.search(r'\bimport\b', lower_text) else 'connect' if re.search(r'\bconnect\b', lower_text) else 'sync'
        return {'intent': 'CONTACT_DIRECTORY', 'tool': 'contact_directory', 'action': action}

    # 0. CURRENT TIME & DATE FAST-PATH INTENT CHECK
    time_patterns = [
        "what time is it", "what's the time", "what is the time", "current time", "tell me the time",
        "time kya hua", "time kya hai", "kitne baje", "kitna time hua", "time batao", "time bata",
        "what day is it", "what is the date", "what's the date", "today's date", "aaj ki date", "aaj konsa din"
    ]
    if any(k in lower_text for k in time_patterns) or (lower_text.startswith("time") and len(lower_text.split()) <= 3):
        return {
            "intent": "CURRENT_TIME",
            "query": raw_text,
            "tool": "system_info"
        }

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

    # Exact controls precede generic observation; never match message payloads.
    camera_control_match = re.fullmatch(r'(?:camera|cam|webcam|कैमरा) (on|off|status|chalu|band|चालू|बंद)(?: karo| kar| करो)?', lower_text.strip(' ,.!?।'))
    if camera_control_match:
        action = {'chalu': 'on', 'चालू': 'on', 'band': 'off', 'बंद': 'off'}.get(camera_control_match[1], camera_control_match[1])
        return {'intent': 'CAMERA_CONTROL', 'tool': 'camera_control', 'action': action, 'query': raw_text}
    if lower_text.strip(' ,.!?।') in ('access status', 'permissions status', 'laptop access status', 'meri permissions dikhao', 'kya access hai', 'what can you access'):
        return {'intent': 'ASSISTANT_ACCESS', 'tool': 'assistant_access', 'query': raw_text}

    # 0.1 SCREEN OBSERVATION & VISION ANALYSIS INTENTS ("Screen dekh", "Screen analyze karo", "What's on my screen?")
    screen_vision_patterns = [
        "screen dekh", "screen dekho", "screen dekhna", "screen analyze", "screen pe kya", "screen par kya",
        "screen check", "look at my screen", "look at the screen", "what's on my screen", "what is on my screen",
        "analyze my screen", "analyze screen", "can you see my screen", "ye screen pe kya", "screen par dekho",
        "dekh screen pe", "screen pe dekh", "screen dikhao", "read my screen", "screen reading", "screen observe",
        "webcam dekh", "camera dekh", "cam dekh", "camera check", "look at camera", "what do you see in camera"
    ]
    if any(k in lower_text for k in screen_vision_patterns) or re.search(r'(?:स्क्रीन|स्क्रिन|कैमरा).*(?:देख|दिख|एनालाइज|अनालाइज|पढ़|चेक)', lower_text) or re.search(r"\b(screen|camera|webcam|cam)\b.*\b(dekh|dekho|dekhiyo|analyze|look|see|inspect|read|check)\b", lower_text) or re.search(r"\b(dekh|dekho|analyze|look at|inspect)\b.*\b(screen|camera|webcam|cam)\b", lower_text):
        angle = "camera" if re.search(r'\b(?:camera|webcam|cam)\b|कैमरा', lower_text) else "screen"
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

    # VISUAL AGENT INTENTS (screen interaction, click, UI inspection, error debugging)
    visual_agent_patterns = [
        "click the", "click on", "button click", "button dabao", "pe click karo",
        "screen dekh ke bata", "screen dekho", "screen pe kya hai", "what is on my screen",
        "ye error fix karo", "isme problem kya hai", "error check karo", "screen analyze",
        "type in the", "type into", "scroll down", "scroll up",
        "look at my screen", "inspect screen", "screen mein kya dikh raha",
        "continue button", "submit button", "next button", "ok button",
        "right click", "double click",
    ]
    if any(k in lower_text for k in visual_agent_patterns):
        return {"intent": "VISUAL_AGENT", "query": raw_text, "tool": "visual_agent"}

    # WORKFLOW INTENTS
    workflow_patterns = [
        "workflow run", "workflow chala", "workflow start", "workflow create",
        "workflow bana", "workflow save", "workflow list", "workflow delete",
        "workflow cancel", "run workflow", "create workflow", "list workflows",
        "saved workflows", "mere workflows", "workflow dikhao",
    ]
    if any(k in lower_text for k in workflow_patterns):
        return {"intent": "WORKFLOW", "query": raw_text, "tool": "workflow_engine"}

    # MACRO INTENTS
    macro_patterns = [
        "study mode", "coding setup", "morning routine", "macro run",
        "macro chala", "macro start", "macro create", "macro bana",
        "macro list", "macro delete", "run macro", "create macro",
        "macros dikhao", "same kaam firse", "wahi kaam dobara",
    ]
    if any(k in lower_text for k in macro_patterns):
        return {"intent": "MACRO", "query": raw_text, "tool": "macro_executor"}

    # NOTES INTENTS
    notes_patterns = [
        "note this", "note down", "note bana", "note likh", "save note",
        "my notes", "mere notes", "notes dikhao", "open notes", "show notes",
        "note search", "find note", "note kya likha tha", "yesterday note",
        "hackathon notes", "project notes", "study notes",
    ]
    if any(k in lower_text for k in notes_patterns):
        return {"intent": "NOTES", "query": raw_text, "tool": "notes_manager"}

    # PERSONAL PROFILE INTENTS
    profile_patterns = [
        "my name is", "mera naam", "i like", "mujhe pasand", "my hobby",
        "remember that i", "yaad rakh", "my favorite", "mera favorite",
        "my preference", "meri preference", "my profile", "mera profile",
        "what do you know about me", "mere baare mein kya jaante ho",
        "privacy mode", "forget me", "clear profile", "delete my data",
    ]
    if any(k in lower_text for k in profile_patterns):
        return {"intent": "PERSONAL_PROFILE", "query": raw_text, "tool": "personal_profile"}

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

    if any(k in lower_text for k in ["volume up", "volume down", "volume badhao", "volume badha", "volume kam", "volume kam karo", "awaz badhao", "awaz badha", "awaz kam", "awaz kam karo", "volume increase", "volume decrease", "increase volume", "decrease volume", "turn volume up", "turn volume down", "mute system", "unmute system", "open wifi settings", "open bluetooth settings", "open windows settings"]):
        act = "volume_up" if any(x in lower_text for x in ["up", "badha", "increase"]) else ("volume_down" if any(x in lower_text for x in ["down", "kam", "decrease"]) else ("mute" if "mute" in lower_text else "open_settings"))
        return {"intent": "COMPUTER_SETTINGS", "query": raw_text, "action": act, "tool": "computer_settings"}

    if any(k in lower_text for k in ["wifi on", "wifi off", "turn on wifi", "turn off wifi", "wifi chalu", "wifi band", "bluetooth on", "bluetooth off", "turn on bluetooth", "turn off bluetooth"]):
        act = "toggle_wifi" if "wifi" in lower_text else "open_settings"
        return {"intent": "COMPUTER_SETTINGS", "query": raw_text, "action": act, "tool": "computer_settings"}

    # TIMER, ALARM & REMINDER FAST-PATH INTENT CHECKS
    if re.search(r"\b(?:set|create)(?:\s+(?:a|an))?\s+(?:reminder|timer|alarm)\b", lower_text) or any(k in lower_text for k in [
        "remind me", "set reminder", "reminder set", "reminder laga", "create reminder",
        "mujhe yaad dilana", "yaad dilana", "yaad dila", "remind kar", "timer laga", "set timer", "timer set",
        "alarm laga", "set alarm", "alarm set"
    ]):
        return {"intent": "REMINDER", "query": raw_text, "tool": "reminder"}

    # APPLICATION CLOSE FAST-PATH INTENT CHECK ("Chrome band karo", "close Chrome", "isko band karo")
    if lower_text.endswith((" band karo", " bandh karo", " close karo", " band kar")) or lower_text.startswith(("close ", "stop app ")):
        target_app = re.sub(r"\s+(band karo|bandh karo|close karo|band kar)$", "", clean_raw, flags=re.IGNORECASE).strip()
        target_app = re.sub(r"^(close|stop app)\s+", "", target_app, flags=re.IGNORECASE).strip()
        target_app = target_app.rstrip(" .")
        return {
            "intent": "CLOSE_APPLICATION",
            "query": raw_text,
            "target": target_app or clean_raw,
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
    if any(lower_text == k or lower_text.startswith(k + " ") for k in ["google kholo", "google khol", "google chala", "google chalao", "open google", "google open karo", "google open kar", "open google in chrome"]):
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
            return {"intent": "WHATSAPP_END_CALL", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp"}

    for pat in WHATSAPP_VIDEO_CALL_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_VIDEO_CALL", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_video_call"}

    for pat in WHATSAPP_CALL_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_CALL", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_voice_call"}

    for pat in WHATSAPP_OPEN_CHAT_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_OPEN_CHAT", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_open_chat"}

    for pat in WHATSAPP_REPLY_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_REPLY", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_reply"}

    for pat in WHATSAPP_AUTOREPLY_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_AUTOREPLY", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp"}

    for pat in WHATSAPP_SEND_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_MESSAGE", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_send_message"}

    for pat in WHATSAPP_READ_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_READ", "query": raw_text, "target": "WINDOWS_INSTALLED_WHATSAPP_DESKTOP", "tool": "whatsapp_read_messages"}

    # 4. EXPLICIT WEB APPLICATION REQUESTS (e.g. "open WhatsApp Web", "WhatsApp Web kholo")
    for pat in EXPLICIT_WHATSAPP_WEB_COMPILED:
        if pat.search(lower_text):
            return {"intent": "WHATSAPP_WEB", "query": raw_text, "target": "https://web.whatsapp.com/", "tool": "whatsapp", "mode": "web", "action": "open"}

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

    # 6.5 SENSITIVE ACTIONS (High/Critical risk operations requiring explicit confirmation)
    if any(k in lower_text for k in ["format drive", "format disk", "delete all", "disable defender", "disable firewall"]):
        return {"intent": "SENSITIVE", "query": raw_text, "target": "", "tool": "security_confirmation"}

    # 6.6 COMPLEX MULTI-STEP PLANNER INTENTS
    has_multi_clause = bool(
        re.search(r"\b(and|aur|phir|then)\b", lower_text) and
        re.search(r"\b(open|launch|kholo|khol|check|find|write|likho|inspect|analyze|solve|research)\b", lower_text)
    )
    if has_multi_clause or any(k in lower_text for k in [
        "open antigravity and", "antigravity kholo aur", "open notepad and", "notepad kholo aur",
        "find my project and", "inspect the build", "check the build", "inspect the latest error",
        "mera jarvis project open karo", "build error check karo"
    ]):
        return {"intent": "COMPLEX_PLANNER", "query": raw_text, "target": "", "tool": "task_planner"}

    # 6.7 SCREEN VISION INTENTS
    if any(k in lower_text for k in [
        "what is on my screen", "what's on my screen", "screen pe kya hai", "screen pe kya chal raha",
        "dekho screen", "screen dekho", "look at my screen", "screen check karo", "inspect screen"
    ]):
        return {"intent": "SCREEN_ANALYSIS", "query": raw_text, "target": "", "tool": "screen_process"}

    # 6.8 SELF DIAGNOSTICS & SYSTEM TELEMETRY INTENTS
    raw_lower = raw_text.lower()
    if any(k in lower_text or k in raw_lower for k in [
        "jarvis status", "system check", "kya chal raha hai", "which ai", "konsa ai", "why are you slow",
        "system status", "diagnostics", "status"
    ]) or lower_text == "status":
        return {"intent": "DIAGNOSTICS", "query": raw_text, "target": "", "tool": "diagnostics"}

    # 6.9 UNIFIED TASK MANAGER INTENTS
    if any(k in lower_text for k in [
        "pending tasks", "tasks batao", "sabse important", "most important task",
        "kal assignment submit", "friday tak project", "complete mark karo", "mark complete"
    ]):
        return {"intent": "TASK_MANAGER", "query": raw_text, "target": "", "tool": "task_manager"}

    # 6.10 AMBIGUOUS SINGLE-WORD QUERIES
    clean_words = [w for w in lower_text.split() if len(w) > 1]
    if len(clean_words) == 1 and clean_words[0] in ["file", "window", "project", "open", "kholo", "check"]:
        return {"intent": "AMBIGUOUS", "query": raw_text, "target": clean_words[0], "tool": "clarification"}

    # Fresh/explicit lookups must precede static knowledge answers.
    if any(pat.search(lower_text) for pat in WEB_SEARCH_TRIGGERS_COMPILED):
        return {"intent": "WEB_SEARCH", "query": raw_text, "target": "", "tool": "web_search"}

    # 6.11 INFORMATION & KNOWLEDGE QUESTIONS
    if (lower_text.startswith(("what is ", "who is ", "who was ", "explain ", "what are ", "why does ", "how does "))
            and not any(k in lower_text for k in ["screen", "class", "schedule", "timetable", "assignment", "status", "ai", "today's", "weather"])):
        return {"intent": "INFORMATION", "query": raw_text, "target": "", "tool": "ai_brain"}

    # 7.5 TYPING & KEYBOARD INPUT INTENT ("Isme hello type karo", "type hello", "hello type karo", "isme likho hello")
    typing_extracted = None
    # Pattern A: 'isme type karo hello' or 'isme likho hello' or 'type hello'
    mA = re.search(r"^(?:isme|yahan|in it|here)?\s*(?:type|write|likho|likh do|likh)\s+(?:karo\s+|kar do\s+)?(.+?)(?:\s*(?:karo|kar do|kardo))?$", lower_text, re.IGNORECASE)
    if mA:
        val = mA.group(1).strip()
        if val and not any(val.startswith(x) for x in ["open ", "khol ", "close ", "band ", "http"]):
            typing_extracted = val

    # Pattern B: 'isme hello type karo' or 'hello type karo'
    if not typing_extracted:
        mB = re.search(r"^(?:isme|yahan|in it|here)?\s*(.+?)\s+(?:type|likho|likh)\s*(?:karo|kar do|kardo|de|do)$", lower_text, re.IGNORECASE)
        if mB:
            val = mB.group(1).strip()
            if val and not any(val.startswith(x) for x in ["open ", "khol ", "close ", "band ", "http"]):
                typing_extracted = val

    if typing_extracted:
        return {
            "intent": "TYPING",
            "query": raw_text,
            "target": typing_extracted,
            "text": typing_extracted,
            "tool": "computer_control",
            "action": "type",
        }

    # 8. WINDOWS APPLICATION INTENTS (APP-FIRST: "open chrome", "launch vs code", "start spotify", "run notepad", "open antigravity", etc.)
    app_open_prefixes = ("open ", "launch ", "start ", "run ", "chalao ", "chala ")
    app_open_suffixes = (
        " kholo", " khol", " khol de", " khol do", " khol dena",
        " open karo", " open kar", " open kardo", " open karde", " kholna", " kholo na",
        " chala", " chalao", " chala do", " chala de", " chalana",
        " start karo", " start kar", " run karo", " run kar"
    )
    if lower_text.startswith(app_open_prefixes) or any(lower_text.endswith(s) for s in app_open_suffixes):
        app_name = clean_raw
        for p in ("open", "launch", "start", "run", "chalao", "chala"):
            app_name = re.sub(rf"^{p}\s+", "", app_name, flags=re.IGNORECASE).strip()
        for s in (
            "kholo na", "kholo", "khol de", "khol do", "khol dena", "kholna", "khol",
            "open kardo", "open karde", "open karo", "open kar",
            "chala do", "chala de", "chalao", "chala", "chalana",
            "start karo", "start kar", "run karo", "run kar"
        ):
            app_name = re.sub(rf"\s+{s}$", "", app_name, flags=re.IGNORECASE).strip()
        app_name = app_name.strip(" '\"`.,")
        
        # Remove trailing "application" or "app"
        app_name = re.sub(r"\s+(application|app)$", "", app_name, flags=re.IGNORECASE).strip()
        app_name = app_name.strip(" '\"`.,")

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

