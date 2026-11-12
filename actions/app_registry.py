# actions/app_registry.py
# JARVIS — Extensible Application & Service Registry

import os
import platform
try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

from typing import Dict, Any, List, Optional

# Standardized Extensible Application Registry
# Schema:
# {
#     "name": str,
#     "aliases": list[str],
#     "category": "messaging" | "email" | "social" | "productivity" | "browser" | "media" | "system" | "development" | "gaming",
#     "protocols": list[str],
#     "executables": list[str],
#     "registry_keys": list[str],
#     "install_dirs": list[str],
#     "web_url": Optional[str],
#     "process_names": list[str]
# }

APP_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ── MESSAGING ──
    "whatsapp": {
        "name": "WhatsApp",
        "aliases": ["whatsapp", "whats app", "wa", "watsapp", "whatsapp desktop"],
        "category": "messaging",
        "protocols": ["whatsapp:", "whatsapp-desktop:"],
        "executables": ["WhatsApp.exe", "WhatsAppDesktop.exe", "WhatsApp"],
        "uwp_app_ids": ["WhatsApp.WhatsApp_8wekyb3d8bbwe!App", "WhatsApp.WhatsAppDesktop_531f527m5524g!App"],
        "registry_keys": ["WhatsApp", "WhatsAppDesktop"],
        "install_dirs": ["WhatsApp", "WhatsAppDesktop"],
        "web_url": "https://web.whatsapp.com",
        "process_names": ["WhatsApp.exe", "WhatsAppDesktop.exe", "WhatsApp"],
    },
    "telegram": {
        "name": "Telegram",
        "aliases": ["telegram", "tg", "telegram desktop", "telegram web"],
        "category": "messaging",
        "protocols": ["tg:", "telegram:"],
        "executables": ["Telegram.exe", "Telegram"],
        "registry_keys": ["Telegram Desktop", "Telegram"],
        "install_dirs": ["Telegram Desktop"],
        "web_url": "https://web.telegram.org",
        "process_names": ["Telegram.exe", "Telegram"],
    },
    "discord": {
        "name": "Discord",
        "aliases": ["discord", "disc", "discord app", "discord web"],
        "category": "messaging",
        "protocols": ["discord:"],
        "executables": ["Discord.exe", "Discord"],
        "registry_keys": ["Discord"],
        "install_dirs": ["Discord"],
        "web_url": "https://discord.com/app",
        "process_names": ["Discord.exe", "Discord"],
    },
    "slack": {
        "name": "Slack",
        "aliases": ["slack", "slack app", "slack web"],
        "category": "messaging",
        "protocols": ["slack:"],
        "executables": ["Slack.exe", "Slack"],
        "registry_keys": ["Slack"],
        "install_dirs": ["Slack"],
        "web_url": "https://app.slack.com/client",
        "process_names": ["Slack.exe", "Slack"],
    },
    "signal": {
        "name": "Signal",
        "aliases": ["signal", "signal app", "signal desktop"],
        "category": "messaging",
        "protocols": ["signal:"],
        "executables": ["Signal.exe", "Signal"],
        "registry_keys": ["Signal"],
        "install_dirs": ["Signal"],
        "web_url": "https://signal.org",
        "process_names": ["Signal.exe", "Signal"],
    },
    "messenger": {
        "name": "Messenger",
        "aliases": ["messenger", "facebook messenger", "fb messenger"],
        "category": "messaging",
        "protocols": ["ms-messenger:"],
        "executables": ["Messenger.exe", "Messenger"],
        "registry_keys": ["Messenger"],
        "install_dirs": ["Messenger"],
        "web_url": "https://www.messenger.com",
        "process_names": ["Messenger.exe", "Messenger"],
    },

    # ── EMAIL ──
    "gmail": {
        "name": "Gmail",
        "aliases": ["gmail", "google mail", "my gmail", "check gmail", "email", "mail"],
        "category": "email",
        "protocols": ["mailto:"],
        "executables": [],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": "https://mail.google.com",
        "process_names": [],
    },
    "outlook": {
        "name": "Outlook",
        "aliases": ["outlook", "microsoft outlook", "ms outlook", "outlook mail", "outlook desktop"],
        "category": "email",
        "protocols": ["ms-outlook:", "mailto:"],
        "executables": ["OUTLOOK.EXE", "outlook.exe", "olk.exe", "outlook"],
        "registry_keys": ["Outlook.EXE", "Outlook"],
        "install_dirs": ["Microsoft Office", "Office16", "Outlook"],
        "web_url": "https://outlook.live.com/mail/",
        "process_names": ["OUTLOOK.EXE", "outlook.exe", "olk.exe"],
    },
    "yahoo": {
        "name": "Yahoo Mail",
        "aliases": ["yahoo mail", "yahoo", "yahoomail"],
        "category": "email",
        "protocols": [],
        "executables": [],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": "https://mail.yahoo.com",
        "process_names": [],
    },

    # ── SOCIAL ──
    "instagram": {
        "name": "Instagram",
        "aliases": ["instagram", "insta", "ig", "instagram web", "instagram app"],
        "category": "social",
        "protocols": ["instagram:"],
        "executables": ["Instagram.exe", "Instagram"],
        "registry_keys": ["Instagram"],
        "install_dirs": ["Instagram"],
        "web_url": "https://www.instagram.com",
        "process_names": ["Instagram.exe", "Instagram"],
    },
    "facebook": {
        "name": "Facebook",
        "aliases": ["facebook", "fb", "face book"],
        "category": "social",
        "protocols": ["facebook:"],
        "executables": ["Facebook.exe", "Facebook"],
        "registry_keys": ["Facebook"],
        "install_dirs": ["Facebook"],
        "web_url": "https://www.facebook.com",
        "process_names": ["Facebook.exe", "Facebook"],
    },
    "twitter": {
        "name": "X (Twitter)",
        "aliases": ["x", "twitter", "x.com", "twt", "tweet", "x twitter"],
        "category": "social",
        "protocols": ["twitter:"],
        "executables": ["Twitter.exe", "Twitter"],
        "registry_keys": ["Twitter"],
        "install_dirs": ["Twitter"],
        "web_url": "https://x.com",
        "process_names": ["Twitter.exe", "Twitter"],
    },
    "reddit": {
        "name": "Reddit",
        "aliases": ["reddit", "reddit web"],
        "category": "social",
        "protocols": [],
        "executables": ["Reddit.exe"],
        "registry_keys": ["Reddit"],
        "install_dirs": ["Reddit"],
        "web_url": "https://www.reddit.com",
        "process_names": ["Reddit.exe"],
    },
    "linkedin": {
        "name": "LinkedIn",
        "aliases": ["linkedin", "linked in"],
        "category": "social",
        "protocols": ["linkedin:"],
        "executables": ["LinkedIn.exe", "LinkedIn"],
        "registry_keys": ["LinkedIn"],
        "install_dirs": ["LinkedIn"],
        "web_url": "https://www.linkedin.com",
        "process_names": ["LinkedIn.exe", "LinkedIn"],
    },
    "youtube": {
        "name": "YouTube",
        "aliases": ["youtube", "yt", "you tube"],
        "category": "social",
        "protocols": [],
        "executables": ["YouTube.exe"],
        "registry_keys": ["YouTube"],
        "install_dirs": ["YouTube"],
        "web_url": "https://www.youtube.com",
        "process_names": ["YouTube.exe"],
    },
    "snapchat": {
        "name": "Snapchat",
        "aliases": ["snapchat", "snap", "snap chat"],
        "category": "social",
        "protocols": [],
        "executables": ["Snapchat.exe"],
        "registry_keys": ["Snapchat"],
        "install_dirs": ["Snapchat"],
        "web_url": "https://web.snapchat.com",
        "process_names": ["Snapchat.exe"],
    },
    "tiktok": {
        "name": "TikTok",
        "aliases": ["tiktok", "tik tok"],
        "category": "social",
        "protocols": [],
        "executables": ["TikTok.exe", "TikTok"],
        "registry_keys": ["TikTok"],
        "install_dirs": ["TikTok"],
        "web_url": "https://www.tiktok.com",
        "process_names": ["TikTok.exe"],
    },
    "pinterest": {
        "name": "Pinterest",
        "aliases": ["pinterest", "pin"],
        "category": "social",
        "protocols": [],
        "executables": [],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": "https://www.pinterest.com",
        "process_names": [],
    },
    "twitch": {
        "name": "Twitch",
        "aliases": ["twitch", "twitch tv"],
        "category": "social",
        "protocols": ["twitch:"],
        "executables": ["Twitch.exe", "Twitch"],
        "registry_keys": ["Twitch"],
        "install_dirs": ["Twitch"],
        "web_url": "https://www.twitch.tv",
        "process_names": ["Twitch.exe"],
    },

    # ── BROWSERS ──
    "chrome": {
        "name": "Google Chrome",
        "aliases": ["chrome", "google chrome", "browser"],
        "category": "browser",
        "protocols": ["googlechrome:", "http:", "https:"],
        "executables": ["chrome.exe", "chrome"],
        "registry_keys": ["chrome.exe", "Google Chrome"],
        "install_dirs": ["Google\\Chrome\\Application"],
        "web_url": "https://www.google.com",
        "process_names": ["chrome.exe", "chrome"],
    },
    "edge": {
        "name": "Microsoft Edge",
        "aliases": ["edge", "microsoft edge", "msedge"],
        "category": "browser",
        "protocols": ["ms-edge:", "http:", "https:"],
        "executables": ["msedge.exe", "msedge"],
        "registry_keys": ["msedge.exe", "Microsoft Edge"],
        "install_dirs": ["Microsoft\\Edge\\Application"],
        "web_url": "https://www.bing.com",
        "process_names": ["msedge.exe", "msedge"],
    },

    # ── DEVELOPMENT ──
    "antigravity": {
        "name": "Antigravity IDE",
        "aliases": ["antigravity", "anti gravity", "antigravity ide", "agy", "google antigravity"],
        "category": "development",
        "protocols": ["antigravity:"],
        "executables": ["Antigravity IDE.exe", "Antigravity.exe", "antigravity.exe"],
        "registry_keys": ["Antigravity IDE", "Antigravity"],
        "install_dirs": [
            "Antigravity IDE",
            "Antigravity",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity IDE")
        ],
        "web_url": None,
        "process_names": ["Antigravity IDE.exe", "Antigravity.exe"],
    },
    "vscode": {
        "name": "VS Code",
        "aliases": ["vscode", "vs code", "visual studio code", "code"],
        "category": "development",
        "protocols": ["vscode:"],
        "executables": ["code.exe", "code"],
        "registry_keys": ["code.exe", "Visual Studio Code"],
        "install_dirs": ["Microsoft VS Code"],
        "web_url": "https://vscode.dev",
        "process_names": ["code.exe", "code"],
    },
    "notepad": {
        "name": "Notepad",
        "aliases": ["notepad", "notes", "text editor", "note pad"],
        "category": "productivity",
        "protocols": [],
        "executables": ["notepad.exe", "notepad"],
        "registry_keys": ["notepad.exe"],
        "install_dirs": ["Windows", "System32"],
        "web_url": None,
        "process_names": ["notepad.exe", "Notepad.exe"],
    },
    "calculator": {
        "name": "Calculator",
        "aliases": ["calculator", "calc", "windows calculator"],
        "category": "productivity",
        "protocols": ["calculator:"],
        "executables": ["calc.exe"],
        "registry_keys": ["calc.exe"],
        "install_dirs": [],
        "web_url": None,
        "process_names": ["CalculatorApp.exe", "calc.exe"],
    },

    # ── MEDIA ──
    "spotify": {
        "name": "Spotify",
        "aliases": ["spotify", "music", "spotify app"],
        "category": "media",
        "protocols": ["spotify:"],
        "executables": ["Spotify.exe", "Spotify"],
        "registry_keys": ["Spotify.exe", "Spotify"],
        "install_dirs": ["Spotify"],
        "web_url": "https://open.spotify.com",
        "process_names": ["Spotify.exe", "Spotify"],
    },

    # ── SYSTEM ──
    "explorer": {
        "name": "File Explorer",
        "aliases": ["file explorer", "explorer", "files", "my computer", "this pc", "folders"],
        "category": "system",
        "protocols": [],
        "executables": ["explorer.exe", "explorer"],
        "registry_keys": ["explorer.exe"],
        "install_dirs": [],
        "web_url": None,
        "process_names": ["explorer.exe"],
    },
    "settings": {
        "name": "Settings",
        "aliases": ["settings", "system settings", "windows settings", "control panel"],
        "category": "system",
        "protocols": ["ms-settings:"],
        "executables": ["ms-settings:"],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": None,
        "process_names": ["SystemSettings.exe"],
    },
    "taskmanager": {
        "name": "Task Manager",
        "aliases": ["task manager", "taskmgr", "processes"],
        "category": "system",
        "protocols": [],
        "executables": ["taskmgr.exe"],
        "registry_keys": ["taskmgr.exe"],
        "install_dirs": [],
        "web_url": None,
        "process_names": ["Taskmgr.exe"],
    },
    "terminal": {
        "name": "Terminal",
        "aliases": ["terminal", "cmd", "command prompt", "powershell"],
        "category": "system",
        "protocols": [],
        "executables": ["wt.exe", "cmd.exe", "powershell.exe"],
        "registry_keys": ["wt.exe", "cmd.exe", "powershell.exe"],
        "install_dirs": ["WindowsTerminal"],
        "web_url": None,
        "process_names": ["WindowsTerminal.exe", "cmd.exe", "powershell.exe"],
    },

    # ── PRODUCTIVITY ──
    "calendar": {
        "name": "Calendar",
        "aliases": ["calendar", "windows calendar", "my calendar", "google calendar"],
        "category": "productivity",
        "protocols": ["outlookcal:", "ms-clock:"],
        "executables": ["outlookcal.exe"],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": "https://calendar.google.com",
        "process_names": ["outlookcal.exe"],
    },
    "maps": {
        "name": "Maps",
        "aliases": ["maps", "google maps", "bing maps"],
        "category": "productivity",
        "protocols": ["bingmaps:"],
        "executables": [],
        "registry_keys": [],
        "install_dirs": [],
        "web_url": "https://maps.google.com",
        "process_names": [],
    },
    "calculator": {
        "name": "Calculator",
        "aliases": ["calculator", "calc"],
        "category": "productivity",
        "protocols": ["calculator:"],
        "executables": ["calc.exe"],
        "registry_keys": ["calc.exe"],
        "install_dirs": [],
        "web_url": "https://www.google.com/search?q=calculator",
        "process_names": ["Calculator.exe", "calc.exe"],
    },
    "notepad": {
        "name": "Notepad",
        "aliases": ["notepad", "notes", "text editor"],
        "category": "productivity",
        "protocols": [],
        "executables": ["notepad.exe"],
        "registry_keys": ["notepad.exe"],
        "install_dirs": [],
        "web_url": None,
        "process_names": ["notepad.exe", "Notepad.exe"],
    },
    "word": {
        "name": "Microsoft Word",
        "aliases": ["word", "ms word", "microsoft word"],
        "category": "productivity",
        "protocols": ["ms-word:"],
        "executables": ["WINWORD.EXE", "winword.exe"],
        "registry_keys": ["WINWORD.EXE"],
        "install_dirs": ["Microsoft Office\\root\\Office16"],
        "web_url": "https://word.office.com",
        "process_names": ["WINWORD.EXE"],
    },
    "excel": {
        "name": "Microsoft Excel",
        "aliases": ["excel", "ms excel", "microsoft excel"],
        "category": "productivity",
        "protocols": ["ms-excel:"],
        "executables": ["EXCEL.EXE", "excel.exe"],
        "registry_keys": ["EXCEL.EXE"],
        "install_dirs": ["Microsoft Office\\root\\Office16"],
        "web_url": "https://excel.office.com",
        "process_names": ["EXCEL.EXE"],
    },
    "powerpoint": {
        "name": "Microsoft PowerPoint",
        "aliases": ["powerpoint", "ppt", "presentation"],
        "category": "productivity",
        "protocols": ["ms-powerpoint:"],
        "executables": ["POWERPNT.EXE", "powerpnt.exe"],
        "registry_keys": ["POWERPNT.EXE"],
        "install_dirs": ["Microsoft Office\\root\\Office16"],
        "web_url": "https://powerpoint.office.com",
        "process_names": ["POWERPNT.EXE"],
    },
    "zoom": {
        "name": "Zoom",
        "aliases": ["zoom", "zoom meeting"],
        "category": "productivity",
        "protocols": ["zoomus:"],
        "executables": ["Zoom.exe"],
        "registry_keys": ["Zoom.exe"],
        "install_dirs": ["Zoom\\bin"],
        "web_url": "https://zoom.us",
        "process_names": ["Zoom.exe"],
    },
    "notion": {
        "name": "Notion",
        "aliases": ["notion"],
        "category": "productivity",
        "protocols": ["notion:"],
        "executables": ["Notion.exe"],
        "registry_keys": ["Notion.exe"],
        "install_dirs": ["Notion"],
        "web_url": "https://www.notion.so",
        "process_names": ["Notion.exe"],
    },
    "obsidian": {
        "name": "Obsidian",
        "aliases": ["obsidian"],
        "category": "productivity",
        "protocols": ["obsidian:"],
        "executables": ["Obsidian.exe"],
        "registry_keys": ["Obsidian.exe"],
        "install_dirs": ["Obsidian"],
        "web_url": None,
        "process_names": ["Obsidian.exe"],
    },

    # ── GAMING ──
    "steam": {
        "name": "Steam",
        "aliases": ["steam", "steam games"],
        "category": "gaming",
        "protocols": ["steam:"],
        "executables": ["steam.exe", "steam"],
        "registry_keys": ["Steam.exe"],
        "install_dirs": ["Steam"],
        "web_url": "https://store.steampowered.com",
        "process_names": ["steam.exe"],
    },
}


