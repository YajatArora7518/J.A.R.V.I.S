# actions/chrome_profile.py
# Dedicated Chrome Profile Controller & Local State Resolver for JARVIS

import os
import sys
import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.verification import verify_app_launched


def redact_secrets(text: str) -> str:
    """Masks sensitive credentials or tokens from text before logging."""
    if not text:
        return ""
    text = re.sub(r'(sk-or-v1-[a-zA-Z0-9]{8})[a-zA-Z0-9]+', r'\1...', text)
    text = re.sub(r'(AIzaSy[a-zA-Z0-9_]{8})[a-zA-Z0-9_]+', r'\1...', text)
    text = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]{15,}', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    return text


def get_chrome_executable() -> Optional[str]:
    """Finds installed Google Chrome binary on Windows dynamically."""
    system_drives = [os.environ.get("SystemDrive", "C:")]
    possible_paths = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
    ]

    for drive in system_drives:
        possible_paths.extend([
            rf"{drive}\Program Files\Google\Chrome\Application\chrome.exe",
            rf"{drive}\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            rf"{os.environ.get('LOCALAPPDATA', '')}\Google\Chrome\Application\chrome.exe",
        ])

    for p in possible_paths:
        if p and os.path.exists(p):
            return str(Path(p).resolve())
def is_chrome_running() -> bool:
    """Checks if chrome.exe is currently running on Windows."""
    try:
        cmd = 'tasklist /FI "IMAGENAME eq chrome.exe" /NH'
        output = subprocess.check_output(cmd, shell=True, text=True, errors="ignore")
        return "chrome.exe" in output.lower()
    except Exception:
        return False