def normalize_app_name(input_name: str) -> str:
    """
    Normalizes human speech input:
    - Lowercase
    - Removes speech filler words ('open', 'launch', 'start', 'take me to', 'go to', 'check', 'my', 'the', 'app', 'application', 'website', 'web', 'desktop', 'email', 'mail')
    - Strips punctuation & extra whitespace
    """
    if not input_name:
        return ""

    text = input_name.lower().strip()
    import re
    text = re.sub(r"[^\w\s]", " ", text)
    words = text.split()

    fillers = {
        "open", "launch", "start", "take", "me", "to", "go", "check", "show",
        "my", "the", "a", "an", "app", "application", "website", "web", "desktop", "please", "email", "mail"
    }

    filtered = [w for w in words if w not in fillers]
    if filtered:
        return " ".join(filtered)
    return text.strip()


def resolve_app(input_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolves natural language app name to a registry entry using:
    1. Normalized exact key match
    2. Exact alias match
    3. Safe substring & token overlap matching
    4. Dynamic fallback entry creation if confidence is reasonable
    """
    if not input_name:
        return None

    raw_clean = input_name.lower().strip()
    norm = normalize_app_name(input_name)

    # 1. Exact key match
    if norm in APP_REGISTRY:
        return APP_REGISTRY[norm]
    if raw_clean in APP_REGISTRY:
        return APP_REGISTRY[raw_clean]

    # 2. Alias match
    for key, entry in APP_REGISTRY.items():
        aliases = entry.get("aliases", [])
        if norm in aliases or raw_clean in aliases:
            return entry

    # 3. Safe Substring / Token overlap match
    for key, entry in APP_REGISTRY.items():
        if key == norm or key in norm or norm in key:
            return entry
        for alias in entry.get("aliases", []):
            if alias == norm or (len(alias) >= 3 and (alias in norm or norm in alias)):
                return entry

    # 4. Fallback: Create dynamic entry for custom/unregistered app
    import re
    cleaned_title = re.sub(r"^(open|launch|start|take me to|go to|check|my|the|show|\s)+", "", input_name.strip(), flags=re.IGNORECASE).strip()
    title = cleaned_title.title() if cleaned_title else input_name.strip().title()
    clean_k = norm.replace(" ", "")
    return {
        "name": title,
        "aliases": [norm, raw_clean],
        "category": "productivity",
        "protocols": [f"{clean_k}:"],
        "executables": [f"{title}.exe", f"{clean_k}.exe", norm],
        "registry_keys": [f"{clean_k}.exe"],
        "install_dirs": [title],
        "web_url": None,
        "process_names": [f"{title}.exe", f"{clean_k}.exe"],
    }


def find_app_path_in_registry(exec_name: str) -> Optional[str]:
    """
    Queries Windows Registry App Paths (HKCU & HKLM) with support for 32-bit & 64-bit views.
    """
    if not _HAS_WINREG or platform.system() != "Windows":
        return None

    hkeys = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    subpath = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

    flags = [0]
    if hasattr(winreg, "KEY_WOW64_64KEY"):
        flags.append(winreg.KEY_WOW64_64KEY)
    if hasattr(winreg, "KEY_WOW64_32KEY"):
        flags.append(winreg.KEY_WOW64_32KEY)

    exec_candidates = [exec_name]
    if not exec_name.endswith(".exe"):
        exec_candidates.append(f"{exec_name}.exe")

    for hkey in hkeys:
        for flag in flags:
            for exe in exec_candidates:
                try:
                    with winreg.OpenKey(hkey, f"{subpath}\\{exe}", 0, winreg.KEY_READ | flag) as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and os.path.exists(val):
                            return val
                except Exception:
                    pass

    return None


def is_app_installed(app_name: str) -> bool:
    """Returns True if the application executable or installation registry key exists."""
    app_info = resolve_app(app_name)
    if not app_info:
        return False
    execs = app_info.get("executables", [])
    for exe in execs:
        if find_app_path_in_registry(exe):
            return True
    return bool(app_info.get("installed", False))