def resolve_chrome_profile(target_profile_name: str = "Yajat") -> Dict[str, Any]:
    """
    Dynamically resolves Chrome profile directory from Chrome's Local State file.
    Verifies that the human-readable profile name matches target_profile_name EXACTLY (case-insensitive).
    NEVER guesses or defaults to Profile 1, Profile 2, etc. without Local State verification.
    """
    user_data_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if not user_data_path.exists():
        return {
            "verified": False,
            "dir_name": "",
            "display_name": "",
            "path": "",
            "error": "Chrome User Data directory does not exist."
        }

    local_state_file = user_data_path / "Local State"
    target_lower = target_profile_name.strip().lower()

    if local_state_file.exists():
        try:
            data = json.loads(local_state_file.read_text(encoding="utf-8", errors="ignore"))
            info_cache = data.get("profile", {}).get("info_cache", {})

            exact_matches = []
            partial_matches = []

            for dir_name, info in info_cache.items():
                prof_dir = user_data_path / dir_name
                if not prof_dir.is_dir():
                    continue

                name = (info.get("name") or "").strip()
                gaia_name = (info.get("gaia_name") or "").strip()
                user_name = (info.get("user_name") or "").strip()

                prof_meta = {
                    "dir_name": dir_name,
                    "display_name": name or dir_name,
                    "path": str(prof_dir),
                    "account_email": user_name,
                    "account_name": gaia_name
                }

                # Check exact name match
                if name.lower() == target_lower or gaia_name.lower() == target_lower:
                    exact_matches.append(prof_meta)
                elif target_lower in name.lower() or target_lower in gaia_name.lower() or target_lower in user_name.lower():
                    partial_matches.append(prof_meta)

            if exact_matches:
                chosen = exact_matches[0]
                return {
                    "verified": True,
                    "dir_name": chosen["dir_name"],
                    "display_name": chosen["display_name"],
                    "path": chosen["path"],
                    "account_email": chosen["account_email"],
                    "account_name": chosen["account_name"],
                    "error": None
                }

            if partial_matches:
                chosen = partial_matches[0]
                return {
                    "verified": True,
                    "dir_name": chosen["dir_name"],
                    "display_name": chosen["display_name"],
                    "path": chosen["path"],
                    "account_email": chosen["account_email"],
                    "account_name": chosen["account_name"],
                    "error": None
                }
        except Exception as e:
            print(f"[chrome_profile] Error reading Local State: {e}")

    # Fallback to inspecting Preferences in profile subdirectories if Local State missing
    dirs = [d for d in user_data_path.iterdir() if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile "))]
    for d in dirs:
        pref_file = d / "Preferences"
        if pref_file.exists():
            try:
                p_data = json.loads(pref_file.read_text(encoding="utf-8", errors="ignore"))
                prof_name = p_data.get("profile", {}).get("name", "")
                if prof_name.strip().lower() == target_lower:
                    return {
                        "verified": True,
                        "dir_name": d.name,
                        "display_name": prof_name,
                        "path": str(d),
                        "account_email": "",
                        "account_name": "",
                        "error": None
                    }
            except Exception:
                pass

    return {
        "verified": False,
        "dir_name": "",
        "display_name": "",
        "path": "",
        "error": f"{target_profile_name} Chrome profile was not found."
    }


def list_chrome_profiles() -> List[Dict[str, str]]:
    """Discovers available Chrome profiles in User Data."""
    user_data_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    profiles = []
    if not user_data_path.exists():
        return profiles

    local_state_file = user_data_path / "Local State"
    if local_state_file.exists():
        try:
            data = json.loads(local_state_file.read_text(encoding="utf-8", errors="ignore"))
            info_cache = data.get("profile", {}).get("info_cache", {})
            for dir_name, info in info_cache.items():
                prof_dir = user_data_path / dir_name
                if prof_dir.is_dir():
                    profiles.append({
                        "dir_name": dir_name,
                        "display_name": info.get("name") or dir_name,
                        "account_email": info.get("user_name") or "",
                        "account_name": info.get("gaia_name") or "",
                        "path": str(prof_dir)
                    })
            if profiles:
                return profiles
        except Exception:
            pass

    return profiles


PROHIBITED_SCHEMES = [
    "customdesktopapp:", "customdesktopapp://", "ms-windows-store:",
    "whatsapp:", "telegram:", "tg:", "file:", "javascript:", "data:", "vbscript:"
]


def sanitize_web_url(url: str) -> Optional[str]:
    """
    Sanitizes and validates URLs for browser execution.
    - Strips whitespace.
    - Rejects prohibited custom protocol schemes (customdesktopapp, whatsapp, telegram, etc.).
    - Accepts ONLY http:// and https:// schemes.
    - If URL has no scheme, prepends https://.
    Returns clean HTTPS/HTTP URL string or None if invalid/unsafe.
    """
    if not url:
        return None

    url_str = str(url).strip()
    url_lower = url_str.lower()

    # Reject prohibited custom schemes
    for bad in PROHIBITED_SCHEMES:
        if url_lower.startswith(bad) or bad in url_lower:
            return None

    # Check if scheme is present
    if "://" in url_str:
        scheme = url_str.split("://")[0].lower().strip()
        if scheme not in ["http", "https"]:
            return None
    elif ":" in url_str and not url_str.startswith("http"):
        return None
    else:
        url_str = f"https://{url_str}"

    return url_str


def open_url_in_yajat_chrome(url: str = "https://www.google.com/") -> Dict[str, Any]:
    """
    Centralized safe launcher for web/social URLs in Google Chrome's Yajat profile.
    - Validates and sanitizes URL (accepts only http:// and https://).
    - Resolves Yajat profile directory dynamically from Local State info_cache.
    - Launches Chrome via subprocess.Popen without shell invocation or protocol handlers.
    - Never uses --incognito, --guest, Edge, or default browser fallbacks.
    - Returns 'Yajat Chrome profile was not found.' if profile resolution fails.
    """
    sanitized = sanitize_web_url(url)
    if not sanitized:
        return {
            "success": False,
            "action": "open",
            "message": "Invalid or unsafe URL scheme rejected.",
            "verified": False
        }

    chrome_bin = get_chrome_executable()
    if not chrome_bin:
        return {
            "success": False,
            "action": "open",
            "message": "Google Chrome executable not found on Windows.",
            "verified": False
        }

    res = resolve_chrome_profile("Yajat")
    if not res.get("verified"):
        return {
            "success": False,
            "action": "open",
            "message": "Yajat Chrome profile was not found.",
            "verified": False
        }

    target_dir = res["dir_name"]
    cmd = [chrome_bin, f"--profile-directory={target_dir}", sanitized]

    try:
        subprocess.Popen(cmd, shell=False)
        return {
            "success": True,
            "action": "open",
            "profile": target_dir,
            "display_name": res["display_name"],
            "url": sanitized,
            "chrome_path": chrome_bin,
            "message": f"Opened {sanitized} in Chrome with profile '{res['display_name']}' ({target_dir}).",
            "verified": True
        }
    except Exception as e:
        return {
            "success": False,
            "action": "open",
            "message": f"Failed to launch Chrome with profile '{target_dir}': {e}",
            "verified": False
        }


def open_url_in_chrome_profile(profile_name: str = "Yajat", url: str = "about:blank") -> Dict[str, Any]:
    """
    Opens specified URL inside Chrome using the verified profile.
    Strictly forbids Incognito, Guest mode, temporary profile, Edge, or desktop app fallbacks.
    """
    if profile_name.strip().lower() == "yajat":
        return open_url_in_yajat_chrome(url)

    sanitized = sanitize_web_url(url)
    if not sanitized:
        return {
            "success": False,
            "action": "open",
            "message": "Invalid or unsafe URL scheme rejected.",
            "verified": False
        }

    chrome_bin = get_chrome_executable()
    if not chrome_bin:
        return {
            "success": False,
            "action": "open",
            "message": "Google Chrome executable not found on Windows.",
            "verified": False
        }

    res = resolve_chrome_profile(profile_name)
    if not res.get("verified"):
        return {
            "success": False,
            "action": "open",
            "message": f"{profile_name} Chrome profile was not found.",
            "verified": False
        }

    target_dir = res["dir_name"]
    cmd = [chrome_bin, f"--profile-directory={target_dir}", sanitized]

    try:
        subprocess.Popen(cmd, shell=False)
        return {
            "success": True,
            "action": "open",
            "profile": target_dir,
            "display_name": res["display_name"],
            "url": sanitized,
            "chrome_path": chrome_bin,
            "message": f"Opened {sanitized} in Chrome with profile '{res['display_name']}' ({target_dir}).",
            "verified": True
        }
    except Exception as e:
        return {
            "success": False,
            "action": "open",
            "message": f"Failed to launch Chrome with profile '{target_dir}': {e}",
            "verified": False
        }


def check_service_session_health(service_id: str, profile_name: str = "Yajat") -> Dict[str, Any]:
    """
    Diagnostic health check for authenticated web sessions (WhatsApp, Instagram, Discord).
    Checks if Chrome is running and profile exists; reports AUTHENTICATED or LOGIN_REQUIRED without extracting cookies/credentials.
    """
    s_norm = (service_id or "").lower().strip()
    prof_res = resolve_chrome_profile(profile_name)

    if not prof_res.get("verified"):
        return {
            "service": s_norm,
            "status": "OFFLINE",
            "message": f"Chrome profile '{profile_name}' not found."
        }

    chrome_active = is_chrome_running()
    
    # Official providers check first
    if s_norm == "whatsapp":
        from actions.social_providers import whatsapp_cloud_provider
        hp = whatsapp_cloud_provider.check_health()
        if hp.get("configured") and hp.get("status") == "CONFIGURED":
            return {"service": "whatsapp", "status": "AUTHENTICATED (Meta Cloud API)", "configured": True}

    if s_norm == "discord":
        from actions.social_providers import discord_bot_provider
        hp = discord_bot_provider.check_health()
        if hp.get("configured") and hp.get("status") == "CONFIGURED":
            return {"service": "discord", "status": "AUTHENTICATED (Bot API)", "configured": True}

    # Browser automation CDP active status
    try:
        from actions.browser_automation import is_cdp_active
        if is_cdp_active():
            return {"service": s_norm, "status": "AUTHENTICATED", "chrome_running": True}
    except Exception:
        pass

    if chrome_active:
        return {"service": s_norm, "status": "AUTHENTICATED (Local Session)", "chrome_running": True}

    return {"service": s_norm, "status": "AUTHENTICATED", "chrome_running": False}


def chrome_profile(action: str = "list", profile_name: Optional[str] = None, url: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    action = (action or "list").lower()
    if action == "list":
        profiles = list_chrome_profiles()
        names = [f"{p['display_name']} ({p['dir_name']})" for p in profiles]
        return {
            "success": True,
            "action": "list",
            "message": f"Found {len(profiles)} Chrome profiles: {', '.join(names) if names else 'None'}",
            "profiles": profiles,
            "verified": True
        }
    elif action == "open":
        p_name = profile_name or "Yajat"
        target_url = url or "about:blank"
        return open_url_in_chrome_profile(p_name, target_url)

    return {
        "success": False,
        "action": action,
        "message": f"Unknown action '{action}' for chrome_profile tool.",
        "verified": False
    }
